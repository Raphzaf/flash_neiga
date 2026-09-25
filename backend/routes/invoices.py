"""
Factures d'abonnement (Flash Neiga) — espace administrateur.

Objectif : sortir du site tout ce dont la comptable a besoin pour une période,
en deux clics.

  GET    /api/admin/invoices/config          → mentions légales manquantes, taux de TVA
  POST   /api/admin/invoices/generate        → émettre les factures manquantes d'une période
  GET    /api/admin/invoices                 → liste des factures d'une période
  GET    /api/admin/invoices/summary         → total encaissé et TVA collectée
  GET    /api/admin/invoices/export.csv      → récapitulatif tableur
  GET    /api/admin/invoices/export.zip      → toutes les factures PDF de la période
  PUT    /api/admin/invoices/config          → renseigner l'identité de l'entreprise
  GET    /api/admin/invoices/{invoice_id}    → détail d'une facture
  GET    /api/admin/invoices/{invoice_id}.pdf  → la facture en PDF
  GET    /api/admin/invoices/{invoice_id}.html → la facture en page web imprimable
  GET    /api/admin/invoices/{invoice_id}.jpg  → la facture en image (JPG)
  GET    /api/admin/invoices/{invoice_id}.png  → la facture en image (PNG)
  POST   /api/admin/invoices/{invoice_id}/cancel → annuler par un avoir
  POST   /api/admin/invoices/{invoice_id}/send   → (re)envoyer la facture au client

Toutes les routes sont réservées aux administrateurs (`require_admin`).
"""
import io
import json
import logging
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

try:
    from database import get_db
    from models import InvoiceDB, TransactionDB, User
    from auth import require_admin
    import app_settings
    import invoicing
    import invoice_pdf
    import invoice_formats
    import mailer
except ImportError:  # pragma: no cover - import depuis la racine du dépôt
    from backend.database import get_db
    from backend.models import InvoiceDB, TransactionDB, User
    from backend.auth import require_admin
    from backend import app_settings
    from backend import invoicing
    from backend import invoice_pdf
    from backend import invoice_formats
    from backend import mailer

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/invoices",
    tags=["admin-invoices"],
    dependencies=[Depends(require_admin)],
)

PLANS_FILE = Path(__file__).parent.parent.parent / "hyp_plans.json"
try:
    with open(PLANS_FILE, "r", encoding="utf-8") as f:
        PLANS: Dict[str, Any] = json.load(f)
except Exception:  # pragma: no cover
    PLANS = {}


def _plan_names() -> Dict[str, str]:
    return {pid: (plan or {}).get("name") or pid for pid, plan in PLANS.items()}


# ===== Schémas =====
class GenerateRequest(BaseModel):
    since: Optional[datetime] = None
    until: Optional[datetime] = None


class CancelRequest(BaseModel):
    reason: str


class IssuerConfig(BaseModel):
    """Identité légale de l'émetteur, saisie depuis le CRM.

    Tous les champs sont facultatifs dans le schéma : une modification partielle
    (corriger seulement le téléphone) ne doit pas effacer le reste. Un champ
    laissé à `None` n'est pas touché ; un champ vidé volontairement (chaîne
    vide) revient à la valeur de l'environnement.
    """
    company_name: Optional[str] = None
    company_legal_id: Optional[str] = None
    company_address: Optional[str] = None
    company_city: Optional[str] = None
    company_country: Optional[str] = None
    company_email: Optional[str] = None
    company_phone: Optional[str] = None
    company_vat_id: Optional[str] = None
    footer: Optional[str] = None
    vat_rate: Optional[float] = None
    prices_include_vat: Optional[bool] = None


