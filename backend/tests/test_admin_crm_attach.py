"""
CRM : rattrapage d'un paiement encaissé sans compte.

C'est l'outil de dépannage de l'équipe quand un élève a payé mais ne peut pas
entrer : le paiement est rattaché à un compte (créé au besoin) et l'abonnement
s'ouvre immédiatement.
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
from models import TransactionDB, SubscriptionDB, UserDB

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_admin_crm_attach.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ADMIN_EMAIL = "admin@gmail.com"   # valeur par défaut de ADMIN_EMAILS


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
def admin_headers(client, test_db):
    response = client.post(
        "/api/auth/register",
        json={"email": ADMIN_EMAIL, "password": "motdepasse-admin"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def orphan_transaction(test_db):
    """Paiement encaissé auquel aucun compte n'est rattaché."""
    transaction = TransactionDB(
        plan_id="code_14d",
        amount=99,
        currency="ILS",
        status="completed",
        event_data={"user_email": "sarah@example.com", "needs_account": True},
    )
    test_db.add(transaction)
    test_db.commit()
    test_db.refresh(transaction)
    return transaction


def test_orphan_payments_are_listed(client, test_db, admin_headers, orphan_transaction):
    response = client.get(
        "/api/admin/crm/transactions", params={"needs_account": True}, headers=admin_headers
    )
    assert response.status_code == 200

    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["needs_account"] is True
    assert items[0]["has_account"] is False
    # L'email saisi au paiement reste la piste pour retrouver l'élève.
    assert items[0]["user_email"] == "sarah@example.com"


def test_attach_creates_account_and_opens_subscription(client, test_db, admin_headers, orphan_transaction):
    response = client.post(
        f"/api/admin/crm/transactions/{orphan_transaction.id}/attach",
        json={"email": "Sarah@Example.com", "first_name": "Sarah", "last_name": "Cohen"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["user"]["email"] == "sarah@example.com"
    assert data["subscription"]["status"] == "active"
    # Mot de passe provisoire à transmettre à l'élève.
    assert data["temporary_password"]

    login = client.post(
        "/api/auth/login",
        data={"username": "sarah@example.com", "password": data["temporary_password"]},
    )
    assert login.status_code == 200

    test_db.refresh(orphan_transaction)
    assert orphan_transaction.user_id == data["user"]["id"]
    assert orphan_transaction.event_data["attached_by"] == ADMIN_EMAIL


def test_attach_to_existing_account_keeps_its_password(client, test_db, admin_headers, orphan_transaction):
    client.post("/api/auth/register", json={"email": "sarah@example.com", "password": "motdepasse"})

    response = client.post(
        f"/api/admin/crm/transactions/{orphan_transaction.id}/attach",
        json={"email": "sarah@example.com"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["temporary_password"] is None

    assert test_db.query(UserDB).filter(UserDB.email == "sarah@example.com").count() == 1
    login = client.post(
        "/api/auth/login", data={"username": "sarah@example.com", "password": "motdepasse"}
    )
    assert login.status_code == 200


def test_attach_is_refused_twice(client, test_db, admin_headers, orphan_transaction):
    first = client.post(
        f"/api/admin/crm/transactions/{orphan_transaction.id}/attach",
        json={"email": "sarah@example.com"},
        headers=admin_headers,
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/admin/crm/transactions/{orphan_transaction.id}/attach",
        json={"email": "autre@example.com"},
        headers=admin_headers,
    )
    assert second.status_code == 409
    assert test_db.query(SubscriptionDB).count() == 1


def test_attach_requires_admin(client, test_db, orphan_transaction):
    eleve = client.post(
        "/api/auth/register", json={"email": "eleve@example.com", "password": "motdepasse"}
    )
    response = client.post(
        f"/api/admin/crm/transactions/{orphan_transaction.id}/attach",
        json={"email": "eleve@example.com"},
        headers={"Authorization": f"Bearer {eleve.json()['access_token']}"},
    )
    assert response.status_code == 403
    assert test_db.query(SubscriptionDB).count() == 0
