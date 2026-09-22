"""
Tests de la facture par client, telle qu'elle est attendue depuis le CRM.

Ce que l'exploitant demande, et donc ce qui est vérifié ici :

1. Ouvrir la fiche d'un client suffit à ce que ses paiements encaissés soient
   facturés — aucun traitement à lancer à la main.
2. Rouvrir la fiche ne crée pas de doublon (une transaction = une facture).
3. Chaque facture est récupérable en PDF, en HTML et en image (JPG / PNG).
4. L'identité de l'entreprise se renseigne depuis l'espace administrateur, et
   c'est cette saisie — pas une variable du serveur — qui débloque l'émission.
5. Une facturation non configurée n'empêche jamais la fiche de s'ouvrir.
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
from auth import get_current_user, require_admin  # noqa: E402

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_client_invoices.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ADMIN = User(id="admin-1", email="admin@test.fr")
client = TestClient(app)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_admin():
    return ADMIN


def _clear_invoice_env(monkeypatch):
    """Part d'un serveur sans identité d'entreprise dans l'environnement.

    C'est l'état réel de la production : si un test héritait d'une variable, il
    ne prouverait plus que la saisie depuis l'admin suffit.
    """
    for key in app_settings.ALLOWED_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(scope="function")
def db(monkeypatch):
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_admin
    app.dependency_overrides[require_admin] = override_admin

    _clear_invoice_env(monkeypatch)
    # Le magasin de réglages garde 30 s en mémoire : sans purge, un test verrait
    # les réglages du précédent.
    app_settings.invalidate_cache()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    session.add(UserDB(id="u1", email="sarah@test.fr", hashed_password="x",
                       first_name="Sarah", last_name="Cohen"))
    # Paiement encaissé, non facturé : exactement la situation trouvée en
    # production (des recettes, zéro facture).
    paid_at = datetime(2026, 3, 10, 9, 30)
    session.add(TransactionDB(
        id="tx-1", user_id="u1", plan_id="basic_14d", amount=69.0, currency="ILS",
        status="completed", created_at=paid_at, completed_at=paid_at,
    ))
    session.add(SubscriptionDB(
        id="sub-1", user_id="u1", plan_id="basic_14d", transaction_id="tx-1",
        status="active", start_date=paid_at, end_date=paid_at + timedelta(days=14),
    ))
    session.commit()

    try:
        yield session
    finally:
        session.close()
        app_settings.invalidate_cache()
        app.dependency_overrides = previous


def _configure_issuer():
    """Renseigne l'identité de l'entreprise comme le ferait l'administrateur."""
    response = client.put("/api/admin/invoices/config", json={
        "company_name": "Flash Neiga Ltd",
        "company_legal_id": "515123456",
        "company_city": "Tel Aviv",
        "vat_rate": 18,
        "prices_include_vat": True,
    })
    assert response.status_code == 200, response.text
    return response.json()


# ===== Configuration depuis l'espace administrateur =====
def test_issuer_identity_is_configurable_without_redeploy(db):
    """Sans identité renseignée, rien ne s'émet ; après saisie, tout s'émet.

    C'est le blocage constaté en production : l'identité n'existait que dans les
    variables du serveur, et tant que personne ne les renseignait, aucune
    facture n'était produite pour des paiements bien encaissés.
    """
    before = client.get("/api/admin/invoices/config")
    assert before.status_code == 200
    assert before.json()["configured"] is False

    after = _configure_issuer()
    assert after["configured"] is True
    assert after["issuer"]["name"] == "Flash Neiga Ltd"
    assert after["issuer"]["legal_id"] == "515123456"
    assert after["vat_rate"] == 18
    # La valeur vient bien de la base, pas de l'environnement.
    assert after["sources"]["INVOICE_COMPANY_NAME"] == "base"

    stored = db.query(AppSettingDB).filter(AppSettingDB.key == "INVOICE_COMPANY_NAME").first()
    assert stored is not None and stored.value == "Flash Neiga Ltd"
    assert stored.updated_by == ADMIN.email


def test_partial_config_update_keeps_other_fields(db):
    """Corriger un seul champ ne doit pas effacer les autres."""
    _configure_issuer()
    response = client.put("/api/admin/invoices/config", json={"company_phone": "+972 50 000 0000"})
    assert response.status_code == 200
    issuer = response.json()["issuer"]
    assert issuer["phone"] == "+972 50 000 0000"
    assert issuer["name"] == "Flash Neiga Ltd"       # préservé
    assert issuer["legal_id"] == "515123456"          # préservé


