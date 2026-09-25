"""
Renouvellement automatique des abonnements, comme sur toute plateforme :
prélevé à chaque fin de période (14, 21 ou 30 jours) jusqu'à la résiliation.

Ce qui est vérifié :
1. Le premier paiement, fait après avoir vu les conditions, active le
   renouvellement et enregistre la carte (token HYP). Un paiement ancien,
   sans ce consentement, n'est jamais prélevé.
2. À l'échéance : un prélèvement au prix plein de la formule, l'accès
   prolongé d'une période à partir de la fin de la précédente, une facture.
3. Rien avant l'échéance ; rien après résiliation ; réactivation possible.
4. Carte refusée : nouvelle tentative le lendemain, arrêt après trois.
5. Pas de réponse de HYP : aucune nouvelle tentative (jamais de double
   prélèvement) tant qu'un administrateur n'a pas tranché.
6. Deux processus simultanés ne prélèvent qu'une fois.
7. En changeant de formule, l'ancienne n'est plus prélevée.
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
import renewals  # noqa: E402
from server import app  # noqa: E402
from database import Base, get_db  # noqa: E402
from models import AppSettingDB, InvoiceDB, SubscriptionDB, TransactionDB, UserDB, User  # noqa: E402
from auth import get_current_user, get_current_user_optional, require_admin  # noqa: E402
import routes.hyp_payments as hyp  # noqa: E402

engine = create_engine("sqlite:///./test_auto_renewal.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
client = TestClient(app)
STUDENT = User(id="u1", email="sarah@test.fr")


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class FakeHyp:
    """Terminal HYP simulé : enregistre les prélèvements demandés."""

    def __init__(self):
        self.charges = []
        self.next_result = {"CCode": "0"}
        self.token_result = {"CCode": "0", "Token": "1234567890123454321", "Tokef": "2912"}
        self.fail_network = False

    def get_token(self, trans_id):
        return dict(self.token_result, Id=trans_id)

    def charge(self, **kwargs):
        self.charges.append(kwargs)
        if self.fail_network:
            raise hyp.HypRequestError("timeout")
        return dict(self.next_result, Id=f"hyp-r{len(self.charges)}")


@pytest.fixture
def fake_hyp(monkeypatch):
    fake = FakeHyp()
    monkeypatch.setattr(hyp, "hyp_get_token", fake.get_token)
    monkeypatch.setattr(hyp, "hyp_charge_token", fake.charge)
    monkeypatch.setattr(hyp, "HYP_PASSP", "passp")
    monkeypatch.setattr(hyp, "HYP_REQUIRE_SIGNATURE", False)
    return fake


@pytest.fixture
def db(monkeypatch, fake_hyp):
    for key in app_settings.ALLOWED_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: STUDENT
    app.dependency_overrides[get_current_user_optional] = lambda: STUDENT
    app.dependency_overrides[require_admin] = lambda: STUDENT
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.add(UserDB(id="u1", email="sarah@test.fr", hashed_password="x", first_name="Sarah"))
    session.add(AppSettingDB(key="INVOICE_COMPANY_NAME", value="Flash Neiga Ltd"))
    session.add(AppSettingDB(key="INVOICE_COMPANY_LEGAL_ID", value="515123456"))
    session.commit()
    app_settings.invalidate_cache()
    try:
        yield session
    finally:
        session.close()
        app_settings.invalidate_cache()
        app.dependency_overrides = previous


def _buy(db, plan_id="basic_14d", amount=69.0, consent=True, hyp_id="hyp-1"):
    """Premier paiement par le tunnel, confirmé par HYP."""
    event_data = {"user_email": "sarah@test.fr"}
    if consent:
        event_data["auto_renew"] = True
    tx = TransactionDB(user_id="u1", plan_id=plan_id, amount=amount, currency="ILS",
                       status="pending", event_data=event_data)
    db.add(tx)
    db.commit()
    response = client.post("/api/payments/hyp/callback", json={
        "Order": tx.id, "CCode": "0", "Id": hyp_id, "L4digit": "4321",
        "Tmonth": "12", "Tyear": "2029", "UserId": "000000000",
    })
    assert response.status_code == 200
    db.expire_all()
    return tx, db.query(SubscriptionDB).filter(SubscriptionDB.transaction_id == tx.id).one()


def _at(sub, delta=timedelta(minutes=1)):
    """L'instant où l'échéance de `sub` est atteinte."""
    return sub.next_renewal + delta


# ===== 1. Mise en place =====
def test_first_payment_enables_renewal_and_saves_card(db, fake_hyp):
    _, sub = _buy(db)
    assert sub.auto_renew is True
    assert sub.next_renewal == sub.end_date
    assert sub.hyp_token == "1234567890123454321"
    assert sub.hyp_token_expiry == "2912"
    assert sub.card_last4 == "4321"


def test_old_payment_without_consent_is_never_charged(db, fake_hyp):
    _, sub = _buy(db, consent=False)
    assert not sub.auto_renew
    renewals.run_due_renewals(db, now=sub.end_date + timedelta(days=1))
    assert fake_hyp.charges == []


def test_checkout_records_consent_and_announces_it_to_hyp(db, monkeypatch):
    seen = {}

    def fake_url(**kwargs):
        seen.update(kwargs)
        return "https://pay.test/?x"

    monkeypatch.setattr(hyp, "create_hyp_payment_url", fake_url)
    response = client.post("/api/payments/hyp/create-payment", json={"plan_id": "premium_21d"})
    assert response.status_code == 200
    tx = db.query(TransactionDB).one()
    assert tx.event_data["auto_renew"] is True
    assert "tous les 21 jours" in seen["info"]


# ===== 2. Échéance =====
def test_due_subscription_is_charged_and_extended(db, fake_hyp):
    _, sub = _buy(db, plan_id="basic_14d")
    end_before = sub.end_date

    result = renewals.run_due_renewals(db, now=_at(sub))
    assert result == {"renewed": 1}

    assert len(fake_hyp.charges) == 1
    charge = fake_hyp.charges[0]
    assert charge["amount"] == 69.0 and charge["token"] == "1234567890123454321"
    assert charge["expiry"] == "2912"

    db.refresh(sub)
    assert sub.end_date == end_before + timedelta(days=14)
    assert sub.next_renewal == sub.end_date
    renewal = db.query(TransactionDB).filter(TransactionDB.event_type == "payment.renewal").one()
    assert renewal.status == "completed" and renewal.hyp_transaction_id == "hyp-r1"

    invoice = db.query(InvoiceDB).filter(InvoiceDB.transaction_id == renewal.id).one()
    assert invoice.service_start == end_before
    assert invoice.service_end == end_before + timedelta(days=14)


def test_renews_every_period_until_cancelled(db, fake_hyp):
    _, sub = _buy(db, plan_id="basic_21d", amount=89.0)
    for _ in range(3):
        renewals.run_due_renewals(db, now=_at(sub))
        db.refresh(sub)
    assert len(fake_hyp.charges) == 3
    assert db.query(InvoiceDB).count() == 4  # premier paiement + 3 renouvellements

    assert client.post("/api/profile/subscription/cancel").status_code == 200
    db.refresh(sub)
    renewals.run_due_renewals(db, now=sub.end_date + timedelta(days=30))
    assert len(fake_hyp.charges) == 3


def test_promo_applies_to_first_payment_only(db, fake_hyp):
    _, sub = _buy(db, plan_id="premium_30d", amount=99.0)  # 149 remisé
    renewals.run_due_renewals(db, now=_at(sub))
    assert fake_hyp.charges[0]["amount"] == 149.0


def test_nothing_is_charged_before_due_date(db, fake_hyp):
    _, sub = _buy(db)
    renewals.run_due_renewals(db, now=sub.end_date - timedelta(days=1))
    assert fake_hyp.charges == []


def test_charged_a_little_early_so_access_never_stops(db, fake_hyp):
    _, sub = _buy(db)
    end_before = sub.end_date
    renewals.run_due_renewals(db, now=end_before - timedelta(hours=1))
    db.refresh(sub)
    assert len(fake_hyp.charges) == 1
    assert sub.end_date == end_before + timedelta(days=14)  # pas un jour de perdu


# ===== 3. Résiliation =====
def test_cancel_then_resume(db, fake_hyp):
    _, sub = _buy(db)
    client.post("/api/profile/subscription/cancel")
    db.refresh(sub)
    assert sub.status == "cancelled" and not sub.auto_renew
    profile = client.get("/api/profile").json()
    assert profile["subscription"]["auto_renew"] is False
    assert profile["subscription"]["can_resume"] is True

    assert client.post("/api/profile/subscription/resume").status_code == 200
    db.refresh(sub)
    assert sub.status == "active" and sub.auto_renew and sub.next_renewal == sub.end_date
    renewals.run_due_renewals(db, now=_at(sub))
    assert len(fake_hyp.charges) == 1


def test_profile_shows_next_renewal(db, fake_hyp):
    _, sub = _buy(db)
    data = client.get("/api/profile").json()["subscription"]
    assert data["auto_renew"] is True
    assert data["next_renewal"] is not None
    assert data["card_last4"] == "4321"


# ===== 4. Carte refusée =====
def test_declined_card_retries_then_stops(db, fake_hyp):
    _, sub = _buy(db)
    end_before = sub.end_date
    fake_hyp.next_result = {"CCode": "6"}
    now = _at(sub)
    outcomes = []
    for _ in range(3):
        outcomes.append(renewals.renew_subscription(db, sub, now=now))
        db.refresh(sub)
        if sub.next_renewal:
            now = sub.next_renewal + timedelta(minutes=1)
    assert outcomes == ["declined", "declined", "stopped"]
    assert not sub.auto_renew and sub.next_renewal is None
    assert sub.end_date == end_before  # aucun jour offert sans paiement
    assert db.query(InvoiceDB).count() == 1
    assert db.query(TransactionDB).filter(TransactionDB.status == "failed").count() == 3


def test_declined_then_accepted_resets_failures(db, fake_hyp):
    _, sub = _buy(db)
    fake_hyp.next_result = {"CCode": "6"}
    renewals.renew_subscription(db, sub, now=_at(sub))
    db.refresh(sub)
    fake_hyp.next_result = {"CCode": "0"}
    retry_at = _at(sub)
    assert renewals.renew_subscription(db, sub, now=retry_at) == "renewed"
    db.refresh(sub)
    assert sub.renewal_failures == 0
    # L'accès repart du jour du paiement réussi, pas de la date déjà passée.
    assert sub.end_date == retry_at + timedelta(days=14)


def test_card_token_refused_by_terminal_is_a_decline(db, fake_hyp):
    fake_hyp.token_result = {"CCode": "901"}  # terminal sans tokenisation
    _, sub = _buy(db)
    assert sub.hyp_token is None and "901" in sub.renewal_error
    assert renewals.renew_subscription(db, sub, now=_at(sub)) == "declined"
    assert fake_hyp.charges == []


# ===== 5. Pas de réponse de HYP =====
def test_unknown_outcome_is_never_retried_automatically(db, fake_hyp):
    _, sub = _buy(db)
    fake_hyp.fail_network = True
    assert renewals.renew_subscription(db, sub, now=_at(sub)) == "review"
    fake_hyp.fail_network = False
    for hours in (1, 2, 24):
        renewals.run_due_renewals(db, now=_at(sub) + timedelta(hours=hours))
    assert len(fake_hyp.charges) == 1  # jamais de second prélèvement

    detail = client.get("/api/admin/crm/users/u1").json()
    assert len(detail["pending_renewals"]) == 1


def test_admin_confirms_charge_after_checking_hyp(db, fake_hyp):
    _, sub = _buy(db)
    end_before = sub.end_date
    fake_hyp.fail_network = True
    renewals.renew_subscription(db, sub, now=_at(sub))
    attempt = renewals.pending_attempts(db)[0]

    response = client.post(f"/api/admin/crm/renewals/{attempt.id}/resolve",
                           json={"charged": True, "hyp_transaction_id": "hyp-verif"})
    assert response.status_code == 200
    db.refresh(sub)
    assert sub.end_date == end_before + timedelta(days=14)
    assert db.query(InvoiceDB).filter(InvoiceDB.transaction_id == attempt.id).count() == 1

    fake_hyp.fail_network = False
    renewals.run_due_renewals(db, now=_at(sub))
    assert len(fake_hyp.charges) == 2  # le cycle reprend normalement


def test_admin_declares_not_charged(db, fake_hyp):
    _, sub = _buy(db)
    fake_hyp.fail_network = True
    renewals.renew_subscription(db, sub, now=_at(sub))
    attempt = renewals.pending_attempts(db)[0]
    client.post(f"/api/admin/crm/renewals/{attempt.id}/resolve", json={"charged": False})
    fake_hyp.fail_network = False
    db.refresh(sub)
    assert renewals.renew_subscription(db, sub, now=_at(sub)) == "renewed"


# ===== 6. Concurrence =====
def test_only_one_process_can_claim_a_renewal(db, fake_hyp):
    _, sub = _buy(db)
    now = _at(sub)
    assert renewals._claim(db, sub.id, now) is True
    other = TestingSessionLocal()
    try:
        assert renewals._claim(other, sub.id, now) is False
        assert renewals.renew_subscription(other, other.get(SubscriptionDB, sub.id), now=now) == "skipped"
    finally:
        other.close()
    assert fake_hyp.charges == []


# ===== 7. Changement de formule =====
def test_upgrade_stops_renewing_the_previous_plan(db, fake_hyp):
    _, basic = _buy(db, plan_id="basic_14d", hyp_id="hyp-1")
    _, premium = _buy(db, plan_id="premium_30d", amount=149.0, hyp_id="hyp-2")
    db.refresh(basic)
    assert not basic.auto_renew and premium.auto_renew
    renewals.run_due_renewals(db, now=premium.end_date + timedelta(minutes=1))
    assert [c["amount"] for c in fake_hyp.charges] == [149.0]
