"""
Tests de la facturation des abonnements.

On vérifie ici ce qu'une comptable — ou un contrôle fiscal — vérifierait :

1. La numérotation est continue, sans trou ni doublon, même en cas d'émissions
   simultanées.
2. Une facture émise ne change plus : renommer l'élève ne réécrit pas le passé.
3. Total = HT + TVA, au centime, toujours.
4. Rien ne se supprime : une erreur se corrige par un avoir.
5. Aucune facture n'est émise tant que les mentions légales manquent.
"""
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import invoicing  # noqa: E402
import invoice_pdf  # noqa: E402
from server import app  # noqa: E402
from database import Base, get_db  # noqa: E402
from models import InvoiceDB, SubscriptionDB, TransactionDB, UserDB, User  # noqa: E402
from auth import get_current_user, require_admin  # noqa: E402

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_invoices.db"
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


@pytest.fixture(scope="function")
def db(monkeypatch):
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_admin
    app.dependency_overrides[require_admin] = override_admin

    # Identité légale renseignée : sans elle, rien ne s'émet (c'est testé à part).
    monkeypatch.setenv("INVOICE_COMPANY_NAME", "Flash Neiga Ltd")
    monkeypatch.setenv("INVOICE_COMPANY_LEGAL_ID", "515123456")
    monkeypatch.setenv("INVOICE_COMPANY_ADDRESS", "12 rue Herzl")
    monkeypatch.setenv("INVOICE_COMPANY_CITY", "Tel Aviv")
    monkeypatch.setenv("INVOICE_VAT_RATE", "18")
    monkeypatch.setenv("INVOICE_PRICES_INCLUDE_VAT", "true")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.add(UserDB(id="u1", email="sarah@test.fr", hashed_password="x",
                       first_name="Sarah", last_name="Cohen"))
    session.commit()

    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides = previous


def _transaction(session, tid="t1", amount=99.0, user_id="u1", plan_id="basic_30d",
                 paid_at=None, status="completed", event_data=None):
    transaction = TransactionDB(
        id=tid, user_id=user_id, plan_id=plan_id, amount=amount, currency="ILS",
        status=status, completed_at=paid_at or datetime(2026, 3, 15, 10, 0),
        created_at=paid_at or datetime(2026, 3, 15, 10, 0), event_data=event_data,
    )
    session.add(transaction)
    session.commit()
    return transaction


# ===== Ventilation de la TVA =====
@pytest.mark.parametrize("total", [69.0, 89.0, 99.0, 119.0, 0.01, 1234.56])
def test_total_egale_toujours_ht_plus_tva(total):
    """Le contrôle le plus élémentaire d'une comptable — et le premier à casser
    si l'on arrondit HT et TVA indépendamment."""
    ttc, net, vat = invoicing.split_vat(total, 18, inclusive=True)
    assert round(net + vat, 2) == ttc


def test_ventilation_prix_ttc():
    ttc, net, vat = invoicing.split_vat(99, 18, inclusive=True)
    assert (ttc, net, vat) == (99.0, 83.9, 15.1)


def test_ventilation_prix_hors_taxes():
    ttc, net, vat = invoicing.split_vat(100, 18, inclusive=False)
    assert (ttc, net, vat) == (118.0, 100.0, 18.0)


def test_sans_tva_le_net_egale_le_total():
    assert invoicing.split_vat(99, 0) == (99.0, 99.0, 0.0)


def test_taux_de_tva_illisible_retombe_sur_le_defaut(monkeypatch):
    monkeypatch.setenv("INVOICE_VAT_RATE", "dix-huit")
    assert invoicing.vat_rate() == invoicing.DEFAULT_VAT_RATE
    monkeypatch.setenv("INVOICE_VAT_RATE", "300")
    assert invoicing.vat_rate() == invoicing.DEFAULT_VAT_RATE


# ===== Mentions légales obligatoires =====
def test_aucune_facture_sans_identite_legale(db, monkeypatch):
    monkeypatch.delenv("INVOICE_COMPANY_NAME", raising=False)
    transaction = _transaction(db)

    with pytest.raises(invoicing.InvoicingNotConfigured):
        invoicing.issue_invoice(db, transaction)

    r = client.post("/api/admin/invoices/generate", json={})
    assert r.status_code == 409
    assert "INVOICE_COMPANY_NAME" in str(r.json()["detail"]["aide"]["missing_env"])


