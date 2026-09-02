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
  GET    /api/admin/invoices/{invoice_id}    → détail d'une facture
  GET    /api/admin/invoices/{invoice_id}.pdf → la facture en PDF
  POST   /api/admin/invoices/{invoice_id}/cancel → annuler par un avoir

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
    from models import InvoiceDB, TransactionDB
    from auth import require_admin
    import invoicing
    import invoice_pdf
except ImportError:  # pragma: no cover - import depuis la racine du dépôt
    from backend.database import get_db
    from backend.models import InvoiceDB, TransactionDB
    from backend.auth import require_admin
    from backend import invoicing
    from backend import invoice_pdf

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
    }


def _get_or_404(db: Session, invoice_id: str) -> InvoiceDB:
    invoice = db.query(InvoiceDB).filter(InvoiceDB.id == invoice_id).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    return invoice


def _safe_filename(number: str) -> str:
    """Nom de fichier sûr : le numéro sert de nom, débarrassé de tout séparateur."""
    return "".join(c for c in (number or "facture") if c.isalnum() or c in "-_")


# ===== Configuration =====
@router.get("/config")
def invoice_config():
    """Ce qu'il reste à renseigner avant de pouvoir émettre.

    Tant que la raison sociale et le numéro d'entreprise ne sont pas définis,
    aucune facture n'est émise : un PDF sans mentions légales n'aurait aucune
    valeur pour la comptable.
    """
    return invoicing.configuration_help()


# ===== Émission =====
@router.post("/generate")
def generate_invoices(payload: GenerateRequest, db: Session = Depends(get_db)):
    """Émet les factures manquantes des paiements encaissés sur la période.

    Sans période, tout l'historique est repris — c'est le rattrapage à faire une
    fois, pour les paiements antérieurs à la mise en place de la facturation.
    """
    try:
        return invoicing.generate_missing_invoices(
            db, since=payload.since, until=payload.until, plan_names=_plan_names(),
        )
    except invoicing.InvoicingNotConfigured as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "aide": invoicing.configuration_help(),
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

    return {"facture_annulee": _payload(invoice), "avoir": _payload(credit_note)}
