"""
Facturation des abonnements (Flash Neiga).

Transforme les paiements encaissés en factures numérotées, prêtes à être
transmises à la comptable.

Trois règles gouvernent ce module, parce que ce sont des règles comptables et
non des choix techniques :

1. **Une facture ne change jamais.** Tout y est recopié à l'émission. Modifier
   une facture déjà remise, c'est falsifier une pièce comptable.
2. **La numérotation est continue.** Pas de trou, pas de doublon, même si deux
   émissions partent en même temps : la contrainte d'unicité en base tranche, et
   l'appelant retente avec le numéro suivant.
3. **On n'annule pas, on émet un avoir.** Une facture erronée reste en base ;
   un avoir (numéro propre, montants négatifs) vient la neutraliser.

L'identité de l'entreprise n'est jamais codée en dur : elle vient de variables
d'environnement (voir `.env.example`). Tant qu'elle n'est pas renseignée, aucune
facture n'est émise — mieux vaut un message clair qu'un PDF sans mentions
légales envoyé à une comptable.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

try:
    from models import InvoiceDB, SubscriptionDB, TransactionDB, UserDB
except ImportError:  # pragma: no cover - import depuis la racine du dépôt
    from backend.models import InvoiceDB, SubscriptionDB, TransactionDB, UserDB

logger = logging.getLogger(__name__)

# Taux de TVA israélienne (Ma'am). 18 % depuis janvier 2025 ; ajustable sans
# toucher au code, car un taux légal change par décision politique. Les factures
# déjà émises gardent le taux en vigueur à leur date : il est recopié dedans.
DEFAULT_VAT_RATE = 18.0

# Les tarifs affichés aux élèves (69, 89, 99 ₪…) sont des prix à la consommation,
# donc TTC. Le net est recalculé à partir du total, jamais l'inverse.
DEFAULT_PRICES_INCLUDE_VAT = True

INVOICE_PREFIX = "INV"
CREDIT_NOTE_PREFIX = "AV"

DOCUMENT_INVOICE = "facture"
DOCUMENT_CREDIT_NOTE = "avoir"

# Nombre de tentatives d'attribution d'un numéro en cas d'émissions simultanées.
_NUMBER_ATTEMPTS = 8


class InvoicingNotConfigured(Exception):
    """L'identité légale de l'entreprise n'est pas renseignée."""


# ===== Identité de l'émetteur =====
def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def vat_rate() -> float:
    """Taux de TVA à appliquer aux nouvelles factures, en pourcentage."""
    raw = os.environ.get("INVOICE_VAT_RATE")
    if raw is None or not raw.strip():
        return DEFAULT_VAT_RATE
    try:
        value = float(raw)
    except ValueError:
        logger.warning("INVOICE_VAT_RATE illisible (%r) — %s %% appliqué.", raw, DEFAULT_VAT_RATE)
        return DEFAULT_VAT_RATE
    if not 0 <= value <= 100:
        logger.warning("INVOICE_VAT_RATE hors bornes (%s) — %s %% appliqué.", value, DEFAULT_VAT_RATE)
        return DEFAULT_VAT_RATE
    return value


def prices_include_vat() -> bool:
    raw = _env("INVOICE_PRICES_INCLUDE_VAT").lower()
    if not raw:
        return DEFAULT_PRICES_INCLUDE_VAT
    return raw in ("1", "true", "yes", "oui")


def issuer() -> Dict[str, str]:
    """Coordonnées légales de l'entreprise, telles qu'elles figureront en tête."""
    return {
        "name": _env("INVOICE_COMPANY_NAME"),
        "legal_id": _env("INVOICE_COMPANY_LEGAL_ID"),      # ח.פ / ע.מ
        "address": _env("INVOICE_COMPANY_ADDRESS"),
        "city": _env("INVOICE_COMPANY_CITY"),
        "country": _env("INVOICE_COMPANY_COUNTRY", "Israël"),
        "email": _env("INVOICE_COMPANY_EMAIL"),
        "phone": _env("INVOICE_COMPANY_PHONE"),
        "vat_id": _env("INVOICE_COMPANY_VAT_ID"),          # n° assujetti TVA, si distinct
        "footer": _env("INVOICE_FOOTER"),                  # mention libre (RIB, conditions…)
    }


