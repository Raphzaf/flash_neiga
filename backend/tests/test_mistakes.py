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
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from server import app  # noqa: E402
from database import Base, get_db  # noqa: E402
from models import UserDB, QuestionDB, ExamSessionDB, UserMistakeDB, User  # noqa: E402
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