def test_config_indique_ce_qui_manque(db, monkeypatch):
    monkeypatch.delenv("INVOICE_COMPANY_LEGAL_ID", raising=False)
    body = client.get("/api/admin/invoices/config").json()
    assert body["configured"] is False
    assert body["missing"] == ["legal_id"]


# ===== Numérotation =====
def test_numerotation_sequentielle_sans_trou(db):
    for i in range(5):
        invoicing.issue_invoice(db, _transaction(db, tid=f"t{i}"))

    numbers = [inv.number for inv in db.query(InvoiceDB).order_by(InvoiceDB.sequence).all()]
    assert numbers == [f"INV-2026-{i:04d}" for i in range(1, 6)]


def test_numerotation_unique_en_emissions_simultanees(db):
    """Deux encaissements à la même seconde ne doivent jamais partager un numéro."""
    for i in range(12):
        _transaction(db, tid=f"t{i}")

    errors = []
    barrier = threading.Barrier(6)

    def worker(index):
        session = TestingSessionLocal()
        try:
            transaction = session.query(TransactionDB).filter(TransactionDB.id == f"t{index}").first()
            barrier.wait(timeout=10)  # tout le monde part en même temps
            invoicing.issue_invoice(session, transaction)
        except Exception as exc:  # pragma: no cover - remonté par l'assertion
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)

    assert not errors, errors
    numbers = [inv.number for inv in db.query(InvoiceDB).all()]
    assert len(numbers) == 6
    assert len(set(numbers)) == 6  # aucun doublon
    sequences = sorted(inv.sequence for inv in db.query(InvoiceDB).all())
    assert sequences == list(range(1, 7))  # aucun trou


def test_une_transaction_ne_donne_quune_facture(db):
    """Les webhooks de paiement se répètent : une facture en double serait une faute."""
    transaction = _transaction(db)
    first = invoicing.issue_invoice(db, transaction)
    second = invoicing.issue_invoice(db, transaction)
    assert first.id == second.id
    assert db.query(InvoiceDB).count() == 1


# ===== Immuabilité =====
def test_facture_figee_apres_emission(db):
    """Renommer l'élève ne doit pas réécrire une facture déjà remise."""
    transaction = _transaction(db)
    invoice = invoicing.issue_invoice(db, transaction)
    assert invoice.customer_name == "Sarah Cohen"
    assert invoice.issuer_snapshot["name"] == "Flash Neiga Ltd"

    user = db.query(UserDB).filter(UserDB.id == "u1").first()
    user.last_name = "Levy"
    db.commit()

    db.refresh(invoice)
    assert invoice.customer_name == "Sarah Cohen"


def test_periode_de_service_reprise_de_labonnement(db):
    transaction = _transaction(db)
    db.add(SubscriptionDB(
        id="s1", user_id="u1", plan_id="basic_30d", transaction_id="t1",
        start_date=datetime(2026, 3, 15), end_date=datetime(2026, 4, 14), status="active",
    ))
    db.commit()

    invoice = invoicing.issue_invoice(db, transaction)
    assert invoice.service_start == datetime(2026, 3, 15)
    assert invoice.service_end == datetime(2026, 4, 14)


# ===== Paiement sans compte, puis rattachement =====
def test_paiement_sans_compte_facture_avec_lemail_de_paiement(db):
    """La recette existe : elle doit être facturée, même sans compte élève."""
    transaction = _transaction(db, tid="t-orphelin", user_id=None,
                               event_data={"user_email": "Inconnu@Test.fr"})
    invoice = invoicing.issue_invoice(db, transaction)
    assert invoice.customer_email == "inconnu@test.fr"
    assert invoice.customer_name is None


def test_rattachement_ulterieur_complete_le_client(db):
    transaction = _transaction(db, tid="t-orphelin", user_id=None,
                               event_data={"user_email": "sarah@test.fr"})
    invoice = invoicing.issue_invoice(db, transaction)
    assert invoice.customer_name is None
    numero_initial = invoice.number

    # L'élève réclame son paiement : le compte est rattaché.
    transaction.user_id = "u1"
    db.commit()
    invoicing.issue_invoice(db, transaction)

    db.refresh(invoice)
    assert invoice.customer_name == "Sarah Cohen"
    assert invoice.number == numero_initial  # ni nouveau numéro, ni doublon
    assert db.query(InvoiceDB).count() == 1