# Sans ces deux-là, le document n'a aucune valeur : c'est le minimum exigé sur
# une facture israélienne.
REQUIRED_ISSUER_FIELDS = ("name", "legal_id")


def missing_issuer_fields() -> List[str]:
    data = issuer()
    return [field for field in REQUIRED_ISSUER_FIELDS if not data.get(field)]


def invoicing_configured() -> bool:
    return not missing_issuer_fields()


def configuration_help() -> Dict[str, Any]:
    """Ce qu'il reste à renseigner — affiché tel quel côté admin."""
    missing = missing_issuer_fields()
    labels = {
        "name": "INVOICE_COMPANY_NAME — raison sociale de l'entreprise",
        "legal_id": "INVOICE_COMPANY_LEGAL_ID — numéro d'entreprise (ח.פ / ע.מ)",
    }
    return {
        "configured": not missing,
        "missing": missing,
        "missing_env": [labels.get(field, field) for field in missing],
        "vat_rate": vat_rate(),
        "prices_include_vat": prices_include_vat(),
        "issuer": issuer(),
    }


# ===== Montants =====
def split_vat(total: float, rate: float, inclusive: bool = True) -> Tuple[float, float, float]:
    """Ventile un montant en (total TTC, net HT, TVA).

    `inclusive` : le montant fourni contient déjà la TVA (cas des prix affichés
    aux élèves). Sinon il s'agit d'un net auquel la TVA s'ajoute.

    Les trois valeurs sont arrondies au centime ET la TVA est recalculée par
    différence : sans cela, total ≠ net + TVA à cause des arrondis, et la
    comptable rejette la pièce.
    """
    total = round(float(total or 0), 2)
    rate = float(rate or 0)

    if rate <= 0:
        return total, total, 0.0

    if inclusive:
        net = round(total / (1 + rate / 100), 2)
        return total, net, round(total - net, 2)

    net = total
    vat = round(net * rate / 100, 2)
    return round(net + vat, 2), net, vat


# ===== Numérotation =====
def _next_sequence(db: Session, year: int, document_type: str) -> int:
    """Numéro suivant pour l'année et le type de document."""
    current = (
        db.query(func.max(InvoiceDB.sequence))
        .filter(InvoiceDB.year == year, InvoiceDB.document_type == document_type)
        .scalar()
    )
    return int(current or 0) + 1


def format_number(year: int, sequence: int, document_type: str) -> str:
    prefix = CREDIT_NOTE_PREFIX if document_type == DOCUMENT_CREDIT_NOTE else INVOICE_PREFIX
    return f"{prefix}-{year}-{sequence:04d}"


# ===== Émission =====
def _customer_name(user: Optional[UserDB]) -> Optional[str]:
    if user is None:
        return None
    parts = [p for p in (user.first_name, user.last_name) if p]
    return " ".join(parts) or None


# Clés sous lesquelles les prestataires de paiement déposent l'email du payeur.
_EMAIL_KEYS = ("user_email", "email", "Email", "UserEmail", "client_email")


def _payment_email(transaction: TransactionDB) -> Optional[str]:
    """E-mail saisi au paiement, quand le paiement n'est rattaché à aucun compte.

    Un encaissement sans compte doit tout de même donner lieu à une facture —
    la recette est bien réalisée et doit être déclarée. On y porte alors la
    seule identité connue : l'adresse utilisée pour payer.
    """
    for source in (transaction.event_data, transaction.callback_data):
        if isinstance(source, dict):
            for key in _EMAIL_KEYS:
                value = source.get(key)
                if value:
                    return str(value).strip().lower()
    return None