def test_config_rejects_out_of_range_vat_rate(db):
    response = client.put("/api/admin/invoices/config", json={"vat_rate": 150})
    assert response.status_code == 400
    assert "TVA" in response.json()["detail"]


# ===== Facture automatique par client =====
def test_opening_client_record_issues_missing_invoice(db):
    """Ouvrir la fiche du client émet la facture de son paiement encaissé."""
    _configure_issuer()
    assert db.query(InvoiceDB).count() == 0

    response = client.get("/api/admin/crm/users/u1")
    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body["invoices"]) == 1
    invoice = body["invoices"][0]
    assert invoice["number"] == "INV-2026-0001"
    assert invoice["amount_total"] == 69.0
    # 69 TTC à 18 % → 58,47 HT + 10,53 de TVA, et la somme doit être exacte.
    assert invoice["amount_net"] == 58.47
    assert invoice["vat_amount"] == 10.53
    assert round(invoice["amount_net"] + invoice["vat_amount"], 2) == invoice["amount_total"]
    assert body["invoicing"]["configured"] is True
    assert body["invoicing"]["generated"]["factures_creees"] == 1
    assert body["invoicing"]["total_facture"] == 69.0


def test_reopening_client_record_does_not_duplicate(db):
    """Une transaction ne donne qu'une facture, quel que soit le nombre d'ouvertures."""
    _configure_issuer()
    first = client.get("/api/admin/crm/users/u1").json()
    numbers = [i["number"] for i in first["invoices"]]

    for _ in range(3):
        again = client.get("/api/admin/crm/users/u1").json()

    assert [i["number"] for i in again["invoices"]] == numbers
    assert db.query(InvoiceDB).count() == 1
    assert again["invoicing"]["generated"]["factures_creees"] == 0


def test_client_record_opens_even_when_invoicing_unconfigured(db):
    """Sans mentions légales, la fiche s'ouvre quand même et explique le blocage.

    Bloquer l'ouverture de la fiche pour un défaut de configuration priverait
    l'exploitant de tout le reste (abonnement, activité, coordonnées).
    """
    response = client.get("/api/admin/crm/users/u1")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["email"] == "sarah@test.fr"     # la fiche est bien servie
    assert body["invoices"] == []
    assert body["invoicing"]["configured"] is False
    assert body["invoicing"]["blocked"] is not None
    assert body["invoicing"]["blocked"]["aide"]["missing"] == ["name", "legal_id"]


def test_free_access_creates_no_invoice(db):
    """Un accès offert (montant nul) ne donne pas de facture : aucune recette."""
    _configure_issuer()
    db.add(TransactionDB(
        id="tx-free", user_id="u1", plan_id="basic_14d", amount=0.0, currency="ILS",
        status="completed", created_at=datetime(2026, 4, 1), completed_at=datetime(2026, 4, 1),
    ))
    db.commit()

    body = client.get("/api/admin/crm/users/u1/invoices").json()
    assert len(body["invoices"]) == 1                              # seul le paiement payant
    assert body["invoicing"]["generated"]["sans_montant_ignores"] == 1


def test_pending_payment_is_not_invoiced(db):
    """Un paiement non abouti n'est pas une recette : il ne se facture pas."""
    _configure_issuer()
    db.add(TransactionDB(
        id="tx-pending", user_id="u1", plan_id="basic_30d", amount=99.0, currency="ILS",
        status="pending", created_at=datetime(2026, 4, 1),
    ))
    db.commit()

    body = client.get("/api/admin/crm/users/u1/invoices").json()
    assert [i["number"] for i in body["invoices"]] == ["INV-2026-0001"]


def test_invoice_paid_before_account_creation_is_attached_by_email(db):
    """Une facture émise sans compte rattaché reste visible sur la fiche du client.

    Un paiement encaissé avant la création du compte a pu être facturé avec la
    seule adresse du payeur : cette facture existe, elle doit apparaître.
    """
    _configure_issuer()
    db.add(InvoiceDB(
        id="inv-orphan", number="INV-2025-0009", year=2025, sequence=9,
        document_type="facture", user_id=None, customer_email="SARAH@test.fr",
        plan_id="basic_14d", plan_name="Formule Standard — 14 jours",
        currency="ILS", amount_total=69.0, amount_net=58.47, vat_rate=18.0, vat_amount=10.53,
        issued_at=datetime(2025, 12, 1), status="issued",
    ))
    db.commit()

    body = client.get("/api/admin/crm/users/u1/invoices").json()
    numbers = {i["number"] for i in body["invoices"]}
    assert "INV-2025-0009" in numbers


