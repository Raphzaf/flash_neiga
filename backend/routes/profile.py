"""
Profil utilisateur (Flash Neiga).

- GET  /api/profile                       → infos du compte + abonnement courant
- PATCH /api/profile                      → modifier prénom / nom
- POST /api/profile/subscription/cancel   → résilier (ne pas renouveler) l'abonnement actif

« Passer à un abonnement supérieur » se fait via la page Tarifs (flux de paiement HYP) :
le front y renvoie l'utilisateur. La résiliation marque l'abonnement comme annulé côté
application ; l'accès reste valable jusqu'à sa date de fin (plans à durée déterminée).
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

try:
    from database import get_db
    from models import UserDB, SubscriptionDB, User, ProfileUpdate
    from auth import get_current_user
except ImportError:  # pragma: no cover
    from backend.database import get_db
    from backend.models import UserDB, SubscriptionDB, User, ProfileUpdate
    from backend.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])

PLANS_FILE = Path(__file__).parent.parent.parent / "hyp_plans.json"
try:
    with open(PLANS_FILE, "r", encoding="utf-8") as f:
        PLANS: Dict[str, Any] = json.load(f)
except Exception:  # pragma: no cover
    PLANS = {}


def _active_subscription(db: Session, user_id: str) -> Optional[SubscriptionDB]:
    """Abonnement actif de l'élève, sinon le plus récent (pour l'historique)."""
    active = (
        db.query(SubscriptionDB)
        .filter(SubscriptionDB.user_id == user_id, SubscriptionDB.status == "active")
        .order_by(SubscriptionDB.created_at.desc())
        .first()
    )
    if active:
        return active
    return (
        db.query(SubscriptionDB)
        .filter(SubscriptionDB.user_id == user_id)
        .order_by(SubscriptionDB.created_at.desc())
        .first()
    )


def _subscription_payload(sub: Optional[SubscriptionDB]) -> Optional[Dict[str, Any]]:
    if not sub:
        return None
    plan = PLANS.get(sub.plan_id or "", {})
    now = datetime.utcnow()
    is_active = sub.status == "active" and (sub.end_date is None or sub.end_date > now)
    return {
        "plan_id": sub.plan_id,
        "plan_name": plan.get("name") or sub.plan_id or "Abonnement",
        "plan_description": plan.get("description"),
        "amount": plan.get("amount"),
        "currency": plan.get("currency"),
        "status": sub.status,
        "is_active": is_active,
        "start_date": sub.start_date,
        "end_date": sub.end_date,
        "canceled_at": sub.canceled_at,
    }


@router.get("")
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(UserDB).filter(UserDB.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    sub = _active_subscription(db, user.id)
    sub_payload = _subscription_payload(sub)
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "created_at": user.created_at,
        "subscription": sub_payload,
        "has_active_subscription": bool(sub_payload and sub_payload["is_active"]),
    }


@router.patch("")
async def update_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(UserDB).filter(UserDB.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if payload.first_name is not None:
        user.first_name = payload.first_name.strip() or None
    if payload.last_name is not None:
        user.last_name = payload.last_name.strip() or None
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


@router.post("/subscription/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(SubscriptionDB)
        .filter(SubscriptionDB.user_id == current_user.id, SubscriptionDB.status == "active")
        .order_by(SubscriptionDB.created_at.desc())
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Aucun abonnement actif à résilier.")

    sub.status = "cancelled"
    sub.canceled_at = datetime.utcnow()
    db.commit()
    db.refresh(sub)
    return {
        "status": "cancelled",
        "message": "Ton abonnement ne sera pas renouvelé. Tu gardes l'accès jusqu'à sa date de fin.",
        "end_date": sub.end_date,
    }