# ===== Helpers =====
def _parse_period(
    since: Optional[str], until: Optional[str], month: Optional[str],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Interprète une période. `month` (AAAA-MM) est le cas courant : la
    comptable travaille au mois, et le mois se traduit en bornes exactes."""
    if month:
        try:
            start = datetime.strptime(month, "%Y-%m")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Mois attendu au format AAAA-MM (par exemple 2026-03).",
            )
        # Premier jour du mois suivant, sans se soucier de sa longueur.
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return start, end

    def _parse(value: Optional[str], label: str) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Date « {label} » illisible : format attendu AAAA-MM-JJ.",
            )

    return _parse(since, "since"), _parse(until, "until")


def _query_period(db: Session, since: Optional[datetime], until: Optional[datetime]):
    query = db.query(InvoiceDB)
    if since is not None:
        query = query.filter(InvoiceDB.issued_at >= since)
    if until is not None:
        query = query.filter(InvoiceDB.issued_at < until)
    return query.order_by(InvoiceDB.year.asc(), InvoiceDB.sequence.asc())


def _payload(invoice: InvoiceDB) -> Dict[str, Any]:
    return {
        "downloads": _download_links(invoice.id),
        "id": invoice.id,
        "number": invoice.number,
        "document_type": invoice.document_type,
        "status": invoice.status,
        "customer_name": invoice.customer_name,
        "customer_email": invoice.customer_email,
        "plan_id": invoice.plan_id,
        "plan_name": invoice.plan_name,
        "service_start": invoice.service_start,
        "service_end": invoice.service_end,
        "currency": invoice.currency,
        "amount_net": invoice.amount_net,
        "vat_rate": invoice.vat_rate,
        "vat_amount": invoice.vat_amount,
        "amount_total": invoice.amount_total,
        "issued_at": invoice.issued_at,
        "paid_at": invoice.paid_at,
        "cancelled_at": invoice.cancelled_at,
        "cancellation_reason": invoice.cancellation_reason,
        "cancels_invoice_id": invoice.cancels_invoice_id,
        "transaction_id": invoice.transaction_id,
        "emailed_at": invoice.emailed_at,
        "email_error": invoice.email_error,
    }


def _get_or_404(db: Session, invoice_id: str) -> InvoiceDB:
    invoice = db.query(InvoiceDB).filter(InvoiceDB.id == invoice_id).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    return invoice


def _safe_filename(number: str) -> str:
    """Nom de fichier sûr : le numéro sert de nom, débarrassé de tout séparateur."""
    return "".join(c for c in (number or "facture") if c.isalnum() or c in "-_")


def _download_links(invoice_id: str) -> Dict[str, str]:
    """Les formes sous lesquelles une facture est récupérable.

    Fournies par le serveur plutôt que reconstruites côté navigateur : ajouter
    une forme demain n'obligera pas à retoucher le front.
    """
    base = f"/api/admin/invoices/{invoice_id}"
    return {
        "pdf": f"{base}.pdf",
        "html": f"{base}.html",
        "jpg": f"{base}.jpg",
        "png": f"{base}.png",
    }


# ===== Configuration =====
@router.get("/config")
def invoice_config(db: Session = Depends(get_db)):
    """Ce qu'il reste à renseigner avant de pouvoir émettre.

    Tant que la raison sociale et le numéro d'entreprise ne sont pas définis,
    aucune facture n'est émise : un PDF sans mentions légales n'aurait aucune
    valeur pour la comptable.
    """
    help_ = invoicing.configuration_help(db)
    # Envoi des factures aux clients : sans SMTP, elles sont émises mais
    # restent seulement téléchargeables depuis le profil de l'élève.
    help_["email_delivery"] = mailer.status()
    return help_


# Correspondance entre les champs du formulaire et les clés de réglage.
_CONFIG_KEYS = {
    "company_name": "INVOICE_COMPANY_NAME",
    "company_legal_id": "INVOICE_COMPANY_LEGAL_ID",
    "company_address": "INVOICE_COMPANY_ADDRESS",
    "company_city": "INVOICE_COMPANY_CITY",
    "company_country": "INVOICE_COMPANY_COUNTRY",
    "company_email": "INVOICE_COMPANY_EMAIL",
    "company_phone": "INVOICE_COMPANY_PHONE",
    "company_vat_id": "INVOICE_COMPANY_VAT_ID",
    "footer": "INVOICE_FOOTER",
}


@router.put("/config")
def update_invoice_config(
    payload: IssuerConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Enregistre l'identité de l'entreprise, sans redéploiement.

    C'est ce qui débloque l'émission : avant, ces informations n'existaient que
    dans les variables du serveur, et une facture ne pouvait donc pas être
    émise tant que personne n'y touchait.
    """
    values: Dict[str, Optional[str]] = {}
    for field, key in _CONFIG_KEYS.items():
        value = getattr(payload, field)
        if value is not None:
            values[key] = value

    if payload.vat_rate is not None:
        if not 0 <= payload.vat_rate <= 100:
            raise HTTPException(
                status_code=400,
                detail="Le taux de TVA doit être compris entre 0 et 100.",
            )
        values["INVOICE_VAT_RATE"] = str(payload.vat_rate)

    if payload.prices_include_vat is not None:
        values["INVOICE_PRICES_INCLUDE_VAT"] = "true" if payload.prices_include_vat else "false"

    if not values:
        raise HTTPException(status_code=400, detail="Aucun réglage à enregistrer.")

    try:
        app_settings.set_many(db, values, updated_by=current_user.email)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return invoicing.configuration_help(db)


# ===== Émission =====
@router.post("/generate")
def generate_invoices(payload: GenerateRequest, db: Session = Depends(get_db)):
    """Émet les factures manquantes des paiements encaissés sur la période.

    Sans période, tout l'historique est repris — c'est le rattrapage à faire une
    fois, pour les paiements antérieurs à la mise en place de la facturation.
    """
    try:
        result = invoicing.generate_missing_invoices(
            db, since=payload.since, until=payload.until, plan_names=_plan_names(),
        )
        # Les factures rattrapées partent aussi chez les clients.
        result["envoi"] = invoicing.send_pending_invoice_emails(db)
        return result
    except invoicing.InvoicingNotConfigured as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "aide": invoicing.configuration_help(db),
            },
        )


