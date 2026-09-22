"""
Tests de la réparation des textes abîmés par un double encodage UTF-8.

Constat sur la base de production : 510 des 1842 questions portaient une
catégorie du type « SÃ©curitÃ© » ou « Connaissance du vÃ©hicule ». L'élève les
voyait dans le filtre d'entraînement et dans ses statistiques.

Deux exigences gouvernent ces tests, parce qu'une réparation de texte en masse
ne se rejoue pas :

1. Elle ne touche QUE ce qui est abîmé. Un texte sain doit ressortir intact,
   même s'il contient des caractères qui ressemblent à du mojibake.
2. Elle est idempotente : la relancer ne dégrade pas ce qu'elle vient de
   réparer.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import text_repair  # noqa: E402
from server import app  # noqa: E402
from database import Base, get_db  # noqa: E402
from models import QuestionDB, TrafficSignDB, User  # noqa: E402
from auth import get_current_user, require_admin  # noqa: E402

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_text_repair.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ADMIN = User(id="admin-1", email="admin@test.fr")
client = TestClient(app)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db():
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    app.dependency_overrides[require_admin] = lambda: ADMIN

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides = previous


def _opts():
    return [
        {"id": "a", "text": "Bonne", "is_correct": True},
        {"id": "b", "text": "Mauvaise", "is_correct": False},
    ]


# ===== La fonction de réparation =====
@pytest.mark.parametrize("mangled, expected", [
    ("SÃ©curitÃ©", "Sécurité"),
    ("Connaissance du vÃ©hicule", "Connaissance du véhicule"),
    ("PrioritÃ©s", "Priorités"),
    ("l'Ã©lÃ¨ve", "l'élève"),
    ("Â« citation Â»", "« citation »"),
    ("StationnementÂ°", "Stationnement°"),
])
def test_mangled_text_is_restored(mangled, expected):
    assert text_repair.repair_mojibake(mangled) == expected


@pytest.mark.parametrize("healthy", [
    "Sécurité",
    "Connaissance du véhicule",
    "Code de la route",
    "Panneaux",
    "Priorité",
    "São Paulo",   # « ã » légitime
    "Ãrea",        # « Ã » seul : ce n'est pas du mojibake
    "",
])
def test_healthy_text_is_left_untouched(healthy):
    """Le faux positif est le vrai danger : il mutilerait un texte correct."""
    assert text_repair.repair_mojibake(healthy) == healthy


def test_repair_is_idempotent():
    """La réparation tourne à chaque démarrage : elle ne doit pas s'accumuler."""
    once = text_repair.repair_mojibake("SÃ©curitÃ©")
    assert text_repair.repair_mojibake(once) == once == "Sécurité"


def test_none_is_tolerated():
    """La catégorie peut être absente en base."""
    assert text_repair.repair_mojibake(None) is None


def test_undecodable_text_is_preserved_rather_than_mutilated():
    """Un mélange de mojibake et de caractères hors latin-1 reste tel quel.

    Mieux vaut un accent abîmé qu'un texte tronqué : on ne répare que ce qu'on
    sait réparer exactement.
    """
    mixed = "SÃ©curitÃ© — 日本語"
    assert text_repair.repair_mojibake(mixed) == mixed


# ===== La réparation en base =====
def test_database_categories_are_repaired(db):
    db.add(QuestionDB(id="q1", text="Question 1", category="SÃ©curitÃ©", options=_opts()))
    db.add(QuestionDB(id="q2", text="Question 2", category="Connaissance du vÃ©hicule", options=_opts()))
    db.add(QuestionDB(id="q3", text="Question 3", category="Code de la route", options=_opts()))
    db.add(TrafficSignDB(id="s1", number="IL-1", name="Stop", description="Stop",
                         category="PrioritÃ©s"))
    db.commit()

    report = text_repair.repair_question_categories(db)
    assert report["questions"] == 2
    assert report["panneaux"] == 1

    categories = {q.id: q.category for q in db.query(QuestionDB).all()}
    assert categories == {
        "q1": "Sécurité",
        "q2": "Connaissance du véhicule",
        "q3": "Code de la route",   # déjà sain, inchangé
    }
    assert db.query(TrafficSignDB).first().category == "Priorités"


def test_database_repair_reports_nothing_on_a_healthy_base(db):
    db.add(QuestionDB(id="q1", text="Question 1", category="Sécurité", options=_opts()))
    db.commit()

    report = text_repair.repair_question_categories(db)
    assert report["questions"] == 0
    assert report["panneaux"] == 0
    assert report["corrections"] == {}


def test_repair_merges_the_mangled_category_with_its_healthy_twin(db):
    """Une catégorie abîmée et sa version saine doivent se rejoindre.

    C'est l'intérêt réel de la réparation : avant, le filtre d'entraînement
    proposait « Sécurité » ET « SÃ©curitÃ© » comme deux rubriques distinctes,
    et les questions de l'une étaient invisibles depuis l'autre.
    """
    db.add(QuestionDB(id="q1", text="Q1", category="SÃ©curitÃ©", options=_opts()))
    db.add(QuestionDB(id="q2", text="Q2", category="Sécurité", options=_opts()))
    db.commit()

    text_repair.repair_question_categories(db)
    assert {q.category for q in db.query(QuestionDB).all()} == {"Sécurité"}


# ===== La route d'administration =====
def test_admin_endpoint_repairs_and_reports(db):
    db.add(QuestionDB(id="q1", text="Question 1", category="SÃ©curitÃ©", options=_opts()))
    db.commit()

    response = client.post("/api/admin/repair-categories")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["questions_corrigees"] == 1
    assert body["corrections"] == {"SÃ©curitÃ©": "Sécurité"}
    assert "1 libellé(s) réparé(s)" in body["message"]


def test_admin_endpoint_is_safe_to_rerun(db):
    db.add(QuestionDB(id="q1", text="Question 1", category="SÃ©curitÃ©", options=_opts()))
    db.commit()

    client.post("/api/admin/repair-categories")
    second = client.post("/api/admin/repair-categories").json()
    assert second["questions_corrigees"] == 0
    assert "base est saine" in second["message"]
