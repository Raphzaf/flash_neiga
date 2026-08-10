"""
Codes promotionnels (Flash Neiga).

Logique partagée entre le CRM (création/pilotage) et le tunnel de paiement
(validation puis application de la remise). Le calcul du montant final est fait
**côté serveur uniquement** : le client n'envoie qu'un code, jamais un prix.

Trois types de remise :
  - percent : pourcentage (0-100)
  - amount  : montant fixe en devise du plan
  - free    : accès offert (montant final = 0, aucun paiement)
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

try:
    from models import PromoCodeDB, PromoRedemptionDB
except ImportError:  # pragma: no cover
    from backend.models import PromoCodeDB, PromoRedemptionDB

__all__ = [
    "PromoCodeDB", "PromoRedemptionDB", "PromoError", "DISCOUNT_TYPES",
    "normalize", "compute_discount", "validate", "redeem", "payload",
]

logger = logging.getLogger(__name__)

DISCOUNT_TYPES = ("percent", "amount", "free")


class PromoError(Exception):
    """Code promo refusé — le message est destiné à l'élève."""


def normalize(code: str) -> str:
    return (code or "").strip().upper()


def compute_discount(promo: PromoCodeDB, amount: float) -> Tuple[float, float]:
    """Renvoie (remise, montant_final), bornés à [0, amount]."""
    amount = float(amount or 0)
    if promo.discount_type == "free":
        return amount, 0.0
    if promo.discount_type == "percent":
        discount = amount * (float(promo.discount_value or 0) / 100.0)
    else:  # amount
        discount = float(promo.discount_value or 0)
    discount = max(0.0, min(discount, amount))
    return round(discount, 2), round(amount - discount, 2)


def validate(
    db: Session,
    code: str,
    plan_id: str,
    amount: float,
    user_id: Optional[str] = None,
) -> Tuple[PromoCodeDB, float, float]:
    """Valide un code pour un plan et un montant donnés.

    Renvoie (promo, remise, montant_final) ou lève PromoError avec un message
    lisible par l'élève.
    """
    normalized = normalize(code)
    if not normalized:
        raise PromoError("Aucun code saisi.")

    promo = db.query(PromoCodeDB).filter(PromoCodeDB.code == normalized).first()
    if not promo:
        raise PromoError("Ce code promo n'existe pas.")
    if not promo.active:
        raise PromoError("Ce code promo n'est plus actif.")

    now = datetime.utcnow()
    if promo.valid_from and now < promo.valid_from:
        raise PromoError("Ce code promo n'est pas encore valable.")
    if promo.valid_until and now > promo.valid_until:
        raise PromoError("Ce code promo a expiré.")

    if promo.max_uses is not None and (promo.used_count or 0) >= promo.max_uses:
        raise PromoError("Ce code promo a atteint son nombre maximum d'utilisations.")

    if promo.plan_ids and plan_id not in promo.plan_ids:
        raise PromoError("Ce code promo ne s'applique pas à cette formule.")

    if user_id and promo.max_uses_per_user:
        already = (
            db.query(PromoRedemptionDB)
            .filter(
                PromoRedemptionDB.promo_code_id == promo.id,
                PromoRedemptionDB.user_id == user_id,
            )
            .count()
        )
        if already >= promo.max_uses_per_user:
            raise PromoError("Tu as déjà utilisé ce code promo.")

    discount, final_amount = compute_discount(promo, amount)
    return promo, discount, final_amount


def redeem(
    db: Session,
    promo: PromoCodeDB,
    plan_id: str,
    original_amount: float,
    discount: float,
    final_amount: float,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    transaction_id: Optional[str] = None,
) -> PromoRedemptionDB:
    """Enregistre l'utilisation et incrémente le compteur. Ne commit pas."""
    promo.used_count = (promo.used_count or 0) + 1
    redemption = PromoRedemptionDB(
        promo_code_id=promo.id,
        code=promo.code,
        user_id=user_id,
        user_email=user_email,
        transaction_id=transaction_id,
        plan_id=plan_id,
        original_amount=original_amount,
        discount_amount=discount,
        final_amount=final_amount,
    )
    db.add(promo)
    db.add(redemption)
    logger.info(
        "Code promo %s utilisé (%s → %s) par %s",
        promo.code, original_amount, final_amount, user_email or user_id or "anonyme",
    )
    return redemption


def payload(promo: PromoCodeDB) -> Dict[str, Any]:
    """Représentation JSON d'un code, pour le CRM."""
    now = datetime.utcnow()
    expired = bool(promo.valid_until and now > promo.valid_until)
    exhausted = bool(promo.max_uses is not None and (promo.used_count or 0) >= promo.max_uses)
    return {
        "id": promo.id,
        "code": promo.code,
        "description": promo.description,
        "discount_type": promo.discount_type,
        "discount_value": promo.discount_value,
        "label": (
            "Accès offert" if promo.discount_type == "free"
            else f"-{int(promo.discount_value)} %" if promo.discount_type == "percent"
            else f"-{promo.discount_value} ₪"
        ),
        "plan_ids": promo.plan_ids or [],
        "max_uses": promo.max_uses,
        "max_uses_per_user": promo.max_uses_per_user,
        "used_count": promo.used_count or 0,
        "valid_from": promo.valid_from,
        "valid_until": promo.valid_until,
        "active": promo.active,
        "is_usable": bool(promo.active and not expired and not exhausted),
        "status": (
            "inactif" if not promo.active
            else "expiré" if expired
            else "épuisé" if exhausted
            else "actif"
        ),
        "created_at": promo.created_at,
        "created_by": promo.created_by,
    }