# ===== Consultation =====
@router.get("")
def list_invoices(
    db: Session = Depends(get_db),
    month: Optional[str] = Query(None, description="Période AAAA-MM (le plus simple)"),
    since: Optional[str] = Query(None, description="Début AAAA-MM-JJ"),
    until: Optional[str] = Query(None, description="Fin exclue AAAA-MM-JJ"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    start, end = _parse_period(since, until, month)
    query = _query_period(db, start, end)
    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    return {
        "items": [_payload(invoice) for invoice in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
    }


@router.get("/summary")
def invoices_summary(
    db: Session = Depends(get_db),
    month: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
):
    """Totaux de la période : chiffre d'affaires et TVA collectée.

    Les avoirs portent des montants négatifs : la somme donne donc directement
    le net encaissé, sans retraitement.
    """
    rows = _query_period(db, *_parse_period(since, until, month)).all()

    # Toutes les pièces sont additionnées, annulées comprises : c'est l'avoir,
    # avec ses montants négatifs, qui neutralise la facture qu'il annule.
    # Écarter la facture annulée SANS écarter son avoir soustrairait deux fois
    # la même somme — et le total ne collerait plus avec l'export CSV.
    by_currency: Dict[str, Dict[str, float]] = {}
    for invoice in rows:
        bucket = by_currency.setdefault(
            invoice.currency or "ILS", {"net": 0.0, "tva": 0.0, "ttc": 0.0, "pieces": 0}
        )
        bucket["net"] += invoice.amount_net or 0
        bucket["tva"] += invoice.vat_amount or 0
        bucket["ttc"] += invoice.amount_total or 0
        bucket["pieces"] += 1

    for bucket in by_currency.values():
        for key in ("net", "tva", "ttc"):
            bucket[key] = round(bucket[key], 2)

    return {
        "pieces": len(rows),
        "factures": len([i for i in rows if i.document_type == invoicing.DOCUMENT_INVOICE]),
        "avoirs": len([i for i in rows if i.document_type == invoicing.DOCUMENT_CREDIT_NOTE]),
        "annulees": len([i for i in rows if i.status == "cancelled"]),
        "totaux_par_devise": by_currency,
    }


@router.get("/export.csv")
def export_csv(
    db: Session = Depends(get_db),
    month: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
):
    """Récapitulatif tableur de la période — le fichier à envoyer à la comptable."""
    start, end = _parse_period(since, until, month)
    rows = _query_period(db, start, end).all()
    content = invoice_pdf.render_invoices_csv(rows)
    label = month or (start.date().isoformat() if start else "tout")
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="factures-{label}.csv"'},
    )


@router.get("/export.zip")
def export_zip(
    db: Session = Depends(get_db),
    month: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
):
    """Toutes les factures PDF de la période, plus le récapitulatif CSV.

    Un seul téléchargement à transmettre, plutôt qu'une facture à la fois.
    """
    start, end = _parse_period(since, until, month)
    rows = _query_period(db, start, end).all()
    if not rows:
        raise HTTPException(status_code=404, detail="Aucune facture sur cette période.")

    label = month or (start.date().isoformat() if start else "tout")
    buffer = io.BytesIO()
    failed: List[str] = []

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"recapitulatif-{label}.csv", invoice_pdf.render_invoices_csv(rows))
        for invoice in rows:
            try:
                archive.writestr(
                    f"{_safe_filename(invoice.number)}.pdf",
                    invoice_pdf.render_invoice_pdf(invoice),
                )
            except invoice_pdf.PdfUnavailable:
                raise HTTPException(status_code=503, detail=(
                    "Génération PDF indisponible : reportlab n'est pas installé sur le serveur. "
                    "L'export CSV, lui, reste disponible."
                ))
            except Exception as exc:  # une pièce illisible ne doit pas perdre le lot
                logger.warning("PDF de la facture %s impossible : %s", invoice.number, exc)
                failed.append(invoice.number)

        if failed:
            archive.writestr(
                "FACTURES-MANQUANTES.txt",
                "Ces factures n'ont pas pu être converties en PDF :\n"
                + "\n".join(failed)
                + "\nElles figurent malgré tout dans le récapitulatif CSV.\n",
            )

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="factures-{label}.zip"'},
    )


