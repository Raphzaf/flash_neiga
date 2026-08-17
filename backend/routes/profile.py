"""
Profil utilisateur (Flash Neiga).

Tout ce qu'un élève gère lui-même sur son compte :

- GET   /api/profile                       → infos du compte + abonnement courant
- PATCH /api/profile                       → modifier prénom / nom
- POST  /api/profile/password              → changer son mot de passe
- POST  /api/profile/email                 → changer son email de connexion
- GET   /api/profile/payments              → historique de ses paiements
- POST  /api/profile/subscription/cancel   → résilier (ne pas renouveler) l'abonnement

Souscrire, changer de formule ou renouveler passe par le tunnel d'abonnement
(/subscribe → /checkout → paiement) : c'est l'élève qui décide, jamais un
administrateur. La résiliation marque l'abonnement comme annulé ; l'accès reste
ouvert jusqu'à sa date de fin, puisqu'il est déjà payé.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pydantic import BaseModel, EmailStr

try:
    from database import get_db
    from models import UserDB, SubscriptionDB, TransactionDB, User, ProfileUpdate
    from auth import (
        get_current_user, current_subscription, hash_password, verify_password,
        validate_password, normalize_email, find_user_by_email, validate_phone,
    )
except ImportError:  # pragma: no cover
    from backend.database import get_db
    from backend.models import UserDB, SubscriptionDB, TransactionDB, User, ProfileUpdate
    from backend.auth import (
        get_current_user, current_subscription, hash_password, verify_password,
        validate_password, normalize_email, find_user_by_email, validate_phone,
    )


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class EmailChange(BaseModel):
    """Le mot de passe est exigé : l'email est l'identifiant de connexion."""
    new_email: EmailStr
    current_password: str

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])

PLANS_FILE = Path(__file__).parent.parent.parent / "hyp_plans.json"
try:
    with open(PLANS_FILE, "r", encoding="utf-8") as f:
        PLANS: Dict[str, Any] = json.load(f)
except Exception:  # pragma: no cover
    PLANS = {}


def _active_subscription(db: Session, user_id: str) -> Optional[SubscriptionDB]:
    """Abonnement en cours de l'élève, sinon le plus récent (pour l'historique)."""
    active = current_subscription(db, user_id)
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
    # Un abonnement résilié reste valable jusqu'à sa date de fin : il est déjà payé.
    is_active = sub.status in ("active", "cancelled") and (sub.end_date is None or sub.end_date > now)
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
        "days_left": (
            max(0, (sub.end_date - now).days) if (is_active and sub.end_date) else None
        ),
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
        "phone": user.phone,
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
    if payload.phone is not None:
        user.phone = validate_phone(payload.phone)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
    }


@router.post("/password")
async def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change le mot de passe, l'ancien faisant office de confirmation d'identité."""
    user = db.query(UserDB).filter(UserDB.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=403, detail="Mot de passe actuel incorrect.")

    new_password = validate_password(payload.new_password)
    if verify_password(new_password, user.hashed_password):
        raise HTTPException(
            status_code=400, detail="Le nouveau mot de passe doit être différent de l'ancien."
        )

    user.hashed_password = hash_password(new_password)
    db.commit()
    logger.info("Mot de passe modifié par l'élève %s", user.email)
    return {"status": "ok", "message": "Ton mot de passe a été modifié."}


@router.post("/email")
async def change_email(
    payload: EmailChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change l'email de connexion.

    Le mot de passe est exigé : cet email est l'identifiant du compte, et la
    session reste ouverte ensuite (le jeton porte l'identifiant interne).
    """
    user = db.query(UserDB).filter(UserDB.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=403, detail="Mot de passe incorrect.")

    new_email = normalize_email(payload.new_email)
    if new_email == normalize_email(user.email):
        raise HTTPException(status_code=400, detail="C'est déjà ton email actuel.")

    existing = find_user_by_email(db, new_email)
    if existing and existing.id != user.id:
        raise HTTPException(status_code=409, detail="Cet email est déjà utilisé par un autre compte.")

    previous = user.email
    user.email = new_email
    db.commit()
    logger.info("Email du compte %s changé en %s", previous, new_email)
    return {"status": "ok", "email": new_email, "message": "Ton email de connexion a été mis à jour."}


@router.get("/payments")
async def list_my_payments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Historique des paiements de l'élève : ce qu'il a payé, quand, pour quoi."""
    transactions = (
        db.query(TransactionDB)
        .filter(TransactionDB.user_id == current_user.id, TransactionDB.status == "completed")
        .order_by(TransactionDB.created_at.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": t.id,
                "reference": t.id[:8],
                "plan_id": t.plan_id,
                "plan_name": (PLANS.get(t.plan_id or "", {}) or {}).get("name") or t.plan_id,
                "amount": t.amount,
                "currency": t.currency,
                "paid_at": t.completed_at or t.created_at,
            }
            for t in transactions
        ],
        "count": len(transactions),
    }


@router.post("/subscription/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = current_subscription(db, current_user.id)
    if not sub or sub.status != "active":
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
