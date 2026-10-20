"""
Tests de la rubrique « Mes questions à retravailler » (Phase 1 — coach IA).

Couvre :
- l'enregistrement d'une erreur en mode entraînement (réponse fausse),
- l'absence d'enregistrement sur bonne réponse,
- la liste des questions à retravailler et le compteur du badge,
- la règle de maîtrise (2 bonnes réponses consécutives → mastered),
- l'enregistrement des erreurs à la fin d'un examen.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from server import app  # noqa: E402
from database import Base, get_db  # noqa: E402
from models import (  # noqa: E402
    UserDB, QuestionDB, ExamSessionDB, SubscriptionDB, UserMistakeDB, User,
)
from auth import get_current_user, get_current_user_optional  # noqa: E402

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_mistakes.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TEST_USER = User(id="user-1", email="eleve@test.fr")


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_current_user():
    return TEST_USER


client = TestClient(app)


def _opts():
    return [
        {"id": "a", "text": "Bonne", "is_correct": True},
        {"id": "b", "text": "Mauvaise", "is_correct": False},
    ]


@pytest.fixture(scope="function")
def db():
    # On installe nos overrides le temps du test uniquement, puis on restaure
    # l'état précédent : le module ne pollue pas les autres fichiers de test
    # (le `app` FastAPI est partagé entre modules).
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_current_user_optional] = override_current_user

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.add(UserDB(id="user-1", email="eleve@test.fr", hashed_password="x"))
    # Abonnement actif : l'entraînement et l'examen sont derrière le paywall
    # (`require_subscription`). Sans lui, ces tests recevraient 402 — et ils ne
    # diraient plus rien de la mémoire des erreurs, qu'ils sont censés couvrir.
    # On abonne l'élève plutôt que de neutraliser le paywall, pour que le
    # parcours testé soit celui d'un élève réel.
    session.add(SubscriptionDB(
        id="sub-1", user_id="user-1", plan_id="basic_30d", status="active",
        start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=30),
    ))
    session.add(QuestionDB(id="q1", text="Question 1", category="Priorités", options=_opts()))
    session.add(QuestionDB(id="q2", text="Question 2", category="Croisements", options=_opts()))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides = previous


def test_wrong_training_answer_is_recorded(db):
    res = client.post("/api/training/check", json={"question_id": "q1", "selected_option_id": "b"})
    assert res.status_code == 200
    assert res.json()["is_correct"] is False

    entry = db.query(UserMistakeDB).filter_by(user_id="user-1", question_id="q1").first()
    assert entry is not None
    assert entry.times_wrong == 1
    assert entry.mastered is False


def test_correct_training_answer_not_recorded(db):
    res = client.post("/api/training/check", json={"question_id": "q1", "selected_option_id": "a"})
    assert res.json()["is_correct"] is True
    assert db.query(UserMistakeDB).filter_by(user_id="user-1", question_id="q1").count() == 0


def test_repeated_wrong_answer_increments(db):
    client.post("/api/training/check", json={"question_id": "q1", "selected_option_id": "b"})
    client.post("/api/training/check", json={"question_id": "q1", "selected_option_id": "b"})
    entry = db.query(UserMistakeDB).filter_by(user_id="user-1", question_id="q1").first()
    assert entry.times_wrong == 2


def test_list_and_count(db):
    client.post("/api/training/check", json={"question_id": "q1", "selected_option_id": "b"})
    client.post("/api/training/check", json={"question_id": "q2", "selected_option_id": "b"})

    res = client.get("/api/mistakes")
    body = res.json()
    assert body["total"] == 2
    assert {c["category"] for c in body["categories"]} == {"Priorités", "Croisements"}

    count = client.get("/api/mistakes/count").json()["count"]
    assert count == 2


def test_mastery_after_two_correct_reviews(db):
    # L'élève rate d'abord la question
    client.post("/api/training/check", json={"question_id": "q1", "selected_option_id": "b"})

    # 1re bonne réponse en révision → pas encore maîtrisée
    r1 = client.post("/api/mistakes/review", json={"question_id": "q1", "selected_option_id": "a"})
    assert r1.json()["is_correct"] is True
    assert r1.json()["mastered"] is False
    assert r1.json()["times_correct_since"] == 1

    # 2e bonne réponse consécutive → maîtrisée
    r2 = client.post("/api/mistakes/review", json={"question_id": "q1", "selected_option_id": "a"})
    assert r2.json()["mastered"] is True

    # La question sort de la liste active
    assert client.get("/api/mistakes/count").json()["count"] == 0


def test_wrong_review_resets_streak(db):
    client.post("/api/training/check", json={"question_id": "q1", "selected_option_id": "b"})
    client.post("/api/mistakes/review", json={"question_id": "q1", "selected_option_id": "a"})  # streak = 1
    # Mauvaise réponse → streak remis à 0
    r = client.post("/api/mistakes/review", json={"question_id": "q1", "selected_option_id": "b"})
    assert r.json()["is_correct"] is False
    assert r.json()["times_correct_since"] == 0
    assert r.json()["mastered"] is False


def test_exam_finish_records_mistakes(db):
    # Examen : q1 juste, q2 faux
    exam = ExamSessionDB(
        id="exam-1", user_id="user-1", status="in_progress",
        answers={"q1": "a", "q2": "b"}, question_ids=["q1", "q2"],
    )
    db.add(exam)
    db.commit()

    res = client.post("/api/exam/exam-1/finish")
    assert res.status_code == 200

    mistakes = {m.question_id for m in db.query(UserMistakeDB).filter_by(user_id="user-1").all()}
    assert mistakes == {"q2"}


# ===== Toutes les erreurs doivent arriver dans « à retravailler » =====
def _add_question(db, qid):
    db.add(QuestionDB(id=qid, text=f"Question {qid}", category="Divers", options=_opts()))


def _exam(db, answers, question_ids, status="in_progress", age=timedelta(0)):
    exam = ExamSessionDB(id=f"ex-{len(answers)}-{status}", user_id="user-1", status=status,
                         answers=answers, question_ids=question_ids,
                         created_at=datetime.utcnow() - age)
    db.add(exam)
    db.commit()
    return exam


def _todo(db):
    db.expire_all()
    return {m.question_id: m.times_wrong for m in
            db.query(UserMistakeDB).filter_by(user_id="user-1", mastered=False)}


def test_exam_unanswered_questions_are_reported(db):
    """Une question sans réponse compte fausse dans la note : elle est à retravailler."""
    _add_question(db, "q3")
    exam = _exam(db, {"q1": "a", "q2": "b"}, ["q1", "q2", "q3"])
    res = client.post(f"/api/exam/{exam.id}/finish")
    assert res.status_code == 200
    assert _todo(db) == {"q2": 1, "q3": 1}


def test_finishing_twice_does_not_count_twice(db):
    exam = _exam(db, {"q1": "b"}, ["q1"])
    client.post(f"/api/exam/{exam.id}/finish")
    client.post(f"/api/exam/{exam.id}/finish")
    assert _todo(db) == {"q1": 1}


def test_abandoned_exam_reports_its_wrong_answers(db):
    """Examen jamais terminé (onglet fermé) : ses réponses fausses ne sont pas perdues."""
    _add_question(db, "q3")
    exam = _exam(db, {"q1": "b", "q2": "a"}, ["q1", "q2", "q3"], age=timedelta(hours=3))
    res = client.get("/api/mistakes/count")
    assert res.json()["count"] == 1
    assert _todo(db) == {"q1": 1}            # q3 jamais vue : pas comptée
    db.refresh(exam)
    assert exam.status == "abandoned"
    client.get("/api/mistakes/count")       # une seule fois
    assert _todo(db) == {"q1": 1}


def test_recent_exam_in_progress_is_left_alone(db):
    exam = _exam(db, {"q1": "b"}, ["q1"], age=timedelta(minutes=10))
    client.get("/api/mistakes")
    assert _todo(db) == {}
    db.refresh(exam)
    assert exam.status == "in_progress"


def test_one_failing_record_does_not_erase_the_others(db, monkeypatch):
    """Un incident sur une question n'efface plus les erreurs déjà notées de l'examen."""
    import routes.mistakes as mistakes
    real = mistakes._apply_mistake

    def flaky(session, user_id, question_id):
        if question_id == "q2":
            raise RuntimeError("panne ponctuelle")
        return real(session, user_id, question_id)

    monkeypatch.setattr(mistakes, "_apply_mistake", flaky)
    _add_question(db, "q3")
    exam = _exam(db, {"q1": "b", "q2": "b", "q3": "b"}, ["q1", "q2", "q3"])
    assert client.post(f"/api/exam/{exam.id}/finish").status_code == 200
    assert _todo(db) == {"q1": 1, "q3": 1}


def test_stats_summary_counts_recent_exam_errors(db):
    """« Erreurs totales » et les catégories reflètent les derniers examens."""
    db.add(QuestionDB(id="q3", text="Question 3", category="Croisements", options=_opts()))
    exam = ExamSessionDB(id="ex-stats", user_id="user-1", status="completed",
                         answers={"q1": "a", "q2": "b"}, question_ids=["q1", "q2", "q3"],
                         completed_at=datetime.utcnow(), score=33)
    db.add(exam)
    db.commit()
    body = client.get("/api/stats/summary").json()
    assert body["total_errors"] == 2                 # q2 fausse + q3 sans réponse
    assert body["best_category"] == "Priorités"      # 0 erreur sur 1
    assert body["worst_category"] == "Croisements"   # 2 erreurs sur 2