@router.get("/{invoice_id}.pdf")
def get_invoice_pdf(invoice_id: str, db: Session = Depends(get_db)):
    invoice = _get_or_404(db, invoice_id)
    try:
        content = invoice_pdf.render_invoice_pdf(invoice)
    except invoice_pdf.PdfUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            # `inline` : la facture s'ouvre dans l'onglet, on l'enregistre si besoin.
            "Content-Disposition": f'inline; filename="{_safe_filename(invoice.number)}.pdf"',
        },
    )


# Les routes « {invoice_id}.<extension> » sont déclarées AVANT « {invoice_id} » :
# sinon la route générique attraperait « abc.jpg » et chercherait une facture
# dont l'identifiant contient l'extension.
@router.get("/{invoice_id}.html", response_class=Response)
def get_invoice_html(invoice_id: str, db: Session = Depends(get_db)):
    """La facture en page web : s'ouvre partout, s'imprime en PDF depuis le navigateur.

    Ne dépend d'aucune bibliothèque : c'est la forme qui reste disponible même si
    la génération PDF ou image manque sur le serveur.
    """
    invoice = _get_or_404(db, invoice_id)
    return Response(
        content=invoice_formats.render_invoice_html(invoice),
        media_type="text/html; charset=utf-8",
    )


def _image_response(db: Session, invoice_id: str, fmt: str, extension: str) -> Response:
    invoice = _get_or_404(db, invoice_id)
    try:
        content = invoice_formats.render_invoice_image(invoice, fmt)
    except invoice_formats.ImageUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return Response(
        content=content,
        media_type=f"image/{fmt}",
        headers={
            # `inline` : l'image s'affiche dans l'onglet, on l'enregistre d'un
            # clic droit — c'est le geste attendu pour l'envoyer par messagerie.
            "Content-Disposition": (
                f'inline; filename="{_safe_filename(invoice.number)}.{extension}"'
            ),
        },
    )


@router.get("/{invoice_id}.jpg", response_class=Response)
def get_invoice_jpg(invoice_id: str, db: Session = Depends(get_db)):
    """La facture en image JPG — la forme la plus légère à envoyer par messagerie."""
    return _image_response(db, invoice_id, "jpeg", "jpg")


@router.get("/{invoice_id}.png", response_class=Response)
def get_invoice_png(invoice_id: str, db: Session = Depends(get_db)):
    """La facture en image PNG — sans perte, pour l'impression ou l'archivage."""
    return _image_response(db, invoice_id, "png", "png")


@router.get("/{invoice_id}")
def get_invoice(invoice_id: str, db: Session = Depends(get_db)):
    return _payload(_get_or_404(db, invoice_id))


@router.post("/{invoice_id}/cancel")
def cancel_invoice(invoice_id: str, payload: CancelRequest, db: Session = Depends(get_db)):
    """Annule une facture en émettant l'avoir correspondant.

    La facture d'origine est conservée : la supprimer ferait un trou dans la
    numérotation, ce qui invaliderait toute la série aux yeux du fisc.
    """
    reason = (payload.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Un motif d'annulation est obligatoire.")

    invoice = _get_or_404(db, invoice_id)
    try:
        credit_note = invoicing.cancel_invoice(db, invoice, reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # L'avoir est remis au client comme la facture qu'il annule.
    invoicing.send_invoice_email(db, credit_note)
    return {"facture_annulee": _payload(invoice), "avoir": _payload(credit_note)}


@router.post("/{invoice_id}/send")
def send_invoice(invoice_id: str, db: Session = Depends(get_db)):
    """(Re)envoie la facture au client par e-mail, PDF joint."""
    invoice = _get_or_404(db, invoice_id)
    if not mailer.configured():
        raise HTTPException(
            status_code=409,
            detail="Envoi impossible : aucun serveur d'e-mail configuré (SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM).",
        )
    if not invoice.customer_email:
        raise HTTPException(status_code=400, detail="Aucune adresse e-mail connue pour ce client.")
    if not invoicing.send_invoice_email(db, invoice, force=True):
        db.refresh(invoice)
        raise HTTPException(status_code=502, detail=f"Envoi échoué : {invoice.email_error or 'erreur inconnue'}")
    db.refresh(invoice)
    return _payload(invoice)