# ===== Les formes de la facture =====
@pytest.fixture
def invoice_id(db):
    _configure_issuer()
    body = client.get("/api/admin/crm/users/u1").json()
    return body["invoices"][0]["id"]


def test_every_download_link_is_advertised(db, invoice_id):
    """La fiche annonce elle-même les formes disponibles."""
    body = client.get("/api/admin/crm/users/u1/invoices").json()
    downloads = body["invoices"][0]["downloads"]
    assert set(downloads) == {"pdf", "html", "jpg", "png"}
    for url in downloads.values():
        assert url.startswith(f"/api/admin/invoices/{invoice_id}")


def test_invoice_available_as_pdf(db, invoice_id):
    response = client.get(f"/api/admin/invoices/{invoice_id}.pdf")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_invoice_available_as_html(db, invoice_id):
    """La forme HTML doit se suffire à elle-même : aucune ressource à charger."""
    response = client.get(f"/api/admin/invoices/{invoice_id}.html")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")

    body = response.text
    assert "INV-2026-0001" in body
    assert "Sarah Cohen" in body
    assert "Flash Neiga Ltd" in body
    assert "69,00 ILS" in body           # total TTC
    assert "58,47 ILS" in body           # total HT
    assert "<script" not in body          # rien d'exécutable
    assert "http://" not in body and "https://" not in body   # aucune ressource externe


def test_invoice_available_as_jpg_and_png(db, invoice_id):
    for extension, magic in (("jpg", b"\xff\xd8\xff"), ("png", b"\x89PNG\r\n\x1a\n")):
        response = client.get(f"/api/admin/invoices/{invoice_id}.{extension}")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("image/")
        assert response.content.startswith(magic), extension
        # Une image d'une page A4 lisible ne pèse pas quelques octets.
        assert len(response.content) > 5000, extension


def test_download_filename_carries_invoice_number(db, invoice_id):
    """Le fichier enregistré porte le numéro de facture, pas un identifiant opaque."""
    for extension in ("pdf", "jpg", "png"):
        response = client.get(f"/api/admin/invoices/{invoice_id}.{extension}")
        assert f'filename="INV-2026-0001.{extension}"' in response.headers["content-disposition"]


def test_unknown_invoice_is_a_clean_404(db):
    """Un identifiant inconnu ne doit pas ressembler à une panne du serveur."""
    for extension in ("pdf", "html", "jpg", "png"):
        response = client.get(f"/api/admin/invoices/does-not-exist.{extension}")
        assert response.status_code == 404, extension


def test_all_formats_show_the_same_amounts(db, invoice_id):
    """PDF, HTML et image doivent afficher les mêmes montants.

    Deux formes divergentes du même document, c'est un client et une comptable
    qui ne lisent pas la même chose — la faute la plus coûteuse du lot.
    """
    import invoice_formats
    from models import InvoiceDB as Model

    invoice = db.query(Model).filter(Model.id == invoice_id).first()
    view = invoice_formats.invoice_view(invoice)
    assert view["amount_total"] == "69,00 ILS"
    assert view["amount_net"] == "58,47 ILS"
    assert view["amount_vat"] == "10,53 ILS"
    assert view["vat_rate"] == "18 %"

    html_body = client.get(f"/api/admin/invoices/{invoice_id}.html").text
    for value in (view["amount_total"], view["amount_net"], view["amount_vat"]):
        assert value in html_body


def test_cancelled_invoice_is_marked_in_every_format(db, invoice_id):
    """Une facture annulée doit se voir, sur toutes les formes."""
    response = client.post(
        f"/api/admin/invoices/{invoice_id}/cancel",
        json={"reason": "Remboursement accordé"},
    )
    assert response.status_code == 200, response.text
    credit_note = response.json()["avoir"]

    html_body = client.get(f"/api/admin/invoices/{invoice_id}.html").text
    assert "FACTURE ANNULÉE" in html_body
    assert "Remboursement accordé" in html_body

    # L'avoir porte son propre numéro et des montants négatifs.
    assert credit_note["number"] == "AV-2026-0001"
    assert credit_note["amount_total"] == -69.0
    avoir_html = client.get(f"/api/admin/invoices/{credit_note['id']}.html").text
    assert "AVOIR AV-2026-0001" in avoir_html

    # L'image de l'annulation se produit aussi, sans erreur.
    image = client.get(f"/api/admin/invoices/{invoice_id}.png")
    assert image.status_code == 200
    assert len(image.content) > 5000
