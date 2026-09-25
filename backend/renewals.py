"""
Renouvellement automatique des abonnements (Flash Neiga).

Un abonnement se renouvelle comme sur n'importe quelle plateforme : à la fin
de chaque période (14, 21 ou 30 jours selon la formule), la carte de l'élève
est prélevée du prix de sa formule, l'accès est prolongé d'une période, et la
facture lui est envoyée. Cela continue jusqu'à ce qu'il résilie depuis son
profil.

HYP ne sait prélever automatiquement qu'au mois (paramètre `freq`, en mois) :
impossible pour 14 ou 21 jours. On applique donc la méthode prévue par HYP
pour les intervalles libres : le token de la carte est obtenu au premier
paiement, puis c'est ce module qui la prélève (`action=soft`) à chaque
échéance.

Règle absolue : ne jamais prélever deux fois la même échéance.
- Un verrou en base (`renewal_locked_until`), posé par une mise à jour
  conditionnelle, garantit qu'un seul processus traite un abonnement.
- La transaction est enregistrée AVANT d'appeler HYP. Si la réponse de HYP
  n'arrive pas (coupure réseau, redémarrage), on ignore si la carte a été
  débitée : la transaction reste « processing », l'abonnement est mis en
  attente de vérification, et aucune nouvelle tentative n'est faite tant
  qu'un administrateur n'a pas tranché.

En cas de refus de la carte, trois tentatives espacées d'un jour. Ensuite le
renouvellement s'arrête et l'élève est prévenu ; il peut repayer depuis le
site. L'accès n'est jamais prolongé sans paiement.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

try:
    from models import SubscriptionDB, TransactionDB, UserDB
    import mailer
    from routes import hyp_payments as hyp
except ImportError:  # pragma: no cover - import depuis la racine du dépôt
    from backend.models import SubscriptionDB, TransactionDB, UserDB
    from backend import mailer
    from backend.routes import hyp_payments as hyp

logger = logging.getLogger(__name__)

# On prélève un peu avant l'échéance pour que l'accès ne s'interrompe pas
# entre deux passages du balayage (horaire).
CHARGE_AHEAD = timedelta(hours=2)
RETRY_DELAY = timedelta(days=1)
MAX_FAILURES = 3
LOCK_DURATION = timedelta(minutes=15)

REVIEW_ERROR = (
    "Issue du prélèvement inconnue (HYP n'a pas répondu). Vérifier dans HYP "
    "si la carte a été débitée avant toute nouvelle tentative."
)


def _claim(db: Session, subscription_id: str, now: datetime) -> bool:
    """Pose le verrou de renouvellement. Vrai si ce processus l'a obtenu."""
    result = db.execute(
        update(SubscriptionDB)
        .where(
            SubscriptionDB.id == subscription_id,
            SubscriptionDB.status == "active",
            SubscriptionDB.auto_renew.is_(True),
            or_(SubscriptionDB.renewal_locked_until.is_(None),
                SubscriptionDB.renewal_locked_until < now),
        )
        .values(renewal_locked_until=now + LOCK_DURATION)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount == 1


def _release(db: Session, subscription: SubscriptionDB) -> None:
    subscription.renewal_locked_until = None
    db.commit()


def _open_attempt(db: Session, subscription: SubscriptionDB) -> Optional[TransactionDB]:
    """Prélèvement déjà lancé pour cet abonnement et resté sans issue connue."""
    candidates = (
        db.query(TransactionDB)
        .filter(
            TransactionDB.user_id == subscription.user_id,
            TransactionDB.event_type == "payment.renewal",
            TransactionDB.status == "processing",
        )
        .all()
    )
    return next(
        (t for t in candidates
         if isinstance(t.event_data, dict) and t.event_data.get("subscription_id") == subscription.id),
        None,
    )


def due_subscriptions(db: Session, now: Optional[datetime] = None) -> List[SubscriptionDB]:
    now = now or datetime.utcnow()
    return (
        db.query(SubscriptionDB)
        .filter(
            SubscriptionDB.status == "active",
            SubscriptionDB.auto_renew.is_(True),
            SubscriptionDB.next_renewal.isnot(None),
            SubscriptionDB.next_renewal <= now + CHARGE_AHEAD,
        )
        .order_by(SubscriptionDB.next_renewal.asc())
        .all()
    )


def _notify_failure(subscription: SubscriptionDB, user: Optional[UserDB], final: bool) -> None:
    """Prévient l'élève que sa carte a été refusée. Ne lève jamais."""
    if user is None or not user.email or not mailer.configured():
        return
    plan = hyp.get_plan(subscription.plan_id or "") or {}
    name = f"Bonjour {user.first_name}," if user.first_name else "Bonjour,"
    if final:
        body = (
            f"{name}\n\nLe renouvellement de ton abonnement {plan.get('name', 'Flash Neiga')} "
            "n'a pas pu être prélevé après plusieurs tentatives : il n'est plus renouvelé.\n\n"
            "Pour continuer à t'entraîner, reprends une formule sur https://app.flash-neiga.com/subscribe\n\n"
            "— Flash Neiga"
        )
        subject = "Ton abonnement Flash Neiga n'a pas pu être renouvelé"
    else:
        body = (
            f"{name}\n\nNous n'avons pas pu prélever le renouvellement de ton abonnement "
            f"{plan.get('name', 'Flash Neiga')}. Nous réessaierons demain.\n\n"
            "Si ta carte a changé, reprends une formule sur https://app.flash-neiga.com/subscribe\n\n"
            "— Flash Neiga"
        )
        subject = "Paiement refusé pour ton abonnement Flash Neiga"
    try:
        mailer.send(to=user.email, subject=subject, text=body)
    except Exception as exc:
        logger.warning("Avis d'échec de prélèvement non envoyé à %s : %s", user.email, exc)


def renew_subscription(db: Session, subscription: SubscriptionDB, now: Optional[datetime] = None) -> str:
    """Tente le renouvellement d'un abonnement arrivé à échéance.

    Renvoie : renewed | declined | stopped | review | skipped.
    """
    now = now or datetime.utcnow()
    if not _claim(db, subscription.id, now):
        return "skipped"
    db.refresh(subscription)

    try:
        if _open_attempt(db, subscription) is not None:
            subscription.renewal_error = REVIEW_ERROR
            db.commit()
            return "review"

        plan = hyp.get_plan(subscription.plan_id or "")
        if not plan or not hyp.is_renewable_plan(subscription.plan_id):
            subscription.auto_renew = False
            subscription.next_renewal = None
            subscription.renewal_error = "Formule non renouvelable"
            db.commit()
            return "stopped"

        if not subscription.hyp_token:
            original = (db.query(TransactionDB)
                        .filter(TransactionDB.id == subscription.transaction_id).first())
            hyp.fetch_card_token(db, subscription, original.hyp_transaction_id if original else None)
        if not subscription.hyp_token or not subscription.hyp_token_expiry:
            return _declined(db, subscription, now, subscription.renewal_error or "Carte non enregistrée")

        user = db.query(UserDB).filter(UserDB.id == subscription.user_id).first()
        amount = float(plan["amount"])
        currency = plan.get("currency", "ILS")
        # À l'heure, la période suivante démarre à la fin de la précédente
        # (même si le balayage passe quelques minutes après). Après un refus,
        # l'élève a été sans accès : elle démarre au paiement, pas avant.
        if subscription.end_date and not subscription.renewal_failures:
            period_start = subscription.end_date
        else:
            period_start = max(subscription.end_date or now, now)
        period_end = period_start + timedelta(days=int(plan.get("duration_days", 30)))

        # 1. On trace la tentative AVANT d'appeler HYP.
        attempt = TransactionDB(
            user_id=subscription.user_id,
            plan_id=subscription.plan_id,
            amount=amount,
            currency=currency,
            status="processing",
            event_type="payment.renewal",
            event_data={
                "subscription_id": subscription.id,
                "renewal_of": subscription.transaction_id,
                "user_email": user.email if user else None,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
        )
        db.add(attempt)
        db.commit()

        # 2. Prélèvement.
        try:
            result = hyp.hyp_charge_token(
                token=subscription.hyp_token,
                expiry=subscription.hyp_token_expiry,
                amount=amount,
                currency=currency,
                reference=attempt.id,
                info=f"{plan.get('name', 'Flash Neiga')} — renouvellement",
                client_name=(user.first_name if user else "") or "",
                user_id=subscription.hyp_user_id,
                email=user.email if user else None,
            )
        except hyp.HypRequestError as exc:
            # Issue inconnue : la transaction reste « processing ».
            subscription.renewal_error = f"{REVIEW_ERROR} ({exc})"
            db.commit()
            logger.error("Renouvellement %s sans réponse de HYP : %s", subscription.id, exc)
            return "review"

        attempt.callback_data = result
        attempt.hyp_transaction_id = result.get("Id")

        if result.get("CCode") != "0":
            attempt.status = "failed"
            db.commit()
            return _declined(db, subscription, now, f"Carte refusée (CCode={result.get('CCode')})", user=user)

        # 3. Payé : accès prolongé d'une période, facture émise et envoyée.
        attempt.status = "completed"
        attempt.completed_at = datetime.utcnow()
        subscription.end_date = period_end
        subscription.next_renewal = period_end
        subscription.renewal_failures = 0
        subscription.renewal_error = None
        subscription.updated_at = datetime.utcnow()
        db.commit()
        hyp.issue_invoice_safely(db, attempt)
        logger.info("Abonnement %s renouvelé jusqu'au %s (%s %s)",
                    subscription.id, period_end, amount, currency)
        return "renewed"
    finally:
        try:
            db.refresh(subscription)
            _release(db, subscription)
        except Exception:  # pragma: no cover - base indisponible
            db.rollback()


def _declined(db: Session, subscription: SubscriptionDB, now: datetime, reason: str,
              user: Optional[UserDB] = None) -> str:
    failures = int(subscription.renewal_failures or 0) + 1
    subscription.renewal_failures = failures
    subscription.renewal_error = reason
    final = failures >= MAX_FAILURES
    if final:
        # L'accès s'arrête à la date de fin déjà payée ; plus de prélèvement.
        subscription.auto_renew = False
        subscription.next_renewal = None
    else:
        subscription.next_renewal = now + RETRY_DELAY
    db.commit()
    logger.warning("Renouvellement %s refusé (%s/%s) : %s",
                   subscription.id, failures, MAX_FAILURES, reason)
    if user is None:
        user = db.query(UserDB).filter(UserDB.id == subscription.user_id).first()
    _notify_failure(subscription, user, final)
    return "stopped" if final else "declined"


def run_due_renewals(db: Session, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Traite tous les abonnements arrivés à échéance. Appelé chaque heure."""
    now = now or datetime.utcnow()
    counts: Dict[str, int] = {}
    for subscription in due_subscriptions(db, now):
        try:
            outcome = renew_subscription(db, subscription, now)
        except Exception as exc:
            db.rollback()
            logger.error("Renouvellement %s en erreur : %s", subscription.id, exc, exc_info=True)
            outcome = "error"
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def pending_attempts(db: Session, user_id: Optional[str] = None) -> List[TransactionDB]:
    """Prélèvements dont l'issue est inconnue, à vérifier dans HYP."""
    query = db.query(TransactionDB).filter(
        TransactionDB.event_type == "payment.renewal",
        TransactionDB.status == "processing",
    )
    if user_id:
        query = query.filter(TransactionDB.user_id == user_id)
    return query.order_by(TransactionDB.created_at.asc()).all()


def resolve_attempt(db: Session, attempt: TransactionDB, charged: bool,
                    hyp_transaction_id: Optional[str] = None) -> Optional[SubscriptionDB]:
    """Tranche un prélèvement resté sans réponse, après vérification dans HYP.

    `charged` : la carte a bien été débitée (visible dans HYP). L'accès est alors
    prolongé et la facture émise ; sinon la tentative est abandonnée et le
    renouvellement reprend à la prochaine échéance.
    """
    if attempt.event_type != "payment.renewal" or attempt.status != "processing":
        raise ValueError("Ce prélèvement n'est pas en attente de vérification.")
    data = attempt.event_data if isinstance(attempt.event_data, dict) else {}
    subscription = (db.query(SubscriptionDB)
                    .filter(SubscriptionDB.id == data.get("subscription_id")).first())

    if charged:
        attempt.status = "completed"
        attempt.completed_at = datetime.utcnow()
        if hyp_transaction_id:
            attempt.hyp_transaction_id = hyp_transaction_id
        if subscription is not None and data.get("period_end"):
            period_end = datetime.fromisoformat(data["period_end"])
            if not subscription.end_date or subscription.end_date < period_end:
                subscription.end_date = period_end
            if subscription.auto_renew:
                subscription.next_renewal = subscription.end_date
            subscription.renewal_error = None
            subscription.renewal_failures = 0
        db.commit()
        hyp.issue_invoice_safely(db, attempt)
    else:
        attempt.status = "failed"
        if subscription is not None:
            subscription.renewal_error = None
        db.commit()
    logger.info("Prélèvement %s tranché par un administrateur : %s",
                attempt.id, "débité" if charged else "non débité")
    return subscription
