"""
Tests du profil utilisateur : inscription avec prénom/nom, lecture du profil,
modification du nom, et résiliation d'abonnement.
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
from models import UserDB, SubscriptionDB, User  # noqa: E402
from auth import get_current_user  # noqa: E402

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_profile.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TEST_USER = User(id="user-1", email="eleve@test.fr", first_name="Sarah", last_name="Cohen")


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(scope="function")
def db():
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.add(UserDB(id="user-1", email="eleve@test.fr", hashed_password="x",
                       first_name="Sarah", last_name="Cohen"))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides = previous


def test_register_stores_first_and_last_name(db):
    r = client.post("/api/auth/register", json={
        "email": "nouveau@test.fr", "password": "secret6",
        "first_name": "David", "last_name": "Levy",
    })
    assert r.status_code == 200
    user = db.query(UserDB).filter_by(email="nouveau@test.fr").first()
    assert user.first_name == "David"
    assert user.last_name == "Levy"


def test_register_splits_full_name_fallback(db):
    r = client.post("/api/auth/register", json={
        "email": "compat@test.fr", "password": "secret6", "full_name": "Marie Dupont",
    })
    assert r.status_code == 200
    user = db.query(UserDB).filter_by(email="compat@test.fr").first()
    assert user.first_name == "Marie"
    assert user.last_name == "Dupont"


def test_get_profile(db):
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    try:
        r = client.get("/api/profile")
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "eleve@test.fr"
        assert body["first_name"] == "Sarah"
        assert body["has_active_subscription"] is False
        assert body["subscription"] is None
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_update_profile(db):
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    try:
        r = client.patch("/api/profile", json={"first_name": "Sarah-Lea", "last_name": "Cohen-Levy"})
        assert r.status_code == 200
        assert r.json()["first_name"] == "Sarah-Lea"
        user = db.query(UserDB).filter_by(id="user-1").first()
        assert user.last_name == "Cohen-Levy"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_profile_shows_active_subscription_and_cancel(db):
    db.add(SubscriptionDB(
        id="sub-1", user_id="user-1", plan_id="code_30d", status="active",
        start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=30),
    ))
    db.commit()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    try:
        r = client.get("/api/profile")
        body = r.json()
        assert body["has_active_subscription"] is True
        assert body["subscription"]["plan_id"] == "code_30d"
        assert body["subscription"]["plan_name"]  # nom résolu depuis le catalogue

        c = client.post("/api/profile/subscription/cancel")
        assert c.status_code == 200
        assert c.json()["status"] == "cancelled"

        sub = db.query(SubscriptionDB).filter_by(id="sub-1").first()
        assert sub.status == "cancelled"
        assert sub.canceled_at is not None
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_cancel_without_subscription_404(db):
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    try:
        r = client.post("/api/profile/subscription/cancel")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
