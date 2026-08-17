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
def student_with_subscription(client, test_db):
    """Un élève ayant souscrit lui-même son abonnement."""
    from datetime import datetime, timedelta

    client.post("/api/auth/register", json={"email": "eleve@example.com", "password": "motdepasse"})
    user = test_db.query(UserDB).filter(UserDB.email == "eleve@example.com").first()
    now = datetime.utcnow()
    subscription = SubscriptionDB(
        user_id=user.id,
        plan_id="premium_30d",
        start_date=now,
        end_date=now + timedelta(days=30),
        status="active",
    )
    test_db.add(subscription)
    test_db.commit()
    return user.id, subscription.id


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


def test_admins_cannot_write_subscriptions(client, test_db, admin_headers, student_with_subscription):
    """L'abonnement appartient à l'élève.

    Un administrateur ne peut ni en accorder un, ni le résilier : ces routes
    n'existent plus. Le seul geste possible reste de rattacher un paiement déjà
    encaissé à son compte.
    """
    user_id, subscription_id = student_with_subscription

    grant = client.post(
        f"/api/admin/crm/users/{user_id}/subscriptions",
        json={"plan_id": "premium_30d"},
        headers=admin_headers,
    )
    cancel = client.post(
        f"/api/admin/crm/subscriptions/{subscription_id}/cancel", headers=admin_headers
    )

    assert grant.status_code == 404
    assert cancel.status_code == 404

    # L'abonnement de l'élève est intact.
    subscription = test_db.query(SubscriptionDB).filter(SubscriptionDB.id == subscription_id).first()
    assert subscription.status == "active"
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


def test_crm_shows_and_searches_by_phone(client, test_db, admin_headers):
    client.post("/api/auth/register", json={
        "email": "noa@example.com", "password": "motdepasse",
        "first_name": "Noa", "phone": "054 123 45 67",
    })

    listing = client.get(
        "/api/admin/crm/users", params={"search": "054 123"}, headers=admin_headers
    ).json()
    assert [u["email"] for u in listing["items"]] == ["noa@example.com"]
    assert listing["items"][0]["phone"] == "054 123 45 67"

    user_id = listing["items"][0]["id"]
    detail = client.get(f"/api/admin/crm/users/{user_id}", headers=admin_headers).json()
    assert detail["phone"] == "054 123 45 67"

    updated = client.patch(
        f"/api/admin/crm/users/{user_id}", json={"phone": "052 000 11 22"}, headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["phone"] == "052 000 11 22"
