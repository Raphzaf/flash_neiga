"""
Unit tests for HYP payment integration
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import sys

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from server import app
from database import Base, get_db
from models import TransactionDB, SubscriptionDB, UserDB

# Create test database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_hyp.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override get_db dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Setup and teardown
@pytest.fixture(scope="function")
def test_db():
    Base.metadata.create_all(bind=engine)
    yield TestingSessionLocal()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def no_signature_check(monkeypatch):
    """Les notifications HYP sont signées en production (HYP_REQUIRE_SIGNATURE).

    Les tests ne disposent d'aucun terminal HYP pour produire une signature :
    on désactive la vérification côté module, sans toucher au comportement par
    défaut de l'application.
    """
    import routes.hyp_payments as hyp
    monkeypatch.setattr(hyp, "HYP_REQUIRE_SIGNATURE", False)

# Test data
SAMPLE_USER = {
    "id": "test-user-123",
    "email": "test@example.com",
    "hashed_password": "hashed"
}

SAMPLE_PLAN = {
    "plan_id": "code_14d",
    "amount": 99,
    "currency": "ILS",
    "duration_days": 14
}


class TestHypConfig:
    """Test HYP configuration and setup"""
    
    def test_verify_config_without_api_key(self, client):
        """Test verify-config endpoint when API key is not set"""
        with patch.dict('os.environ', {'HYP_API_KEY': ''}):
            response = client.get("/api/payments/hyp/verify-config")
            assert response.status_code == 500
            assert "HYP API key not configured" in response.json()["detail"]
    
    def test_verify_config_with_api_key(self, client):
        """Test verify-config endpoint when API key is set"""
        # HYP_API_KEY is read into a module-level constant at import time, so
        # patch the constant directly rather than os.environ.
        with patch('routes.hyp_payments.HYP_API_KEY', 'test-key'):
            response = client.get("/api/payments/hyp/verify-config")
            assert response.status_code == 200
            data = response.json()
            assert data["hyp_configured"] == True
            assert "terminal_id" in data
            assert "plans_loaded" in data
    
    def test_get_plans(self, client):
        """Test get plans endpoint"""
        response = client.get("/api/payments/hyp/plans")
        assert response.status_code == 200
        data = response.json()
        assert "plans" in data
        assert "count" in data
        assert data["count"] > 0


class TestCreatePayment:
    """Test payment creation"""
    
    def test_create_payment_invalid_plan(self, client, test_db):
        """Test creating payment with invalid plan ID"""
        response = client.post(
            "/api/payments/hyp/create-payment",
            json={
                "plan_id": "invalid_plan",
                "user_email": "test@example.com"
            }
        )
        assert response.status_code == 400
        assert "Invalid plan_id" in response.json()["detail"]
    
    def test_create_payment_user_not_found(self, client, test_db):
        """Test creating payment with non-existent user ID"""
        response = client.post(
            "/api/payments/hyp/create-payment",
            json={
                "plan_id": "code_14d",
                "user_id": "non-existent-user",
                "user_email": "test@example.com"
            }
        )
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]
    
    @patch('routes.hyp_payments.create_hyp_payment_url')
    def test_create_payment_success(self, mock_create_url, client, test_db):
        """Test successful payment creation"""
        # Setup mock
        mock_create_url.return_value = "https://icom.yaad.net/p/?test=true"
        
        # Create test user
        user = UserDB(**SAMPLE_USER)
        test_db.add(user)
        test_db.commit()
        
        # Create payment
        response = client.post(
            "/api/payments/hyp/create-payment",
            json={
                "plan_id": "code_14d",
                "user_id": SAMPLE_USER["id"],
                "user_email": SAMPLE_USER["email"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "payment_url" in data
        assert "transaction_id" in data
        assert data["plan_id"] == "code_14d"
        assert data["amount"] == 99
        assert data["currency"] == "ILS"
        
        # Verify transaction was created in DB
        transaction = test_db.query(TransactionDB).filter(
            TransactionDB.id == data["transaction_id"]
        ).first()
        assert transaction is not None
        assert transaction.status == "pending"
        assert transaction.plan_id == "code_14d"


class TestHypCallback:
    """Test HYP callback handling"""
    
    def test_callback_missing_transaction_id(self, client, test_db):
        """Test callback without transaction ID"""
        response = client.post(
            "/api/payments/hyp/callback",
            json={}
        )
        assert response.status_code == 400
        assert "Missing transaction ID" in response.json()["detail"]
    
    def test_callback_transaction_not_found(self, client, test_db):
        """Test callback with non-existent transaction"""
        response = client.post(
            "/api/payments/hyp/callback",
            json={
                "Order": "non-existent-transaction"
            }
        )
        assert response.status_code == 404
        assert "Transaction not found" in response.json()["detail"]
    
    def test_callback_payment_success(self, client, test_db):
        """Test successful payment callback"""
        # Create test user
        user = UserDB(**SAMPLE_USER)
        test_db.add(user)
        test_db.commit()
        
        # Create test transaction
        transaction = TransactionDB(
            user_id=user.id,
            plan_id="code_14d",
            amount=99,
            currency="ILS",
            status="pending"
        )
        test_db.add(transaction)
        test_db.commit()
        
        # Send callback
        response = client.post(
            "/api/payments/hyp/callback",
            json={
                "Order": transaction.id,
                "CCode": "0",
                "Id": "hyp-trans-123",
                "Amount": "9900"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify transaction was updated
        test_db.refresh(transaction)
        assert transaction.status == "completed"
        assert transaction.hyp_transaction_id == "hyp-trans-123"
        assert transaction.completed_at is not None
        
        # Verify subscription was created
        subscription = test_db.query(SubscriptionDB).filter(
            SubscriptionDB.user_id == user.id,
            SubscriptionDB.plan_id == "code_14d"
        ).first()
        assert subscription is not None
        assert subscription.status == "active"
        assert subscription.start_date is not None
        assert subscription.end_date is not None
    
    def test_callback_payment_failed(self, client, test_db):
        """Test failed payment callback"""
        # Create test transaction
        transaction = TransactionDB(
            plan_id="code_14d",
            amount=99,
            currency="ILS",
            status="pending"
        )
        test_db.add(transaction)
        test_db.commit()
        
        # Send callback
        response = client.post(
            "/api/payments/hyp/callback",
            json={
                "Order": transaction.id,
                "CCode": "1",
                "Id": "hyp-trans-123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        
        # Verify transaction was updated
        test_db.refresh(transaction)
        assert transaction.status == "failed"


class TestSubscriptionExtension:
    """Test subscription extension logic"""
    
    def test_extension_extends_existing_subscription(self, client, test_db):
        """Test that extensions extend existing subscriptions"""
        # Create test user
        user = UserDB(**SAMPLE_USER)
        test_db.add(user)
        test_db.commit()
        
        # Create existing subscription
        end_date = datetime.utcnow() + timedelta(days=14)
        existing_sub = SubscriptionDB(
            user_id=user.id,
            plan_id="code_14d",
            start_date=datetime.utcnow(),
            end_date=end_date,
            status="active"
        )
        test_db.add(existing_sub)
        test_db.commit()
        
        # Create extension transaction
        transaction = TransactionDB(
            user_id=user.id,
            plan_id="code_ext",
            amount=59,
            currency="ILS",
            status="pending"
        )
        test_db.add(transaction)
        test_db.commit()
        
        # Send callback for extension
        response = client.post(
            "/api/payments/hyp/callback",
            json={
                "Order": transaction.id,
                "CCode": "0",
                "Id": "hyp-trans-ext-123"
            }
        )
        
        assert response.status_code == 200
        
        # Verify subscription was extended
        test_db.refresh(existing_sub)
        # End date should be extended by 7 days
        assert existing_sub.end_date > end_date


class TestGetTransaction:
    """Test getting transaction details"""
    
    def test_get_transaction_not_found(self, client, test_db):
        """Test getting non-existent transaction"""
        response = client.get("/api/payments/hyp/transaction/non-existent")
        assert response.status_code == 404
    
    def test_get_transaction_success(self, client, test_db):
        """Test getting transaction details"""
        # Create test transaction
        transaction = TransactionDB(
            plan_id="code_14d",
            amount=99,
            currency="ILS",
            status="completed"
        )
        test_db.add(transaction)
        test_db.commit()
        
        # Get transaction
        response = client.get(f"/api/payments/hyp/transaction/{transaction.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == transaction.id
        assert data["plan_id"] == "code_14d"
        assert data["amount"] == 99
        assert data["status"] == "completed"
    
    def test_get_transaction_with_subscription(self, client, test_db):
        """Test getting transaction details with subscription information"""
        # Create test user
        user = UserDB(**SAMPLE_USER)
        test_db.add(user)
        test_db.commit()
        
        # Create test transaction
        transaction = TransactionDB(
            user_id=user.id,
            plan_id="code_14d",
            amount=99,
            currency="ILS",
            status="completed",
            completed_at=datetime.utcnow()
        )
        test_db.add(transaction)
        test_db.commit()
        
        # Create associated subscription
        subscription = SubscriptionDB(
            user_id=user.id,
            plan_id="code_14d",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=14),
            status="active",
            transaction_id=transaction.id
        )
        test_db.add(subscription)
        test_db.commit()
        
        # Get transaction
        response = client.get(f"/api/payments/hyp/transaction/{transaction.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == transaction.id
        assert data["status"] == "completed"
        
        # Verify subscription details are included
        assert "subscription" in data
        sub_data = data["subscription"]
        assert sub_data["id"] == subscription.id
        assert sub_data["plan_id"] == "code_14d"
        assert "plan_name" in sub_data
        assert sub_data["status"] == "active"
        assert "start_date" in sub_data
        assert "end_date" in sub_data
        # Verify dates are in ISO format
        assert "T" in sub_data["start_date"]
        assert "T" in sub_data["end_date"]


class TestCallbackGetMethod:
    """Test HYP callback via GET method"""
    
    def test_callback_get_method(self, client, test_db):
        """Test callback via GET with query parameters"""
        # Create test user
        user = UserDB(**SAMPLE_USER)
        test_db.add(user)
        test_db.commit()
        
        # Create test transaction
        transaction = TransactionDB(
            user_id=user.id,
            plan_id="code_14d",
            amount=99,
            currency="ILS",
            status="pending"
        )
        test_db.add(transaction)
        test_db.commit()
        
        # Send callback via GET with query parameters
        response = client.get(
            f"/api/payments/hyp/callback?Order={transaction.id}&CCode=0&Id=hyp-trans-456&Amount=9900"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify transaction was updated
        test_db.refresh(transaction)
        assert transaction.status == "completed"
        assert transaction.hyp_transaction_id == "hyp-trans-456"
    
    def test_result_endpoint(self, client, test_db):
        """Test alternative result endpoint"""
        # Create test user
        user = UserDB(**SAMPLE_USER)
        test_db.add(user)
        test_db.commit()
        
        # Create test transaction
        transaction = TransactionDB(
            user_id=user.id,
            plan_id="code_14d",
            amount=99,
            currency="ILS",
            status="pending"
        )
        test_db.add(transaction)
        test_db.commit()
        
        # Send result via GET
        response = client.get(
            f"/api/payments/hyp/result?Order={transaction.id}&CCode=0&Id=hyp-trans-789&Amount=9900"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify transaction was updated
        test_db.refresh(transaction)
        assert transaction.status == "completed"


class TestGetUserSubscriptions:
    """Test getting user subscriptions"""
    
    def test_get_user_subscriptions(self, client, test_db):
        """Test getting all subscriptions for a user"""
        # Create test user
        user = UserDB(**SAMPLE_USER)
        test_db.add(user)
        test_db.commit()
        
        # Create subscriptions
        sub1 = SubscriptionDB(
            user_id=user.id,
            plan_id="code_14d",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=14),
            status="active"
        )
        sub2 = SubscriptionDB(
            user_id=user.id,
            plan_id="video_1m",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),
            status="active"
        )
        test_db.add(sub1)
        test_db.add(sub2)
        test_db.commit()
        
        # Get subscriptions
        response = client.get(f"/api/payments/hyp/subscriptions/{user.id}")
        assert response.status_code == 200
        data = response.json()
        assert "subscriptions" in data
        assert data["count"] == 2
        assert len(data["subscriptions"]) == 2


class TestAccountRequiredBeforePayment:
    """Un paiement ne peut pas partir sans compte : c'est ce qui garantit que
    l'abonnement encaissé pourra effectivement être ouvert."""

    def test_create_payment_without_account_is_refused(self, client, test_db):
        response = client.post(
            "/api/payments/hyp/create-payment",
            json={"plan_id": "code_14d", "user_email": "sarah@example.com"},
        )
        assert response.status_code == 401
        assert "compte" in response.json()["detail"].lower()

        # Aucun paiement ne doit avoir été amorcé.
        assert test_db.query(TransactionDB).count() == 0

    @patch('routes.hyp_payments.create_hyp_payment_url')
    def test_authenticated_user_wins_over_client_payload(self, mock_create_url, client, test_db):
        """Le compte crédité est celui du token, jamais le user_id envoyé par le client."""
        mock_create_url.return_value = "https://icom.yaad.net/p/?test=true"

        register = client.post(
            "/api/auth/register",
            json={"email": "sarah@example.com", "password": "motdepasse", "first_name": "Sarah"},
        )
        assert register.status_code == 200
        token = register.json()["access_token"]

        other = UserDB(id="autre-eleve", email="autre@example.com", hashed_password="x")
        test_db.add(other)
        test_db.commit()

        response = client.post(
            "/api/payments/hyp/create-payment",
            json={"plan_id": "code_14d", "user_id": other.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        transaction = test_db.query(TransactionDB).filter(
            TransactionDB.id == response.json()["transaction_id"]
        ).first()
        assert transaction.user_id != other.id
        assert transaction.event_data["user_email"] == "sarah@example.com"


class TestClaimPayment:
    """Rattachement d'un paiement encaissé sans compte (parcours de rattrapage)."""

    def _orphan_transaction(self, client, test_db, email="sarah@example.com"):
        transaction = TransactionDB(
            plan_id="code_14d",
            amount=99,
            currency="ILS",
            status="pending",
            event_data={"user_email": email},
        )
        test_db.add(transaction)
        test_db.commit()

        response = client.post(
            "/api/payments/hyp/callback",
            json={"Order": transaction.id, "CCode": "0", "Id": "hyp-orphan-1"},
        )
        assert response.status_code == 200
        test_db.refresh(transaction)
        return transaction

    def test_payment_without_account_is_flagged(self, client, test_db):
        transaction = self._orphan_transaction(client, test_db)

        assert transaction.status == "completed"
        assert transaction.event_data["needs_account"] is True
        assert test_db.query(SubscriptionDB).count() == 0

        details = client.get(f"/api/payments/hyp/transaction/{transaction.id}").json()
        assert details["needs_account"] is True
        # L'email n'est renvoyé que masqué.
        assert details["email_hint"].endswith("@example.com")
        assert "sarah@example.com" not in details["email_hint"]

    def test_claim_creates_account_and_opens_subscription(self, client, test_db):
        transaction = self._orphan_transaction(client, test_db)

        response = client.post(
            "/api/payments/hyp/claim",
            json={
                "transaction_id": transaction.id,
                "email": "Sarah@Example.com ",
                "password": "motdepasse",
                "first_name": "Sarah",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["subscription"]["status"] == "active"

        # L'élève est connecté immédiatement, sans avoir à deviner d'identifiants.
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
        assert me.status_code == 200
        assert me.json()["email"] == "sarah@example.com"

        test_db.refresh(transaction)
        assert transaction.user_id == data["user"]["id"]
        subscription = test_db.query(SubscriptionDB).filter(
            SubscriptionDB.user_id == data["user"]["id"]
        ).first()
        assert subscription.status == "active"
        assert subscription.transaction_id == transaction.id

        # Le mot de passe choisi permet bien de se reconnecter ensuite.
        login = client.post(
            "/api/auth/login",
            data={"username": "sarah@example.com", "password": "motdepasse"},
        )
        assert login.status_code == 200

    def test_claim_is_single_use(self, client, test_db):
        transaction = self._orphan_transaction(client, test_db)
        payload = {
            "transaction_id": transaction.id,
            "email": "sarah@example.com",
            "password": "motdepasse",
        }
        assert client.post("/api/payments/hyp/claim", json=payload).status_code == 200

        second = client.post(
            "/api/payments/hyp/claim",
            json={**payload, "email": "voleur@example.com", "password": "autremotdepasse"},
        )
        assert second.status_code == 409

    def test_claim_on_existing_account_requires_its_password(self, client, test_db):
        client.post(
            "/api/auth/register",
            json={"email": "sarah@example.com", "password": "motdepasse"},
        )
        transaction = self._orphan_transaction(client, test_db)

        refused = client.post(
            "/api/payments/hyp/claim",
            json={
                "transaction_id": transaction.id,
                "email": "sarah@example.com",
                "password": "mauvais-mot-de-passe",
            },
        )
        assert refused.status_code == 403
        assert test_db.query(SubscriptionDB).count() == 0

        accepted = client.post(
            "/api/payments/hyp/claim",
            json={
                "transaction_id": transaction.id,
                "email": "sarah@example.com",
                "password": "motdepasse",
            },
        )
        assert accepted.status_code == 200
        assert accepted.json()["subscription"]["status"] == "active"

    def test_claim_refuses_unconfirmed_payment(self, client, test_db):
        transaction = TransactionDB(plan_id="code_14d", amount=99, currency="ILS", status="pending")
        test_db.add(transaction)
        test_db.commit()

        response = client.post(
            "/api/payments/hyp/claim",
            json={
                "transaction_id": transaction.id,
                "email": "sarah@example.com",
                "password": "motdepasse",
            },
        )
        assert response.status_code == 409
        assert test_db.query(SubscriptionDB).count() == 0

    def test_claim_refuses_short_password(self, client, test_db):
        transaction = self._orphan_transaction(client, test_db)

        response = client.post(
            "/api/payments/hyp/claim",
            json={
                "transaction_id": transaction.id,
                "email": "sarah@example.com",
                "password": "123",
            },
        )
        assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