# ===== Annulation par avoir =====
def test_annulation_emet_un_avoir_et_conserve_la_facture(db):
    invoice = invoicing.issue_invoice(db, _transaction(db))
    credit = invoicing.cancel_invoice(db, invoice, "Remboursement à la demande de l'élève")

    assert credit.document_type == "avoir"
    assert credit.number.startswith("AV-")
    assert credit.amount_total == -invoice.amount_total
    assert credit.vat_amount == -invoice.vat_amount
    assert credit.cancels_invoice_id == invoice.id

    db.refresh(invoice)
    assert invoice.status == "cancelled"
    # La facture d'origine reste en base : pas de trou dans la numérotation.
    assert db.query(InvoiceDB).filter(InvoiceDB.id == invoice.id).first() is not None


def test_annulation_deux_fois_ne_cree_quun_avoir(db):
    invoice = invoicing.issue_invoice(db, _transaction(db))
    first = invoicing.cancel_invoice(db, invoice, "erreur")
    second = invoicing.cancel_invoice(db, invoice, "erreur")
    assert first.id == second.id
    assert db.query(InvoiceDB).filter(InvoiceDB.document_type == "avoir").count() == 1


def test_un_avoir_ne_sannule_pas(db):
    invoice = invoicing.issue_invoice(db, _transaction(db))
    credit = invoicing.cancel_invoice(db, invoice, "erreur")
    with pytest.raises(ValueError):
        invoicing.cancel_invoice(db, credit, "re-erreur")


def test_route_dannulation_exige_un_motif(db):
    invoice = invoicing.issue_invoice(db, _transaction(db))
    r = client.post(f"/api/admin/invoices/{invoice.id}/cancel", json={"reason": "   "})
    assert r.status_code == 400


# ===== Rattrapage de l'historique =====
def test_generation_rattrape_les_paiements_non_factures(db):
    _transaction(db, tid="t1", paid_at=datetime(2026, 3, 2))
    _transaction(db, tid="t2", paid_at=datetime(2026, 3, 20))
    _transaction(db, tid="t3", paid_at=datetime(2026, 4, 5))
    _transaction(db, tid="t-echec", status="failed", paid_at=datetime(2026, 3, 10))
    _transaction(db, tid="t-offert", amount=0, paid_at=datetime(2026, 3, 12))

    r = client.post("/api/admin/invoices/generate",
                    json={"since": "2026-03-01T00:00:00", "until": "2026-04-01T00:00:00"})
    assert r.status_code == 200
    body = r.json()
    assert body["factures_creees"] == 2          # t1 et t2 seulement
    assert body["sans_montant_ignores"] == 1     # l'accès offert n'est pas facturable

    # Relancer ne crée pas de doublon.
    again = client.post("/api/admin/invoices/generate",
                        json={"since": "2026-03-01T00:00:00", "until": "2026-04-01T00:00:00"}).json()
    assert again["factures_creees"] == 0


