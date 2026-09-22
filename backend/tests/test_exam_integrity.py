"""
Tests d'intégrité de l'examen.

Deux défauts constatés sur l'API en production sont couverts ici :

1. `/api/exam/start` renvoyait `is_correct` pour chaque option — le corrigé
   partait avec le sujet, lisible dans les outils du navigateur.
2. Les routes `/api/exam/{id}` ne vérifiaient pas à qui appartenait l'épreuve :
   un identifiant suffisait pour lire, répondre à ou clore l'examen d'un autre
   élève, et pour y inscrire des erreurs à sa place.
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
from models import ExamSessionDB, QuestionDB, SubscriptionDB, UserDB, User  # noqa: E402
from auth import get_current_user, get_current_user_optional, require_subscription  # noqa: E402

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_exam_integrity.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SARAH = User(id="u-sarah", email="sarah@test.fr")
DAVID = User(id="u-david", email="david@test.fr")

client = TestClient(app)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _act_as(user: User) -> None:
    """Fait parler l'API au nom de cet élève, abonnement supposé actif."""
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_optional] = lambda: user
    app.dependency_overrides[require_subscription] = lambda: user


@pytest.fixture(scope="function")
def db():
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    for user in (SARAH, DAVID):
        session.add(UserDB(id=user.id, email=user.email, hashed_password="x"))
        session.add(SubscriptionDB(
            id=f"sub-{user.id}", user_id=user.id, plan_id="basic_30d", status="active",
            start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=30),
        ))

    # Assez de questions jouables pour qu'une série se constitue sans amorçage.
    for index in range(40):
        session.add(QuestionDB(
            id=f"q{index}",
            text=f"Question {index} ?",
            category="Code de la route",
            options=[
                {"id": f"q{index}-a", "text": "Bonne réponse", "is_correct": True},
                {"id": f"q{index}-b", "text": "Mauvaise réponse", "is_correct": False},
                {"id": f"q{index}-c", "text": "Autre mauvaise", "is_correct": False},
            ],
            explanation="Parce que c'est la règle.",
        ))
    session.commit()

    _act_as(SARAH)
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides = previous


# ===== 1) Le corrigé ne part pas avec le sujet =====
def test_exam_start_never_reveals_the_correct_answer(db):
    """Aucune option servie à l'élève ne doit porter `is_correct`."""
    response = client.post("/api/exam/start", json={})
    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body["questions"]) == 30
    for question in body["questions"]:
        assert question["options"], "une question sans option est injouable"
        for option in question["options"]:
            assert "is_correct" not in option
            # Ce dont le sujet a réellement besoin est toujours là.
            assert option["id"] and option["text"]

    # Vérification brute sur la réponse entière : aucune formulation de la clé.
    assert "is_correct" not in response.text


def test_training_question_list_never_reveals_the_correct_answer(db):
    """Même règle pour l'entraînement : la correction est demandée au serveur."""
    response = client.get("/api/questions")
    assert response.status_code == 200, response.text
    assert "is_correct" not in response.text
    for question in response.json():
        for option in question["options"]:
            assert set(option) == {"id", "text"}


def test_training_check_still_corrects_server_side(db):
    """Retirer la clé du sujet ne doit pas priver l'élève de sa correction."""
    response = client.post("/api/training/check", json={
        "question_id": "q0", "selected_option_id": "q0-b",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_correct"] is False
    assert body["correct_option_id"] == "q0-a"


def test_exam_details_reveals_answers_once_finished(db):
    """Après l'épreuve, le corrigé est légitime : c'est la correction de l'élève."""
    exam_id = client.post("/api/exam/start", json={}).json()["id"]
    client.post("/api/exam/start", json={})  # une seconde série ne gêne pas
    details = client.get(f"/api/exam/{exam_id}/details")
    assert details.status_code == 200, details.text
    questions = details.json()["questions"]
    assert questions, "la correction doit porter sur les questions tirées"
    assert all(q["correct_option_id"] for q in questions)


# ===== 2) Une épreuve appartient à un seul élève =====
def _start_exam_as(user: User) -> str:
    _act_as(user)
    response = client.post("/api/exam/start", json={})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_another_student_cannot_read_your_exam(db):
    exam_id = _start_exam_as(SARAH)
    _act_as(DAVID)
    assert client.get(f"/api/exam/{exam_id}").status_code == 404


def test_another_student_cannot_answer_your_exam(db):
    """Répondre à la place d'un autre faussait sa note — et sa liste d'erreurs."""
    exam_id = _start_exam_as(SARAH)
    question_id = client.get(f"/api/exam/{exam_id}/details").json()["questions"][0]["question_id"]

    _act_as(DAVID)
    response = client.post(
        f"/api/exam/{exam_id}/answer",
        json={"question_id": question_id, "selected_option_id": f"{question_id}-b"},
    )
    assert response.status_code == 404

    # Et l'épreuve de Sarah est restée intacte.
    _act_as(SARAH)
    exam = db.query(ExamSessionDB).filter(ExamSessionDB.id == exam_id).first()
    db.refresh(exam)
    assert not exam.answers


def test_another_student_cannot_finish_your_exam(db):
    exam_id = _start_exam_as(SARAH)
    _act_as(DAVID)
    assert client.post(f"/api/exam/{exam_id}/finish").status_code == 404

    _act_as(SARAH)
    exam = db.query(ExamSessionDB).filter(ExamSessionDB.id == exam_id).first()
    db.refresh(exam)
    assert exam.status == "in_progress"
    assert exam.score is None


def test_another_student_cannot_read_your_correction(db):
    """La correction d'autrui révélerait ses réponses et son score."""
    exam_id = _start_exam_as(SARAH)
    _act_as(DAVID)
    assert client.get(f"/api/exam/{exam_id}/details").status_code == 404


def test_missing_and_foreign_exams_are_indistinguishable(db):
    """Même réponse pour « n'existe pas » et « appartient à un autre ».

    Distinguer les deux dirait à l'appelant quels identifiants sont réels.
    """
    exam_id = _start_exam_as(SARAH)
    _act_as(DAVID)
    foreign = client.get(f"/api/exam/{exam_id}")
    unknown = client.get("/api/exam/does-not-exist")
    assert foreign.status_code == unknown.status_code == 404
    assert foreign.json() == unknown.json()


def test_owner_keeps_full_access_to_their_exam(db):
    """Le durcissement ne doit rien retirer à l'élève légitime."""
    exam_id = _start_exam_as(SARAH)
    questions = client.get(f"/api/exam/{exam_id}/details").json()["questions"]

    assert client.get(f"/api/exam/{exam_id}").status_code == 200
    for question in questions:
        answer = client.post(f"/api/exam/{exam_id}/answer", json={
            "question_id": question["question_id"],
            "selected_option_id": question["correct_option_id"],
        })
        assert answer.status_code == 200

    finished = client.post(f"/api/exam/{exam_id}/finish")
    assert finished.status_code == 200, finished.text
    body = finished.json()
    assert body["correct_answers"] == len(questions)
    assert body["score"] == 100
    assert body["passed"] is True


def test_admin_can_inspect_any_exam(db):
    """Un administrateur doit pouvoir examiner une épreuve pour une réclamation."""
    exam_id = _start_exam_as(SARAH)
    _act_as(User(id="u-admin", email="admin@gmail.com"))
    assert client.get(f"/api/exam/{exam_id}").status_code == 200
    assert client.get(f"/api/exam/{exam_id}/details").status_code == 200
