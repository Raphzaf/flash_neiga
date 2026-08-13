"""
État d'abonnement et catalogue des formules.

Ce sont les deux réponses dont le front a besoin pour router l'élève sans jamais
se fier à une valeur conservée dans le navigateur : où l'envoyer après la
connexion, et quel prix afficher.
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

from server import app
from database import Base, get_db
from models import SubscriptionDB, UserDB

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_subscription_state.db"
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


@pytest.fixture
def student(client, test_db):
    response = client.post(
        "/api/auth/register", json={"email": "sarah@example.com", "password": "motdepasse"}
    )
    assert response.status_code == 200
    user = test_db.query(UserDB).filter(UserDB.email == "sarah@example.com").first()
    return {"id": user.id, "headers": {"Authorization": f"Bearer {response.json()['access_token']}"}}


def add_subscription(test_db, user_id, *, days, status="active"):
    now = datetime.utcnow()
    sub = SubscriptionDB(
        user_id=user_id,
        plan_id="premium_30d",
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=days),
        status=status,
    )
    test_db.add(sub)
    test_db.commit()
    return sub


def test_new_account_has_no_access(client, test_db, student):
    data = client.get("/api/subscriptions/me", headers=student["headers"]).json()

    assert data["has_access"] is False
    assert data["active"] is False
    assert data["subscription"] is None


def test_active_subscription_grants_access(client, test_db, student):
    add_subscription(test_db, student["id"], days=12)

    data = client.get("/api/subscriptions/me", headers=student["headers"]).json()

    assert data["has_access"] is True
    assert data["subscription"]["plan_name"] == "Formule Premium — 30 jours"
    assert data["subscription"]["days_left"] == 11
    assert data["subscription"]["expired"] is False


def test_subscription_past_its_end_date_no_longer_grants_access(client, test_db, student):
    add_subscription(test_db, student["id"], days=-1)

    data = client.get("/api/subscriptions/me", headers=student["headers"]).json()

    assert data["has_access"] is False
    # L'abonnement échu reste visible pour pouvoir proposer un renouvellement.
    assert data["subscription"]["expired"] is True


def test_admin_has_access_without_subscription(client, test_db):
    admin = client.post(
        "/api/auth/register", json={"email": "admin@gmail.com", "password": "motdepasse-admin"}
    )
    data = client.get(
        "/api/subscriptions/me",
        headers={"Authorization": f"Bearer {admin.json()['access_token']}"},
    ).json()

    assert data["is_admin"] is True
    assert data["has_access"] is True
    assert data["active"] is False


def test_subscription_state_requires_authentication(client, test_db):
    assert client.get("/api/subscriptions/me").status_code == 403


def test_visible_plans_catalogue(client, test_db):
    data = client.get("/api/payments/hyp/plans", params={"visible_only": True}).json()

    plan_ids = [p["plan_id"] for p in data["items"]]
    assert plan_ids == [
        "basic_14d", "basic_21d", "basic_30d",
        "premium_14d", "premium_21d", "premium_30d",
    ]
    # Tout ce dont le tunnel a besoin pour afficher une formule.
    for plan in data["items"]:
        assert plan["label"] and plan["period"] and plan["features"]
        assert plan["amount"] > 0 and plan["currency"] == "ILS"

    # Les anciennes formules restent servies pour les abonnements en cours.
    assert "code_14d" in client.get("/api/payments/hyp/plans").json()["plans"]
