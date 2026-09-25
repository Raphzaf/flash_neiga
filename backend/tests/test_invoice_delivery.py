"""
Remise des factures au client, à chaque paiement et à chaque renouvellement.

Ce qui est vérifié :

1. Un paiement HYP encaissé donne une facture, envoyée par e-mail au client
   avec le PDF joint — y compris quand l'identité de l'entreprise n'est
   connue qu'en base (saisie dans le CRM).
2. Un renouvellement (nouveau prélèvement HYP sur une commande déjà payée)
   crée son propre paiement, prolonge l'abonnement sans perdre de jours, et
   donne sa propre facture, elle aussi envoyée.
3. Une notification répétée ne crée ni second renouvellement ni seconde facture.
4. Un envoi raté est consigné sur la facture et rattrapé par le balayage.
5. L'élève retrouve ses factures dans son profil, et seulement les siennes.
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
import mailer  # noqa: E402
from server import app  # noqa: E402
from database import Base, get_db  # noqa: E402
from models import AppSettingDB, InvoiceDB, SubscriptionDB, TransactionDB, UserDB, User  # noqa: E402
from auth import get_current_user  # noqa: E402

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_invoice_delivery.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

client = TestClient(app)
SARAH = User(id="u1", email="sarah@test.fr")


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def outbox(monkeypatch):
    """Remplace le serveur SMTP : chaque envoi est consigné ici."""
    sent = []

    def fake_send(to, subject, text, html=None, attachments=(), timeout=20):
        sent.append({"to": to, "subject": subject, "text": text,
                     "attachments": list(attachments)})
        return "<test@flash-neiga>"

    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_FROM", "factures@flash-neiga.com")
    monkeypatch.setattr(mailer, "send", fake_send)
    return sent


@pytest.fixture
def db(monkeypatch):
    import routes.hyp_payments as hyp
    monkeypatch.setattr(hyp, "HYP_REQUIRE_SIGNATURE", False)
    for key in app_settings.ALLOWED_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key in ("SMTP_HOST", "SMTP_FROM", "SMTP_USER", "SMTP_BCC"):
        monkeypatch.delenv(key, raising=False)
    app_settings.invalidate_cache()

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: SARAH

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.add(UserDB(id="u1", email="sarah@test.fr", hashed_password="x",
                       first_name="Sarah", last_name="Cohen"))
    session.add(UserDB(id="u2", email="david@test.fr", hashed_password="x"))
    # Identité de l'entreprise saisie dans le CRM : en base, pas dans l'environnement.
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


def _pending(db, user_id="u1", plan_id="basic_30d", amount=99.0):
    tx = TransactionDB(user_id=user_id, plan_id=plan_id, amount=amount, currency="ILS",
                       status="pending", event_data={"user_email": "sarah@test.fr"})
    db.add(tx)
    db.commit()
    return tx


def _pay(tx_id, hyp_id, amount="99"):
    return client.post("/api/payments/hyp/callback",
                       json={"Order": tx_id, "CCode": "0", "Id": hyp_id, "Amount": amount})


def _age(db, tx, days):
    """Fait comme si le paiement initial datait de `days` jours."""
    past = datetime.utcnow() - timedelta(days=days)
    tx.completed_at = past
    sub = db.query(SubscriptionDB).filter(SubscriptionDB.transaction_id == tx.id).one()
    sub.start_date = past
    sub.end_date = past + timedelta(days=30)
    db.commit()
    return sub


# ===== 1. Paiement initial =====
def test_payment_issues_and_emails_invoice(db, outbox):
    tx = _pending(db)
    assert _pay(tx.id, "hyp-1").status_code == 200

    invoice = db.query(InvoiceDB).filter(InvoiceDB.transaction_id == tx.id).one()
    assert invoice.number.startswith("INV-")
    assert invoice.emailed_at is not None

    assert len(outbox) == 1
    mail = outbox[0]
    assert "sarah@test.fr" in mail["to"]
    assert invoice.number in mail["subject"]
    filename, content, mime = mail["attachments"][0]
    assert filename == f"{invoice.number}.pdf"
    assert mime == "application/pdf" and content.startswith(b"%PDF")


def test_invoice_issued_even_after_settings_cache_expired(db, outbox):
    """Régression : l'identité n'était lue que dans un cache de 30 s."""
    app_settings.invalidate_cache()
    tx = _pending(db)
    _pay(tx.id, "hyp-1")
    assert db.query(InvoiceDB).filter(InvoiceDB.transaction_id == tx.id).count() == 1


def test_without_smtp_invoice_is_issued_and_sent_later(db, monkeypatch):
    tx = _pending(db)
    _pay(tx.id, "hyp-1")
    invoice = db.query(InvoiceDB).filter(InvoiceDB.transaction_id == tx.id).one()
    assert invoice.emailed_at is None and invoice.email_error is None

    sent = []
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_FROM", "factures@flash-neiga.com")
    monkeypatch.setattr(mailer, "send", lambda **kw: sent.append(kw) or "<id>")
    result = invoicing.run_billing_sweep(db)
    assert result["envoyees"] == 1 and len(sent) == 1
    db.refresh(invoice)
    assert invoice.emailed_at is not None


def test_failed_send_is_recorded_then_retried(db, outbox, monkeypatch):
    def broken(**kwargs):
        raise OSError("connexion refusée")

    monkeypatch.setattr(mailer, "send", broken)
    tx = _pending(db)
    assert _pay(tx.id, "hyp-1").status_code == 200  # le paiement passe quand même
    invoice = db.query(InvoiceDB).filter(InvoiceDB.transaction_id == tx.id).one()
    assert invoice.emailed_at is None
    assert "connexion refusée" in invoice.email_error

    monkeypatch.setattr(mailer, "send", lambda **kw: outbox.append(kw) or "<id>")
    invoicing.send_pending_invoice_emails(db)
    db.refresh(invoice)
    assert invoice.emailed_at is not None and invoice.email_error is None


# ===== 2. Renouvellement =====
def test_renewal_creates_payment_extends_access_and_emails_invoice(db, outbox):
    tx = _pending(db)
    _pay(tx.id, "hyp-1")
    sub = _age(db, tx, days=29)
    end_before = sub.end_date

    response = _pay(tx.id, "hyp-2")
    assert response.status_code == 200
    assert response.json()["message"] == "Renewal recorded"

    renewal = db.query(TransactionDB).filter(TransactionDB.hyp_transaction_id == "hyp-2").one()
    assert renewal.id != tx.id
    assert renewal.status == "completed" and renewal.user_id == "u1"
    assert renewal.event_data["renewal_of"] == tx.id

    db.refresh(sub)
    # Aucun jour perdu : la nouvelle période part de la fin de la précédente.
    assert sub.end_date == end_before + timedelta(days=30)
    assert sub.status == "active"

    invoices = db.query(InvoiceDB).order_by(InvoiceDB.sequence).all()
    assert [i.transaction_id for i in invoices] == [tx.id, renewal.id]
    renewal_invoice = invoices[1]
    assert renewal_invoice.service_start == end_before
    assert renewal_invoice.service_end == end_before + timedelta(days=30)
    assert renewal_invoice.emailed_at is not None
    assert len(outbox) == 2 and renewal_invoice.number in outbox[1]["subject"]


def test_renewal_uses_amount_actually_charged(db, outbox):
    tx = _pending(db, amount=79.0)  # premier mois remisé par un code promo
    _pay(tx.id, "hyp-1", amount="79")
    _age(db, tx, days=30)
    _pay(tx.id, "hyp-2", amount="99")
    renewal = db.query(TransactionDB).filter(TransactionDB.hyp_transaction_id == "hyp-2").one()
    assert renewal.amount == 99.0


def test_repeated_renewal_notification_is_recorded_once(db, outbox):
    tx = _pending(db)
    _pay(tx.id, "hyp-1")
    _age(db, tx, days=30)
    for _ in range(3):
        assert _pay(tx.id, "hyp-2").status_code == 200
    assert db.query(TransactionDB).filter(TransactionDB.hyp_transaction_id == "hyp-2").count() == 1
    assert db.query(InvoiceDB).count() == 2


def test_replayed_initial_notification_is_not_a_renewal(db, outbox):
    tx = _pending(db)
    _pay(tx.id, "hyp-1")
    _age(db, tx, days=30)
    _pay(tx.id, "hyp-1")
    assert db.query(TransactionDB).count() == 1
    assert db.query(InvoiceDB).count() == 1


def test_new_id_right_after_payment_is_not_a_renewal(db, outbox):
    """Deux identifiants pour le même paiement, à quelques minutes d'écart :
    un doublon de notification, pas un mois de plus."""
    tx = _pending(db)
    _pay(tx.id, "hyp-1")
    _pay(tx.id, "hyp-1b")
    assert db.query(TransactionDB).count() == 1
    assert db.query(InvoiceDB).count() == 1


def test_declined_renewal_changes_nothing(db, outbox):
    tx = _pending(db)
    _pay(tx.id, "hyp-1")
    _age(db, tx, days=30)
    client.post("/api/payments/hyp/callback",
                json={"Order": tx.id, "CCode": "6", "Id": "hyp-2"})
    assert db.query(TransactionDB).count() == 1
    db.refresh(tx)
    assert tx.status == "completed"


def test_renewal_reactivates_cancelled_subscription(db, outbox):
    """Résilié mais tout de même prélevé : la période payée est due."""
    tx = _pending(db)
    _pay(tx.id, "hyp-1")
    sub = _age(db, tx, days=30)
    sub.status = "cancelled"
    db.commit()
    _pay(tx.id, "hyp-2")
    db.refresh(sub)
    assert sub.status == "active" and sub.end_date > datetime.utcnow()


# ===== 3. Espace élève =====
def test_student_lists_and_downloads_own_invoices(db, outbox):
    tx = _pending(db)
    _pay(tx.id, "hyp-1")
    data = client.get("/api/profile/invoices").json()
    assert data["count"] == 1
    item = data["items"][0]
    assert item["number"].startswith("INV-") and item["emailed_at"]

    pdf = client.get(item["pdf_url"])
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert item["number"] in pdf.headers["content-disposition"]


def test_student_cannot_download_someone_elses_invoice(db, outbox):
    tx = _pending(db, user_id="u2")
    tx.event_data = {"user_email": "david@test.fr"}
    db.commit()
    _pay(tx.id, "hyp-9")
    other = db.query(InvoiceDB).filter(InvoiceDB.user_id == "u2").one()
    assert client.get(f"/api/profile/invoices/{other.id}.pdf").status_code == 404
    assert client.get("/api/profile/invoices").json()["count"] == 0


def test_email_content_is_in_french_with_amount_and_period(db):
    tx = _pending(db)
    _pay(tx.id, "hyp-1")
    invoice = db.query(InvoiceDB).one()
    subject, text, html = invoicing._invoice_email_content(invoice)
    assert subject.startswith(f"Facture {invoice.number}")
    assert "Bonjour Sarah Cohen" in text
    assert "99,00 ILS" in text
    assert "Période couverte" in text
