"""
CRM administrateur (Flash Neiga).

Gestion des comptes élèves, de leurs abonnements et de leurs paiements.
Toutes les routes sont réservées aux administrateurs (voir `require_admin` :
utilisateur authentifié dont l'email figure dans ADMIN_EMAILS).

  GET    /api/admin/crm/stats                          → indicateurs globaux
  GET    /api/admin/crm/users                          → liste + recherche + pagination
  GET    /api/admin/crm/users/{user_id}                → fiche complète d'un élève
  PATCH  /api/admin/crm/users/{user_id}                → modifier prénom / nom / email
  DELETE /api/admin/crm/users/{user_id}                → supprimer un compte et ses données
  POST   /api/admin/crm/users/{user_id}/password       → réinitialiser le mot de passe
  POST   /api/admin/crm/users/{user_id}/subscriptions  → accorder / prolonger un abonnement
  POST   /api/admin/crm/subscriptions/{sub_id}/cancel  → résilier un abonnement
  GET    /api/admin/crm/transactions                   → historique des paiements
  POST   /api/admin/crm/transactions/{id}/attach       → rattacher un paiement à un compte
  GET    /api/admin/crm/plans                          → catalogue des formules
"""
import json
import logging
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

try:
    from database import get_db
    from models import (
        UserDB, SubscriptionDB, TransactionDB, PaymentDB,
        ExamSessionDB, UserMistakeDB, User, PromoCodeDB, PromoRedemptionDB,
    )
    from auth import require_admin, hash_password, normalize_email, find_user_by_email
    from routes.hyp_payments import provision_subscription, transaction_email
    import promo as promo_lib
except ImportError:  # pragma: no cover - import depuis la racine du repo
    from backend.database import get_db
    from backend.models import (
        UserDB, SubscriptionDB, TransactionDB, PaymentDB,
        ExamSessionDB, UserMistakeDB, User, PromoCodeDB, PromoRedemptionDB,
    )
    from backend.auth import require_admin, hash_password, normalize_email, find_user_by_email
    from backend.routes.hyp_payments import provision_subscription, transaction_email
    from backend import promo as promo_lib

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/crm",
    tags=["admin-crm"],
    dependencies=[Depends(require_admin)],
)

PLANS_FILE = Path(__file__).parent.parent.parent / "hyp_plans.json"
try:
    with open(PLANS_FILE, "r", encoding="utf-8") as f:
        PLANS: Dict[str, Any] = json.load(f)
except Exception:  # pragma: no cover
    PLANS = {}


# ===== Schémas =====
class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None


class PasswordReset(BaseModel):
    new_password: str


class TransactionAttach(BaseModel):
    """Rattachement manuel d'un paiement à un compte élève."""
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None   # None = mot de passe provisoire généré


class SubscriptionGrant(BaseModel):
    plan_id: str
    duration_days: Optional[int] = None   # par défaut : durée du plan
    start_now: bool = True                # sinon, prolonge l'abonnement actif


