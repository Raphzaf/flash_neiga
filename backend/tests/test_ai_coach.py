"""
Tests du coach IA (Phases 2, 3, 4) avec l'appel Claude stubé (aucun réseau).

Couvre :
- mini-leçon : génération + mise en cache + service depuis le cache (0 appel IA),
- 503 propre quand l'IA n'est pas configurée et qu'il n'y a pas de cache,
- bilan de série : encouragement chiffré calculé en SQL + cache du rapport,
- questions pièges : agrégation tous élèves + synthèse admin.
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
    UserDB, QuestionDB, ExamSessionDB, UserMistakeDB, AILessonDB, User,
)
from auth import get_current_user, get_current_user_optional  # noqa: E402
import routes.ai_coach as ai_coach  # noqa: E402
import routes.trap_questions as trap_questions  # noqa: E402

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_ai_coach.db"
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
        {"id": "a", "text": "Bonne réponse", "is_correct": True},
        {"id": "b", "text": "Mauvaise réponse", "is_correct": False},
    ]


FAKE_LESSON = {
    "explication": "Tu t'es trompé parce que…",
    "regle": "En Israël, la règle dit que…",
    "erreurs_a_eviter": ["Ne pas confondre X et Y", "Vérifier le panneau"],
    "schema_svg": None,
}

FAKE_REPORT = {
    "notions_maitrisees": ["Priorités"],
    "notions_a_retravailler": [
        {"notion": "Croisements", "conseil": "Revois le cours", "cours_recommande": "Les croisements"}
    ],
    "mini_cours": [{"question_resume": "Q2", "explication_claire": "Voici pourquoi…"}],
    "message_prof": "Tu progresses, continue !",
}

FAKE_SYNTHESIS = {
    "intro": "Voici les pièges les plus fréquents.",
    "themes": [{"titre": "Priorité à droite", "pourquoi": "Souvent mal comprise", "conseil": "Ralentis"}],
}


@pytest.fixture(scope="function")
def db(monkeypatch):
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_current_user_optional] = override_current_user

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.add(UserDB(id="user-1", email="eleve@test.fr", hashed_password="x"))
    session.add(QuestionDB(id="q1", text="Question 1", category="Priorités", options=_opts(),
                           explanation="Explication officielle q1"))
    session.add(QuestionDB(id="q2", text="Question 2", category="Croisements", options=_opts()))
    session.commit()

    # Par défaut, l'IA est "configurée" et renvoie des contenus factices.
    monkeypatch.setattr(ai_coach, "ai_configured", lambda: True)
    monkeypatch.setattr(trap_questions, "ai_configured", lambda: True)

    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides = previous


# ===== Phase 2 : mini-leçon =====
def test_lesson_generated_then_cached(db, monkeypatch):
    calls = {"n": 0}

    def fake_call(**kwargs):
        calls["n"] += 1
        return dict(FAKE_LESSON)

    monkeypatch.setattr(ai_coach, "call_structured", fake_call)

    r1 = client.post("/api/ai-coach/lesson", json={"question_id": "q1", "selected_option_id": "b"})
    assert r1.status_code == 200
    body = r1.json()
    assert body["explication"] == FAKE_LESSON["explication"]
    assert body["cached"] is False
    assert calls["n"] == 1

    # 2e appel identique → servi depuis le cache, aucun appel IA supplémentaire
    r2 = client.post("/api/ai-coach/lesson", json={"question_id": "q1", "selected_option_id": "b"})
    assert r2.status_code == 200
    assert r2.json()["cached"] is True
    assert calls["n"] == 1

    assert db.query(AILessonDB).count() == 1


def test_lesson_503_when_ai_unavailable_and_no_cache(db, monkeypatch):
    monkeypatch.setattr(ai_coach, "ai_configured", lambda: False)
    r = client.post("/api/ai-coach/lesson", json={"question_id": "q1", "selected_option_id": "b"})
    assert r.status_code == 503
    assert "prof" in r.json()["detail"].lower()


def test_lesson_missing_question(db):
    r = client.post("/api/ai-coach/lesson", json={"question_id": "nope", "selected_option_id": "b"})
    assert r.status_code == 404


# ===== Chatbot =====
def test_chat_reply(db, monkeypatch):
    captured = {}

    def fake_chat(system, history, **kwargs):
        captured["system"] = system
        captured["history"] = history
        return "En Israël, la priorité à droite s'applique sauf panneau contraire."

    monkeypatch.setattr(ai_coach, "call_chat", fake_chat)

    r = client.post("/api/ai-coach/chat", json={
        "messages": [
            {"role": "user", "content": "C'est quoi la priorité à droite ?"},
        ],
    })
    assert r.status_code == 200
    assert "priorité" in r.json()["reply"].lower()
    assert captured["history"][-1]["role"] == "user"


def test_chat_requires_last_user_message(db):
    r = client.post("/api/ai-coach/chat", json={
        "messages": [{"role": "assistant", "content": "Bonjour"}],
    })
    assert r.status_code == 400


def test_chat_503_when_ai_unavailable(db, monkeypatch):
    monkeypatch.setattr(ai_coach, "ai_configured", lambda: False)
    r = client.post("/api/ai-coach/chat", json={"messages": [{"role": "user", "content": "salut"}]})
    assert r.status_code == 503


# ===== Phase 3 : bilan de série + encouragement chiffré =====
def test_series_report_and_encouragement(db, monkeypatch):
    now = datetime.utcnow()
    # Semaine précédente : score 65 ; semaine actuelle : score 82
    db.add(ExamSessionDB(id="ex-prev", user_id="user-1", status="completed",
                         answers={}, question_ids=["q1", "q2"], score=65,
                         completed_at=now - timedelta(days=10)))
    db.add(ExamSessionDB(id="ex-cur", user_id="user-1", status="completed",
                         answers={"q1": "a", "q2": "b"}, question_ids=["q1", "q2"], score=82,
                         completed_at=now - timedelta(days=2)))
    db.commit()

    monkeypatch.setattr(ai_coach, "call_structured", lambda **k: dict(FAKE_REPORT))

    r = client.post("/api/ai-coach/series-report", json={"session_id": "ex-cur"})
    assert r.status_code == 200
    body = r.json()
    # Chiffres exacts issus du SQL, pas de l'IA
    assert body["encouragement"] == {"current_pct": 82, "previous_pct": 65, "has_history": True}
    assert body["report"]["message_prof"] == FAKE_REPORT["message_prof"]
    assert body["cached"] is False

    # 2e appel → rapport servi depuis le cache
    r2 = client.post("/api/ai-coach/series-report", json={"session_id": "ex-cur"})
    assert r2.json()["cached"] is True


def test_series_report_no_history(db, monkeypatch):
    now = datetime.utcnow()
    db.add(ExamSessionDB(id="ex-solo", user_id="user-1", status="completed",
                         answers={"q1": "a"}, question_ids=["q1"], score=90,
                         completed_at=now - timedelta(days=1)))
    db.commit()
    monkeypatch.setattr(ai_coach, "call_structured", lambda **k: dict(FAKE_REPORT))

    r = client.post("/api/ai-coach/series-report", json={"session_id": "ex-solo"})
    assert r.status_code == 200
    enc = r.json()["encouragement"]
    assert enc["has_history"] is False
    assert enc["previous_pct"] is None


# ===== Phase 4 : questions pièges =====
def test_trap_questions_aggregation(db):
    # user-1 rate q1 (3x) et q2 (1x) ; user-2 rate q1 (2x)
    db.add(UserDB(id="user-2", email="autre@test.fr", hashed_password="x"))
    db.add(UserMistakeDB(user_id="user-1", question_id="q1", times_wrong=3))
    db.add(UserMistakeDB(user_id="user-1", question_id="q2", times_wrong=1))
    db.add(UserMistakeDB(user_id="user-2", question_id="q1", times_wrong=2))
    db.commit()

    r = client.get("/api/trap-questions?limit=30")
    assert r.status_code == 200
    body = r.json()
    # q1 en tête (5 erreurs, 2 élèves), q2 ensuite
    assert body["questions"][0]["question"]["id"] == "q1"
    assert body["questions"][0]["stats"]["total_wrong"] == 5
    assert body["questions"][0]["stats"]["distinct_users"] == 2
    # 2 élèves distincts ont fait des erreurs → q1 piège 100%
    assert body["questions"][0]["stats"]["percent_trapped"] == 100


def test_trap_synthesis_admin(db, monkeypatch):
    db.add(UserMistakeDB(user_id="user-1", question_id="q1", times_wrong=3))
    db.commit()
    monkeypatch.setattr(trap_questions, "call_structured", lambda **k: dict(FAKE_SYNTHESIS))

    r = client.post("/api/admin/trap-questions/synthesis")
    assert r.status_code == 200
    assert r.json()["synthesis"]["intro"] == FAKE_SYNTHESIS["intro"]

    # La synthèse est ensuite lisible et jointe à la liste
    r2 = client.get("/api/trap-questions")
    assert r2.json()["synthesis"]["themes"][0]["titre"] == "Priorité à droite"