# ===== Consultation et exports =====
def test_filtre_par_mois(db):
    invoicing.issue_invoice(db, _transaction(db, tid="t1", paid_at=datetime(2026, 3, 2)))
    invoicing.issue_invoice(db, _transaction(db, tid="t2", paid_at=datetime(2026, 4, 2)))

    # `issued_at` est la date d'émission (aujourd'hui) : on filtre dessus.
    mois = datetime.utcnow().strftime("%Y-%m")
    body = client.get(f"/api/admin/invoices?month={mois}").json()
    assert body["total"] == 2

    autre = (datetime.utcnow().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    assert client.get(f"/api/admin/invoices?month={autre}").json()["total"] == 0


def test_mois_mal_forme_refuse(db):
    r = client.get("/api/admin/invoices?month=mars-2026")
    assert r.status_code == 400
    assert "AAAA-MM" in r.json()["detail"]


def test_recapitulatif_neutralise_les_factures_annulees_par_leur_avoir(db):
    """Une facture remboursée ne doit plus peser dans le chiffre d'affaires."""
    invoicing.issue_invoice(db, _transaction(db, tid="t1"))
    seconde = invoicing.issue_invoice(db, _transaction(db, tid="t2"))
    invoicing.cancel_invoice(db, seconde, "remboursée")

    body = client.get("/api/admin/invoices/summary").json()
    totaux = body["totaux_par_devise"]["ILS"]
    # 99 (t1) + 99 (t2) - 99 (avoir) = 99 réellement encaissés.
    assert totaux["ttc"] == 99.0
    assert totaux["tva"] == 15.1
    assert body["avoirs"] == 1
    assert body["annulees"] == 1


def test_recapitulatif_et_export_csv_donnent_le_meme_total(db):
    """Deux chiffres différents pour la même période, et la comptable appelle."""
    invoicing.issue_invoice(db, _transaction(db, tid="t1"))
    seconde = invoicing.issue_invoice(db, _transaction(db, tid="t2", amount=69.0))
    invoicing.cancel_invoice(db, seconde, "remboursée")

    total_resume = client.get("/api/admin/invoices/summary").json()["totaux_par_devise"]["ILS"]["ttc"]
    ligne_totale = client.get("/api/admin/invoices/export.csv").content.decode("utf-8-sig").strip().splitlines()[-1]

    assert ligne_totale.startswith("TOTAL")
    assert f"{total_resume:.2f}".replace(".", ",") in ligne_totale


def test_export_csv_lisible_par_un_tableur_francais(db):
    invoicing.issue_invoice(db, _transaction(db, tid="t1"))
    invoicing.issue_invoice(db, _transaction(db, tid="t2", amount=69.0))

    r = client.get("/api/admin/invoices/export.csv")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]

    raw = r.content
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM : sans lui Excel casse les accents
    text = raw.decode("utf-8-sig")
    lines = text.strip().splitlines()

    assert lines[0].startswith("Numéro;Type;Date d'émission")
    assert ";" in lines[1]
    assert "83,90" in text          # virgule décimale, pas de point
    assert lines[-1].startswith("TOTAL")
    assert "168,00" in lines[-1]    # 99 + 69


def test_export_csv_vide_reste_valide(db):
    r = client.get("/api/admin/invoices/export.csv")
    assert r.status_code == 200
    assert r.content.decode("utf-8-sig").strip().startswith("Numéro;")


# ===== PDF =====
def test_pdf_dune_facture(db):
    invoice = invoicing.issue_invoice(db, _transaction(db))
    content = invoice_pdf.render_invoice_pdf(invoice)

    assert content.startswith(b"%PDF")
    assert len(content) > 1000
    assert content.rstrip().endswith(b"%%EOF")


def test_montants_ecrits_a_la_francaise():
    """PDF et CSV doivent écrire le même montant de la même façon."""
    assert invoice_pdf._money(1234.5, "ILS") == "1\u202f234,50 ILS"
    assert invoice_pdf._money(99, "ILS") == "99,00 ILS"
    assert invoice_pdf._money(None, "ILS") == "0,00 ILS"


def test_pdf_par_la_route(db):
    invoice = invoicing.issue_invoice(db, _transaction(db))
    r = client.get(f"/api/admin/invoices/{invoice.id}.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_pdf_dun_avoir_et_dune_facture_annulee(db):
    invoice = invoicing.issue_invoice(db, _transaction(db))
    credit = invoicing.cancel_invoice(db, invoice, "Remboursement")

    db.refresh(invoice)
    # La facture annulée doit rester imprimable, avec sa mention d'annulation.
    assert invoice_pdf.render_invoice_pdf(invoice).startswith(b"%PDF")
    assert invoice_pdf.render_invoice_pdf(credit).startswith(b"%PDF")


def test_archive_zip_de_la_periode(db):
    import io as _io
    import zipfile

    invoicing.issue_invoice(db, _transaction(db, tid="t1"))
    invoicing.issue_invoice(db, _transaction(db, tid="t2"))

    r = client.get("/api/admin/invoices/export.zip")
    assert r.status_code == 200

    with zipfile.ZipFile(_io.BytesIO(r.content)) as archive:
        names = archive.namelist()
        assert any(n.endswith(".csv") for n in names)
        pdfs = [n for n in names if n.endswith(".pdf")]
        assert len(pdfs) == 2
        assert archive.read(pdfs[0]).startswith(b"%PDF")


def test_zip_vide_renvoie_404(db):
    assert client.get("/api/admin/invoices/export.zip").status_code == 404


def test_facture_introuvable(db):
    assert client.get("/api/admin/invoices/inexistante").status_code == 404