class PromoCodeCreate(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: str                    # percent | amount | free
    discount_value: float = 0
    plan_ids: List[str] = []              # [] = toutes les formules
    max_uses: Optional[int] = None        # None = illimité
    max_uses_per_user: int = 1
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    active: bool = True


class PromoCodeUpdate(BaseModel):
    description: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    plan_ids: Optional[List[str]] = None
    max_uses: Optional[int] = None
    max_uses_per_user: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    active: Optional[bool] = None


# ===== Helpers =====
def _plan_name(plan_id: Optional[str]) -> str:
    return (PLANS.get(plan_id or "") or {}).get("name") or plan_id or "—"


def _is_active(sub: Optional[SubscriptionDB], now: Optional[datetime] = None) -> bool:
    if sub is None:
        return False
    now = now or datetime.utcnow()
    return sub.status == "active" and (sub.end_date is None or sub.end_date > now)


def _sub_payload(sub: Optional[SubscriptionDB]) -> Optional[Dict[str, Any]]:
    if sub is None:
        return None
    return {
        "id": sub.id,
        "plan_id": sub.plan_id,
        "plan_name": _plan_name(sub.plan_id),
        "status": sub.status,
        "is_active": _is_active(sub),
        "start_date": sub.start_date,
        "end_date": sub.end_date,
        "canceled_at": sub.canceled_at,
        "created_at": sub.created_at,
        "days_left": (
            max(0, (sub.end_date - datetime.utcnow()).days) if sub.end_date else None
        ),
    }


def _latest_subscriptions(db: Session, user_ids: List[str]) -> Dict[str, SubscriptionDB]:
    """Abonnement le plus pertinent par élève : l'actif, sinon le plus récent."""
    if not user_ids:
        return {}
    subs = (
        db.query(SubscriptionDB)
        .filter(SubscriptionDB.user_id.in_(user_ids))
        .order_by(SubscriptionDB.created_at.asc())
        .all()
    )
    best: Dict[str, SubscriptionDB] = {}
    for sub in subs:
        current = best.get(sub.user_id)
        # Un abonnement actif l'emporte toujours ; sinon le plus récent (ordre asc).
        if current is None or _is_active(sub) or not _is_active(current):
            best[sub.user_id] = sub
    return best


def _spent_by_user(db: Session, user_ids: List[str]) -> Dict[str, float]:
    """Total réellement encaissé par élève (transactions complétées)."""
    if not user_ids:
        return {}
    rows = (
        db.query(TransactionDB.user_id, func.coalesce(func.sum(TransactionDB.amount), 0.0))
        .filter(
            TransactionDB.user_id.in_(user_ids),
            TransactionDB.status == "completed",
        )
        .group_by(TransactionDB.user_id)
        .all()
    )
    return {uid: float(total or 0) for uid, total in rows}


def _counts(db: Session, model, user_ids: List[str]) -> Dict[str, int]:
    if not user_ids:
        return {}
    rows = (
        db.query(model.user_id, func.count(model.id))
        .filter(model.user_id.in_(user_ids))
        .group_by(model.user_id)
        .all()
    )
    return {uid: int(n or 0) for uid, n in rows}


# ===== Indicateurs globaux =====
@router.get("/stats")
async def crm_stats(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    total_users = db.query(func.count(UserDB.id)).scalar() or 0
    new_30d = (
        db.query(func.count(UserDB.id))
        .filter(UserDB.created_at >= now - timedelta(days=30))
        .scalar()
        or 0
    )
    active_subs = (
        db.query(func.count(SubscriptionDB.id))
        .filter(
            SubscriptionDB.status == "active",
            or_(SubscriptionDB.end_date.is_(None), SubscriptionDB.end_date > now),
        )
        .scalar()
        or 0
    )
    revenue_total = (
        db.query(func.coalesce(func.sum(TransactionDB.amount), 0.0))
        .filter(TransactionDB.status == "completed")
        .scalar()
        or 0.0
    )
    revenue_30d = (
        db.query(func.coalesce(func.sum(TransactionDB.amount), 0.0))
        .filter(
            TransactionDB.status == "completed",
            TransactionDB.created_at >= now - timedelta(days=30),
        )
        .scalar()
        or 0.0
    )
    by_plan_rows = (
        db.query(SubscriptionDB.plan_id, func.count(SubscriptionDB.id))
        .filter(
            SubscriptionDB.status == "active",
            or_(SubscriptionDB.end_date.is_(None), SubscriptionDB.end_date > now),
        )
        .group_by(SubscriptionDB.plan_id)
        .all()
    )
    pending = (
        db.query(func.count(TransactionDB.id))
        .filter(TransactionDB.status == "pending")
        .scalar()
        or 0
    )

    return {
        "total_users": int(total_users),
        "new_users_30d": int(new_30d),
        "active_subscriptions": int(active_subs),
        "revenue_total": round(float(revenue_total), 2),
        "revenue_30d": round(float(revenue_30d), 2),
        "pending_transactions": int(pending),
        "active_by_plan": [
            {"plan_id": pid, "plan_name": _plan_name(pid), "count": int(n)}
            for pid, n in by_plan_rows
        ],
        "generated_at": now,
    }


# ===== Liste des élèves =====
@router.get("/users")
async def list_users(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Recherche email / prénom / nom"),
    status: str = Query("all", pattern="^(all|active|inactive)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = db.query(UserDB)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            or_(
                UserDB.email.ilike(like),
                UserDB.first_name.ilike(like),
                UserDB.last_name.ilike(like),
            )
        )

    total = query.count()
    users = (
        query.order_by(UserDB.created_at.desc()).offset(offset).limit(limit).all()
    )
    user_ids = [u.id for u in users]

    subs = _latest_subscriptions(db, user_ids)
    spent = _spent_by_user(db, user_ids)
    exams = _counts(db, ExamSessionDB, user_ids)
    mistakes = _counts(db, UserMistakeDB, user_ids)

    items = []
    for u in users:
        sub = subs.get(u.id)
        payload = _sub_payload(sub)
        active = bool(payload and payload["is_active"])
        if status == "active" and not active:
            continue
        if status == "inactive" and active:
            continue
        items.append({
            "id": u.id,
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "created_at": u.created_at,
            "subscription": payload,
            "has_active_subscription": active,
            "total_spent": round(spent.get(u.id, 0.0), 2),
            "exam_sessions": exams.get(u.id, 0),
            "mistakes": mistakes.get(u.id, 0),
        })

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(users) < total,
    }


# ===== Fiche d'un élève =====
@router.get("/users/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    subs = (
        db.query(SubscriptionDB)
        .filter(SubscriptionDB.user_id == user_id)
        .order_by(SubscriptionDB.created_at.desc())
        .all()
    )
    transactions = (
        db.query(TransactionDB)
        .filter(TransactionDB.user_id == user_id)
        .order_by(TransactionDB.created_at.desc())
        .limit(50)
        .all()
    )
    payments = (
        db.query(PaymentDB)
        .filter(PaymentDB.user_id == user_id)
        .order_by(PaymentDB.created_at.desc())
        .limit(50)
        .all()
    )
    sessions = (
        db.query(ExamSessionDB)
        .filter(ExamSessionDB.user_id == user_id)
        .order_by(ExamSessionDB.created_at.desc())
        .limit(20)
        .all()
    )
    completed = [s for s in sessions if s.status == "completed" and s.score is not None]
    mistakes_total = (
        db.query(func.count(UserMistakeDB.id))
        .filter(UserMistakeDB.user_id == user_id)
        .scalar()
        or 0
    )
    mistakes_mastered = (
        db.query(func.count(UserMistakeDB.id))
        .filter(UserMistakeDB.user_id == user_id, UserMistakeDB.mastered.is_(True))
        .scalar()
        or 0
    )

    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "created_at": user.created_at,
        "subscriptions": [_sub_payload(s) for s in subs],
        "current_subscription": _sub_payload(next((s for s in subs if _is_active(s)), subs[0] if subs else None)),
        "transactions": [
            {
                "id": t.id,
                "plan_id": t.plan_id,
                "plan_name": _plan_name(t.plan_id),
                "amount": t.amount,
                "currency": t.currency,
                "status": t.status,
                "created_at": t.created_at,
                "completed_at": t.completed_at,
            }
            for t in transactions
        ],
        "payments": [
            {
                "id": p.id,
                "order_id": p.order_id,
                "amount": p.amount,
                "currency": p.currency,
                "status": p.status,
                "created_at": p.created_at,
            }
            for p in payments
        ],
        "activity": {
            "exam_sessions": len(sessions),
            "completed_sessions": len(completed),
            "average_score": (
                round(sum(s.score for s in completed) / len(completed), 1) if completed else None
            ),
            "last_session_at": sessions[0].created_at if sessions else None,
            "mistakes_total": int(mistakes_total),
            "mistakes_mastered": int(mistakes_mastered),
        },
        "total_spent": round(
            sum(float(t.amount or 0) for t in transactions if t.status == "completed"), 2
        ),
    }