def _service_period(db: Session, transaction: TransactionDB) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Période couverte par l'abonnement payé — attendue par la comptable pour
    rattacher la recette au bon exercice."""
    subscription = (
        db.query(SubscriptionDB)
        .filter(SubscriptionDB.transaction_id == transaction.id)
        .first()
    )
    if subscription is None and transaction.user_id:
        subscription = (
            db.query(SubscriptionDB)
            .filter(
                SubscriptionDB.user_id == transaction.user_id,
                SubscriptionDB.plan_id == transaction.plan_id,
            )
            .order_by(SubscriptionDB.created_at.desc())
            .first()
        )
    if subscription is None:
        return None, None
    return subscription.start_date, subscription.end_date


def _insert_with_number(db: Session, build, year: int, document_type: str) -> InvoiceDB:
    """Insère un document en lui attribuant le premier numéro libre.

    Deux émissions simultanées peuvent viser le même numéro : la contrainte
    d'unicité en rejette une, et on retente avec le suivant. C'est ce qui rend
    la numérotation fiable sans verrou global.
    """
    last_error: Optional[Exception] = None
    for _ in range(_NUMBER_ATTEMPTS):
        sequence = _next_sequence(db, year, document_type)
        invoice = build(sequence, format_number(year, sequence, document_type))
        db.add(invoice)
        try:
            db.commit()
            db.refresh(invoice)
            return invoice
        except IntegrityError as exc:
            db.rollback()
            last_error = exc
            continue
    raise RuntimeError(f"Numéro de {document_type} introuvable après {_NUMBER_ATTEMPTS} tentatives : {last_error}")


def _attach_customer_if_missing(db: Session, invoice: InvoiceDB, transaction: TransactionDB) -> None:
    """Complète l'identité du client sur une facture émise sans compte rattaché.

    Seul cas où une facture est retouchée, et il est légitime : on ne change ni
    montant, ni date, ni numéro — on renseigne une identité qui manquait. Une
    facture dont le client est déjà connu n'est jamais modifiée.
    """
    if invoice.customer_name or not transaction.user_id:
        return
    user = db.query(UserDB).filter(UserDB.id == transaction.user_id).first()
    if user is None:
        return

    invoice.user_id = user.id
    invoice.customer_name = _customer_name(user)
    invoice.customer_email = invoice.customer_email or user.email
    try:
        db.commit()
        logger.info("Client renseigné a posteriori sur la facture %s", invoice.number)
    except Exception as exc:
        db.rollback()
        logger.warning("Client non renseigné sur la facture %s : %s", invoice.number, exc)


def issue_invoice(
    db: Session,
    transaction: TransactionDB,
    plan_name: Optional[str] = None,
) -> InvoiceDB:
    """Émet la facture d'un paiement encaissé (ou renvoie celle qui existe déjà).

    Idempotent : rappelée pour la même transaction, elle ne crée pas de doublon —
    les webhooks de paiement se répètent, une facture en double serait une erreur
    comptable.
    """
    if not invoicing_configured():
        raise InvoicingNotConfigured(
            "Identité de l'entreprise incomplète : " + ", ".join(missing_issuer_fields())
        )

    existing = (
        db.query(InvoiceDB).filter(InvoiceDB.transaction_id == transaction.id).first()
    )
    if existing is not None:
        _attach_customer_if_missing(db, existing, transaction)
        return existing

    user = (
        db.query(UserDB).filter(UserDB.id == transaction.user_id).first()
        if transaction.user_id else None
    )
    paid_at = transaction.completed_at or transaction.created_at or datetime.utcnow()
    rate = vat_rate()
    total, net, vat = split_vat(transaction.amount or 0, rate, inclusive=prices_include_vat())
    service_start, service_end = _service_period(db, transaction)
    year = paid_at.year

    def build(sequence: int, number: str) -> InvoiceDB:
        return InvoiceDB(
            number=number,
            year=year,
            sequence=sequence,
            document_type=DOCUMENT_INVOICE,
            transaction_id=transaction.id,
            user_id=transaction.user_id,
            customer_name=_customer_name(user),
            customer_email=(user.email if user else _payment_email(transaction)),
            plan_id=transaction.plan_id,
            plan_name=plan_name or transaction.plan_id,
            service_start=service_start,
            service_end=service_end,
            currency=(transaction.currency or "ILS"),
            amount_total=total,
            amount_net=net,
            vat_rate=rate,
            vat_amount=vat,
            issuer_snapshot=issuer(),
            issued_at=datetime.utcnow(),
            paid_at=paid_at,
            status="issued",
        )

    invoice = _insert_with_number(db, build, year, DOCUMENT_INVOICE)
    logger.info("Facture %s émise pour la transaction %s (%s %s)",
                invoice.number, transaction.id, invoice.amount_total, invoice.currency)
    return invoice


def cancel_invoice(db: Session, invoice: InvoiceDB, reason: str) -> InvoiceDB:
    """Annule une facture par un avoir, et renvoie cet avoir.

    La facture d'origine reste en base, marquée annulée : la supprimer créerait
    un trou dans la numérotation, ce qu'un contrôle fiscal ne pardonne pas.
    """
    if invoice.document_type != DOCUMENT_INVOICE:
        raise ValueError("Un avoir ne s'annule pas.")
    if invoice.status == "cancelled":
        existing = (
            db.query(InvoiceDB)
            .filter(InvoiceDB.cancels_invoice_id == invoice.id)
            .first()
        )
        if existing is not None:
            return existing

    year = datetime.utcnow().year

    def build(sequence: int, number: str) -> InvoiceDB:
        return InvoiceDB(
            number=number,
            year=year,
            sequence=sequence,
            document_type=DOCUMENT_CREDIT_NOTE,
            cancels_invoice_id=invoice.id,
            transaction_id=None,  # la transaction reste rattachée à la facture d'origine
            user_id=invoice.user_id,
            customer_name=invoice.customer_name,
            customer_email=invoice.customer_email,
            plan_id=invoice.plan_id,
            plan_name=invoice.plan_name,
            service_start=invoice.service_start,
            service_end=invoice.service_end,
            currency=invoice.currency,
            amount_total=-invoice.amount_total,
            amount_net=-invoice.amount_net,
            vat_rate=invoice.vat_rate,
            vat_amount=-invoice.vat_amount,
            issuer_snapshot=issuer(),
            issued_at=datetime.utcnow(),
            paid_at=invoice.paid_at,
            status="issued",
            cancellation_reason=reason,
        )

    credit_note = _insert_with_number(db, build, year, DOCUMENT_CREDIT_NOTE)

    invoice.status = "cancelled"
    invoice.cancelled_at = datetime.utcnow()
    invoice.cancellation_reason = reason
    db.commit()

    logger.info("Facture %s annulée par l'avoir %s (%s)", invoice.number, credit_note.number, reason)
    return credit_note


def generate_missing_invoices(
    db: Session,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    plan_names: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Émet les factures manquantes pour tous les paiements encaissés de la période.

    Sert au rattrapage : les paiements antérieurs à la mise en place de la
    facturation n'ont pas de facture, et la comptable les attend.
    """
    if not invoicing_configured():
        raise InvoicingNotConfigured(
            "Identité de l'entreprise incomplète : " + ", ".join(missing_issuer_fields())
        )

    query = db.query(TransactionDB).filter(TransactionDB.status == "completed")
    paid_on = func.coalesce(TransactionDB.completed_at, TransactionDB.created_at)
    if since is not None:
        query = query.filter(paid_on >= since)
    if until is not None:
        query = query.filter(paid_on < until)

    transactions = query.order_by(paid_on.asc()).all()

    already = {
        row[0] for row in
        db.query(InvoiceDB.transaction_id).filter(InvoiceDB.transaction_id.isnot(None)).all()
    }

    created: List[str] = []
    skipped_no_amount = 0
    for transaction in transactions:
        if transaction.id in already:
            continue
        if not transaction.amount:
            # Accès offert par code promo : rien à facturer, mais on le signale
            # pour que le rapprochement comptable ne semble pas incomplet.
            skipped_no_amount += 1
            continue
        plan_name = (plan_names or {}).get(transaction.plan_id or "")
        invoice = issue_invoice(db, transaction, plan_name=plan_name)
        created.append(invoice.number)

    return {
        "paiements_examines": len(transactions),
        "factures_creees": len(created),
        "numeros": created,
        "deja_facturees": len([t for t in transactions if t.id in already]),
        "sans_montant_ignores": skipped_no_amount,
    }
