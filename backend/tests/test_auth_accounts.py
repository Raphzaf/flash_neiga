"""
Création de compte et connexion.

Couvre les pièges qui empêchent un élève d'entrer sur la plateforme alors qu'il
a bien un compte : casse de l'email, espaces parasites, mot de passe trop court.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from server import app
from database import Base, get_db
from models import UserDB

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_auth_accounts.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_db():
    # L'override est posé par test (et retiré ensuite) : d'autres modules de
    # tests branchent leur propre base sur la même application.
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    try:
        yield TestingSessionLocal()
    finally:
        Base.metadata.drop_all(bind=engine)
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous


@pytest.fixture
def client():
    return TestClient(app)


def register(client, email, password="motdepasse", **extra):
    return client.post("/api/auth/register", json={"email": email, "password": password, **extra})


def login(client, email, password="motdepasse"):
    return client.post("/api/auth/login", data={"username": email, "password": password})


def test_email_is_stored_normalized(client, test_db):
    assert register(client, "  Sarah.Cohen@Gmail.COM  ").status_code == 200
    user = test_db.query(UserDB).first()
    assert user.email == "sarah.cohen@gmail.com"


def test_login_ignores_case_and_spaces(client, test_db):
    register(client, "Sarah@Gmail.com")

    for typed in ("Sarah@Gmail.com", "sarah@gmail.com", " SARAH@GMAIL.COM "):
        assert login(client, typed).status_code == 200, typed


def test_login_works_on_legacy_account_stored_with_capitals(client, test_db):
    """Comptes créés avant la normalisation : la connexion doit rester possible."""
    from auth import hash_password

    test_db.add(UserDB(
        id="legacy-1",
        email="Ancienne.Eleve@Gmail.com",
        hashed_password=hash_password("motdepasse"),
    ))
    test_db.commit()

    assert login(client, "ancienne.eleve@gmail.com").status_code == 200


def test_same_email_in_another_case_is_not_a_second_account(client, test_db):
    assert register(client, "sarah@gmail.com").status_code == 200
    duplicate = register(client, "SARAH@gmail.com")

    assert duplicate.status_code == 400
    assert test_db.query(UserDB).count() == 1


def test_short_password_is_refused(client, test_db):
    response = register(client, "sarah@gmail.com", password="123")

    assert response.status_code == 400
    assert test_db.query(UserDB).count() == 0


def test_wrong_password_is_refused(client, test_db):
    register(client, "sarah@gmail.com")

    assert login(client, "sarah@gmail.com", password="autre-mot-de-passe").status_code == 401


def test_unknown_account_is_refused(client, test_db):
    assert login(client, "inconnue@gmail.com").status_code == 401