@router.patch("/users/{user_id}")
async def update_user(user_id: str, payload: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if payload.email and payload.email.lower() != (user.email or "").lower():
        exists = (
            db.query(UserDB)
            .filter(func.lower(UserDB.email) == payload.email.lower(), UserDB.id != user_id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail="Cet email est déjà utilisé")
        user.email = payload.email
    if payload.first_name is not None:
        user.first_name = payload.first_name.strip() or None
    if payload.last_name is not None:
        user.last_name = payload.last_name.strip() or None

    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


@router.post("/users/{user_id}/password")
async def reset_user_password(user_id: str, payload: PasswordReset, db: Session = Depends(get_db)):
    if len(payload.new_password or "") < 6:
        raise HTTPException(status_code=400, detail="Mot de passe trop court (6 caractères minimum)")
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    logger.info("CRM : mot de passe réinitialisé pour %s", user.email)
    return {"status": "ok"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, db: Session = Depends(get_db)):
    """Supprime un compte et les données personnelles associées (RGPD).

    Les transactions sont conservées (obligation comptable) mais détachées
    du compte supprimé.
    """
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    db.query(UserMistakeDB).filter(UserMistakeDB.user_id == user_id).delete(synchronize_session=False)
    db.query(ExamSessionDB).filter(ExamSessionDB.user_id == user_id).delete(synchronize_session=False)
    db.query(SubscriptionDB).filter(SubscriptionDB.user_id == user_id).delete(synchronize_session=False)
    db.query(TransactionDB).filter(TransactionDB.user_id == user_id).update(
        {TransactionDB.user_id: None}, synchronize_session=False
    )
    db.query(PaymentDB).filter(PaymentDB.user_id == user_id).update(
        {PaymentDB.user_id: None}, synchronize_session=False
    )
    email = user.email
    db.delete(user)
    db.commit()
    logger.warning("CRM : compte supprimé (%s)", email)
    return {"status": "deleted", "email": email}


# ===== Abonnements =====
@router.post("/users/{user_id}/subscriptions")
async def grant_subscription(
    user_id: str,
    payload: SubscriptionGrant,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Accorde manuellement un abonnement (offre commerciale, geste commercial,
    paiement encaissé hors plateforme) ou prolonge l'abonnement en cours."""
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    plan = PLANS.get(payload.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Formule inconnue : {payload.plan_id}")

    days = payload.duration_days or int(plan.get("duration_days") or 30)
    if days <= 0:
        raise HTTPException(status_code=400, detail="Durée invalide")

    now = datetime.utcnow()
    current = (
        db.query(SubscriptionDB)
        .filter(SubscriptionDB.user_id == user_id, SubscriptionDB.status == "active")
        .order_by(SubscriptionDB.created_at.desc())
        .first()
    )

    if not payload.start_now and current and _is_active(current, now):
        # Prolongation : on repousse la date de fin de l'abonnement actif.
        base = current.end_date or now
        current.end_date = base + timedelta(days=days)
        current.canceled_at = None
        db.add(current)
        db.commit()
        db.refresh(current)
        logger.info("CRM : abonnement %s prolongé de %s jours par %s", current.id, days, admin.email)
        return {"status": "extended", "subscription": _sub_payload(current)}

    # Nouvel abonnement : l'ancien actif est clos pour éviter les doublons.
    if current:
        current.status = "cancelled"
        current.canceled_at = now
        db.add(current)

    sub = SubscriptionDB(
        user_id=user_id,
        plan_id=payload.plan_id,
        start_date=now,
        end_date=now + timedelta(days=days),
        status="active",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    logger.info("CRM : abonnement %s accordé à %s par %s", payload.plan_id, user.email, admin.email)
    return {"status": "created", "subscription": _sub_payload(sub)}


@router.post("/subscriptions/{sub_id}/cancel")
async def cancel_subscription(sub_id: str, db: Session = Depends(get_db)):
    """Résilie un abonnement. L'accès reste valable jusqu'à sa date de fin."""
    sub = db.query(SubscriptionDB).filter(SubscriptionDB.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Abonnement introuvable")
    sub.status = "cancelled"
    sub.canceled_at = datetime.utcnow()
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return {"status": "cancelled", "subscription": _sub_payload(sub)}


# ===== Paiements =====
@router.get("/transactions")
async def list_transactions(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="pending / completed / failed …"),
    needs_account: bool = Query(
        False, description="Uniquement les paiements encaissés sans compte rattaché"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = db.query(TransactionDB)
    if status:
        query = query.filter(TransactionDB.status == status)
    if needs_account:
        # Paiement encaissé dont personne ne profite : aucun compte ne le porte.
        query = query.filter(
            TransactionDB.status == "completed", TransactionDB.user_id.is_(None)
        )
    total = query.count()
    rows = (
        query.order_by(TransactionDB.created_at.desc()).offset(offset).limit(limit).all()
    )

    user_ids = [t.user_id for t in rows if t.user_id]
    users = (
        {u.id: u for u in db.query(UserDB).filter(UserDB.id.in_(user_ids)).all()}
        if user_ids else {}
    )

    return {
        "items": [
            {
                "id": t.id,
                "user_id": t.user_id,
                # Sans compte rattaché, on affiche l'email saisi au paiement :
                # c'est la seule piste pour retrouver l'élève.
                "user_email": (
                    users.get(t.user_id).email if users.get(t.user_id)
                    else transaction_email(t)
                ),
                "has_account": bool(t.user_id),
                "needs_account": t.status == "completed" and not t.user_id,
                "plan_id": t.plan_id,
                "plan_name": _plan_name(t.plan_id),
                "amount": t.amount,
                "currency": t.currency,
                "status": t.status,
                "created_at": t.created_at,
                "completed_at": t.completed_at,
            }
            for t in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
    }


@router.post("/transactions/{transaction_id}/attach")
async def attach_transaction(
    transaction_id: str,
    payload: TransactionAttach,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Rattache un paiement encaissé à un compte élève et ouvre son abonnement.

    Sert quand un élève a payé mais ne peut pas entrer : soit le compte n'existe
    pas encore (il est créé ici, avec un mot de passe provisoire à lui
    communiquer), soit il existe déjà et le paiement lui est simplement affecté.
    """
    transaction = db.query(TransactionDB).filter(TransactionDB.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Paiement introuvable")
    if transaction.user_id:
        raise HTTPException(status_code=409, detail="Ce paiement est déjà rattaché à un compte")
    if transaction.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Paiement non encaissé (statut : {transaction.status})",
        )

    email = normalize_email(payload.email)
    user = find_user_by_email(db, email)
    temporary_password = None
    if not user:
        temporary_password = payload.password or secrets.token_urlsafe(9)
        user = UserDB(
            email=email,
            hashed_password=hash_password(temporary_password),
            first_name=(payload.first_name or "").strip() or None,
            last_name=(payload.last_name or "").strip() or None,
        )
        db.add(user)
        db.flush()
    elif payload.password:
        user.hashed_password = hash_password(payload.password)
        temporary_password = payload.password
        db.add(user)

    transaction.user_id = user.id
    event_data = dict(transaction.event_data or {})
    event_data.update({
        "needs_account": False,
        "attached_by": admin.email,
        "attached_at": datetime.utcnow().isoformat(),
    })
    event_data.setdefault("user_email", email)
    transaction.event_data = event_data

    subscription = provision_subscription(db, transaction)
    db.commit()

    logger.info("CRM : paiement %s rattaché à %s par %s", transaction.id, email, admin.email)
    return {
        "status": "ok",
        "user": {"id": user.id, "email": user.email},
        # Renvoyé une seule fois, à transmettre à l'élève : il pourra le changer.
        "temporary_password": temporary_password,
        "subscription": _sub_payload(subscription),
    }


# ===== Codes promo =====
def _validate_promo_payload(discount_type: str, discount_value: float) -> None:
    if discount_type not in promo_lib.DISCOUNT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Type de remise invalide : {discount_type} (attendu : percent, amount ou free)",
        )
    if discount_type == "percent" and not (0 < discount_value <= 100):
        raise HTTPException(status_code=400, detail="Le pourcentage doit être compris entre 1 et 100")
    if discount_type == "amount" and discount_value <= 0:
        raise HTTPException(status_code=400, detail="Le montant de la remise doit être positif")


@router.get("/promo-codes")
async def list_promo_codes(db: Session = Depends(get_db)):
    codes = db.query(PromoCodeDB).order_by(PromoCodeDB.created_at.desc()).all()
    total_redemptions = (
        db.query(func.count(PromoRedemptionDB.id)).scalar() or 0
    )
    total_discount = (
        db.query(func.coalesce(func.sum(PromoRedemptionDB.discount_amount), 0.0)).scalar() or 0.0
    )
    return {
        "items": [promo_lib.payload(c) for c in codes],
        "total": len(codes),
        "total_redemptions": int(total_redemptions),
        "total_discount_granted": round(float(total_discount), 2),
    }


@router.post("/promo-codes")
async def create_promo_code(
    payload: PromoCodeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    code = promo_lib.normalize(payload.code)
    if len(code) < 3:
        raise HTTPException(status_code=400, detail="Le code doit faire au moins 3 caractères")
    _validate_promo_payload(payload.discount_type, payload.discount_value)

    if db.query(PromoCodeDB).filter(PromoCodeDB.code == code).first():
        raise HTTPException(status_code=409, detail=f"Le code {code} existe déjà")

    unknown = [p for p in payload.plan_ids if p not in PLANS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Formules inconnues : {', '.join(unknown)}")

    promo = PromoCodeDB(
        code=code,
        description=payload.description,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        plan_ids=payload.plan_ids,
        max_uses=payload.max_uses,
        max_uses_per_user=payload.max_uses_per_user,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        active=payload.active,
        created_by=admin.email,
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    logger.info("CRM : code promo %s créé par %s", code, admin.email)
    return promo_lib.payload(promo)


@router.patch("/promo-codes/{promo_id}")
async def update_promo_code(promo_id: str, payload: PromoCodeUpdate, db: Session = Depends(get_db)):
    promo = db.query(PromoCodeDB).filter(PromoCodeDB.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Code promo introuvable")

    if payload.discount_type is not None or payload.discount_value is not None:
        _validate_promo_payload(
            payload.discount_type or promo.discount_type,
            payload.discount_value if payload.discount_value is not None else promo.discount_value,
        )
    if payload.plan_ids is not None:
        unknown = [p for p in payload.plan_ids if p not in PLANS]
        if unknown:
            raise HTTPException(status_code=400, detail=f"Formules inconnues : {', '.join(unknown)}")

    for field in (
        "description", "discount_type", "discount_value", "plan_ids",
        "max_uses", "max_uses_per_user", "valid_from", "valid_until", "active",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(promo, field, value)

    db.add(promo)
    db.commit()
    db.refresh(promo)
    return promo_lib.payload(promo)


@router.delete("/promo-codes/{promo_id}")
async def delete_promo_code(promo_id: str, db: Session = Depends(get_db)):
    promo = db.query(PromoCodeDB).filter(PromoCodeDB.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Code promo introuvable")
    # L'historique d'utilisation est conservé (suivi commercial) ; il référence
    # le code par sa valeur textuelle en plus de son identifiant.
    code = promo.code
    db.delete(promo)
    db.commit()
    logger.info("CRM : code promo %s supprimé", code)
    return {"status": "deleted", "code": code}


@router.get("/promo-codes/{promo_id}/redemptions")
async def promo_redemptions(promo_id: str, db: Session = Depends(get_db)):
    promo = db.query(PromoCodeDB).filter(PromoCodeDB.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Code promo introuvable")
    rows = (
        db.query(PromoRedemptionDB)
        .filter(PromoRedemptionDB.promo_code_id == promo_id)
        .order_by(PromoRedemptionDB.created_at.desc())
        .limit(200)
        .all()
    )
    return {
        "code": promo.code,
        "items": [
            {
                "id": r.id,
                "user_email": r.user_email,
                "plan_id": r.plan_id,
                "plan_name": _plan_name(r.plan_id),
                "original_amount": r.original_amount,
                "discount_amount": r.discount_amount,
                "final_amount": r.final_amount,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


@router.get("/plans")
async def list_plans():
    """Catalogue des formules (pour le sélecteur d'abonnement du CRM)."""
    return {
        "plans": [
            {
                "plan_id": pid,
                "name": p.get("name"),
                "amount": p.get("amount"),
                "currency": p.get("currency"),
                "duration_days": p.get("duration_days"),
                "type": p.get("type"),
            }
            for pid, p in PLANS.items()
        ]
    }
