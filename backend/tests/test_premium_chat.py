"""
Le chat « prof 24h/24 » est réservé au Premium, et seuls les vrais paiements
sont facturés.

1. Un élève Standard garde ses leçons mais pas le chat : 403 explicite, que le
   front transforme en invitation à passer au Premium.
2. Un élève Premium (et les anciennes formules avec coaching) y a accès.
3. /api/subscriptions/me indique au front si le chat est inclus.
4. L'ancien webhook Verifone, non signé, n'enregistre plus rien.
5. Une transaction sans formule n'est jamais facturée.
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

import app_settings  # noqa: E402
import invoicing  # noqa: E402
from server import app  # noqa: E402
from database import Base, get_db  # noqa: E402
from models import AppSettingDB, InvoiceDB, SubscriptionDB, TransactionDB, UserDB, User  # noqa: E402
from auth import get_current_user  # noqa: E402
import routes.ai_coach as ai_coach  # noqa: E402

engine = create_engine("sqlite:///./test_premium_chat.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
client = TestClient(app)
STUDENT = User(id="u1", email="eleve@test.fr")


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@test.fr")
    monkeypatch.setattr(ai_coach, "call_chat", lambda **kw: "Réponse du prof")
    monkeypatch.setattr(ai_coach, "ai_configured", lambda: True)
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: STUDENT
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.add(UserDB(id="u1", email="eleve@test.fr", hashed_password="x"))
    session.commit()
    app_settings.invalidate_cache()
    try:
        yield session
    finally:
        session.close()
        app_settings.invalidate_cache()
        app.dependency_overrides = previous


def _subscribe(db, plan_id):
    now = datetime.utcnow()
    db.add(SubscriptionDB(user_id="u1", plan_id=plan_id, status="active",
                          start_date=now, end_date=now + timedelta(days=14)))
    db.commit()


def _chat():
    return client.post("/api/ai-coach/chat",
                       json={"messages": [{"role": "user", "content": "Mon cas perso : je dois tourner ?"}]})


def test_standard_student_is_invited_to_upgrade(db):
    _subscribe(db, "basic_14d")
    response = _chat()
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "premium_required"
    me = client.get("/api/subscriptions/me").json()
    assert me["has_access"] is True and me["premium"] is False


@pytest.mark.parametrize("plan_id", ["premium_14d", "premium_30d", "code_30d", "video_1m"])
def test_premium_and_legacy_coaching_plans_keep_the_chat(db, plan_id):
    _subscribe(db, plan_id)
    response = _chat()
    assert response.status_code == 200
    assert response.json()["reply"] == "Réponse du prof"
    assert client.get("/api/subscriptions/me").json()["premium"] is True


def test_no_subscription_still_goes_to_the_paywall(db):
    assert _chat().status_code == 402


def test_expired_premium_loses_the_chat(db):
    now = datetime.utcnow()
    db.add(SubscriptionDB(user_id="u1", plan_id="premium_30d", status="active",
                          start_date=now - timedelta(days=40), end_date=now - timedelta(days=10)))
    db.commit()
    assert _chat().status_code == 402


def test_standard_lessons_are_still_included(db):
    """Les leçons sur les erreurs font partie de la formule Standard."""
    _subscribe(db, "basic_14d")
    response = client.post("/api/ai-coach/lesson/peek",
                           json={"question_id": "q-inconnue", "selected_option_id": "o1"})
    assert response.status_code not in (402, 403)


def test_verifone_webhook_records_nothing(db):
    response = client.post("/api/payments/verifone/webhook",
                           json={"order_id": "fake", "status": "completed", "amount": "999"})
    assert response.status_code == 410
    assert db.query(TransactionDB).count() == 0


def test_transaction_without_plan_is_never_invoiced(db):
    db.add(AppSettingDB(key="INVOICE_COMPANY_NAME", value="Flash Neiga Ltd"))
    db.add(AppSettingDB(key="INVOICE_COMPANY_LEGAL_ID", value="515123456"))
    db.add(TransactionDB(id="fake", amount=999.0, currency="ILS", status="completed",
                         completed_at=datetime.utcnow()))
    db.add(TransactionDB(id="real", user_id="u1", plan_id="basic_14d", amount=69.0,
                         currency="ILS", status="completed", completed_at=datetime.utcnow()))
    db.commit()
    app_settings.invalidate_cache()
    result = invoicing.generate_missing_invoices(db)
    assert result["factures_creees"] == 1
    assert [i.transaction_id for i in db.query(InvoiceDB).all()] == ["real"]
