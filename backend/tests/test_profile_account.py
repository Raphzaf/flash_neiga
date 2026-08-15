"""
Ce qu'un élève gère lui-même depuis son compte : mot de passe, email,
abonnement, historique de paiements.
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
from models import SubscriptionDB, TransactionDB, UserDB

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_profile_account.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

PASSWORD = "motdepasse"


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
        "/api/auth/register",
        json={"email": "sarah@example.com", "password": PASSWORD, "first_name": "Sarah"},
    )
    assert response.status_code == 200
    user = test_db.query(UserDB).filter(UserDB.email == "sarah@example.com").first()
    return {"id": user.id, "headers": {"Authorization": f"Bearer {response.json()['access_token']}"}}


def subscribe(test_db, user_id, *, days=20, status="active"):
    now = datetime.utcnow()
    sub = SubscriptionDB(
        user_id=user_id, plan_id="premium_30d", start_date=now,
        end_date=now + timedelta(days=days), status=status,
    )
    test_db.add(sub)
    test_db.commit()
    return sub


# ===== Mot de passe =====
def test_student_changes_their_password(client, test_db, student):
    response = client.post(
        "/api/profile/password",
        json={"current_password": PASSWORD, "new_password": "nouveau-mot-de-passe"},
        headers=student["headers"],
    )
    assert response.status_code == 200

    assert client.post(
        "/api/auth/login", data={"username": "sarah@example.com", "password": "nouveau-mot-de-passe"}
    ).status_code == 200
    assert client.post(
        "/api/auth/login", data={"username": "sarah@example.com", "password": PASSWORD}
    ).status_code == 401


def test_password_change_requires_the_current_one(client, test_db, student):
    response = client.post(
        "/api/profile/password",
        json={"current_password": "je-ne-sais-pas", "new_password": "nouveau-mot-de-passe"},
        headers=student["headers"],
    )
    assert response.status_code == 403
    # L'ancien mot de passe reste valable.
    assert client.post(
        "/api/auth/login", data={"username": "sarah@example.com", "password": PASSWORD}
    ).status_code == 200


def test_new_password_must_be_long_enough(client, test_db, student):
    response = client.post(
        "/api/profile/password",
        json={"current_password": PASSWORD, "new_password": "123"},
        headers=student["headers"],
    )
    assert response.status_code == 400


# ===== Email =====
def test_student_changes_their_login_email(client, test_db, student):
    response = client.post(
        "/api/profile/email",
        json={"new_email": "Sarah.Cohen@Example.com", "current_password": PASSWORD},
        headers=student["headers"],
    )
    assert response.status_code == 200
    assert response.json()["email"] == "sarah.cohen@example.com"

    # La session reste ouverte, et la connexion se fait avec le nouvel email.
    assert client.get("/api/profile", headers=student["headers"]).status_code == 200
    assert client.post(
        "/api/auth/login", data={"username": "sarah.cohen@example.com", "password": PASSWORD}
    ).status_code == 200


def test_email_change_requires_the_password(client, test_db, student):
    response = client.post(
        "/api/profile/email",
        json={"new_email": "autre@example.com", "current_password": "mauvais"},
        headers=student["headers"],
    )
    assert response.status_code == 403


def test_email_already_taken_is_refused(client, test_db, student):
    client.post("/api/auth/register", json={"email": "noa@example.com", "password": PASSWORD})

    response = client.post(
        "/api/profile/email",
        json={"new_email": "noa@example.com", "current_password": PASSWORD},
        headers=student["headers"],
    )
    assert response.status_code == 409


# ===== Abonnement =====
def test_cancelled_subscription_keeps_access_until_its_end_date(client, test_db, student):
    """Résilier veut dire « ne pas renouveler », pas « perdre ce qui est payé »."""
    subscribe(test_db, student["id"], days=20)

    cancel = client.post("/api/profile/subscription/cancel", headers=student["headers"])
    assert cancel.status_code == 200

    state = client.get("/api/subscriptions/me", headers=student["headers"]).json()
    assert state["has_access"] is True
    assert state["subscription"]["status"] == "cancelled"

    profile = client.get("/api/profile", headers=student["headers"]).json()
    assert profile["subscription"]["is_active"] is True
    assert profile["has_active_subscription"] is True


def test_expired_cancelled_subscription_no_longer_grants_access(client, test_db, student):
    subscribe(test_db, student["id"], days=-1, status="cancelled")

    state = client.get("/api/subscriptions/me", headers=student["headers"]).json()
    assert state["has_access"] is False


def test_cancelling_twice_is_refused(client, test_db, student):
    subscribe(test_db, student["id"], days=20)

    assert client.post("/api/profile/subscription/cancel", headers=student["headers"]).status_code == 200
    assert client.post("/api/profile/subscription/cancel", headers=student["headers"]).status_code == 404


# ===== Paiements =====
def test_student_sees_only_their_own_paid_payments(client, test_db, student):
    test_db.add_all([
        TransactionDB(
            user_id=student["id"], plan_id="premium_30d", amount=149, currency="ILS",
            status="completed", completed_at=datetime.utcnow(),
        ),
        # En attente : n'a pas à figurer dans l'historique.
        TransactionDB(
            user_id=student["id"], plan_id="basic_14d", amount=69, currency="ILS", status="pending",
        ),
        # Paiement d'un autre élève.
        TransactionDB(
            user_id="un-autre-eleve", plan_id="basic_30d", amount=99, currency="ILS",
            status="completed", completed_at=datetime.utcnow(),
        ),
    ])
    test_db.commit()

    data = client.get("/api/profile/payments", headers=student["headers"]).json()

    assert data["count"] == 1
    payment = data["items"][0]
    assert payment["amount"] == 149
    assert payment["plan_name"] == "Formule Premium — 30 jours"
    assert len(payment["reference"]) == 8


def test_account_pages_require_authentication(client, test_db):
    assert client.get("/api/profile").status_code == 403
    assert client.get("/api/profile/payments").status_code == 403
    assert client.post("/api/profile/password", json={
        "current_password": "x", "new_password": "yyyyyy"
    }).status_code == 403
