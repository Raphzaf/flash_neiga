# backend/routes/verifone_payments.py

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import os
import hmac
import hashlib
import json
import logging
from urllib.parse import urlencode

# Import database dependencies
try:
    from database import get_db
    from models import TransactionDB
except ImportError:
    from backend.database import get_db
    from backend.models import TransactionDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments/verifone", tags=["payments", "verifone"])

# === Helpers ===

def _env_str(name: str) -> Optional[str]:
    v = os.getenv(name)
    return v.strip() if v else None


def _build_buy_link(
    merchant_code: str,
    secret_key: Optional[str],
    amount: float,
    currency: str,
    name: Optional[str] = None,
    return_url: Optional[str] = None,
    customer_email: Optional[str] = None,
    test: bool = False,
    product_id: Optional[int] = None,
    lang: Optional[str] = "fr",
) -> str:
    """Construct a Verifone/2Checkout hosted checkout link using dynamic line item params.

    Uses recommended "li_0_*" parameters for a single product and avoids non-standard signature.
    Note: For production hardening, implement Verifone's official buy-link signature per docs.
    """
    params = {
        "merchant": merchant_code,
        # Dynamic line item (single product)
        "li_0_type": "product",
        "li_0_name": name or "Flash Neiga Subscription",
        "li_0_price": f"{amount:.2f}",
        "li_0_quantity": 1,
        "currency": currency,
    }
    if product_id:
        params["li_0_product_id"] = product_id
    if return_url:
        # Verifone uses dash in param name
        params["return-url"] = return_url
    if customer_email:
        params["customer-email"] = customer_email
    if test:
        params["test"] = "true"
    if lang:
        params["lang"] = lang

    # Do NOT include ad-hoc signature; use official method if required
    base = "https://secure.2checkout.com/checkout/purchase"
    return f"{base}?{urlencode(params)}"


# === Schemas ===

class CheckoutRequest(BaseModel):
    amount: float
    currency: str
    name: Optional[str] = None
    productId: Optional[int] = None
    email: Optional[str] = None
    returnUrl: Optional[str] = None
    test: Optional[bool] = False
    lang: Optional[str] = "fr"


class CheckoutResponse(BaseModel):
    checkoutUrl: str


# === Endpoints ===

@router.get("/health")
async def verifone_health():
    merchant = _env_str("VERIFONE_MERCHANT_CODE")
    secret = _env_str("VERIFONE_SECRET_KEY")
    return {"configured": bool(merchant), "has_secret": bool(secret)}


@router.post("/create-checkout", response_model=CheckoutResponse)
async def create_verifone_checkout(req: CheckoutRequest, db: Session = Depends(get_db)):
    merchant = _env_str("VERIFONE_MERCHANT_CODE")
    secret = _env_str("VERIFONE_SECRET_KEY")

    if not merchant:
        raise HTTPException(status_code=400, detail="Verifone not configured: set VERIFONE_MERCHANT_CODE env var")

    try:
        link = _build_buy_link(
            merchant_code=merchant,
            secret_key=secret,
            amount=req.amount,
            currency=req.currency,
            name=req.name,
            return_url=req.returnUrl,
            customer_email=req.email,
            test=bool(req.test),
            product_id=req.productId,
            lang=req.lang,
        )
        return CheckoutResponse(checkoutUrl=link)
    except Exception as e:
        logger.error(f"Error creating Verifone checkout: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/webhook")
async def verifone_webhook(request: Request):
    """Désactivé : Verifone n'est plus le prestataire de paiement (c'est HYP).

    Ce point d'entrée enregistrait n'importe quelle requête comme un paiement,
    sans aucune vérification de signature : des « paiements » inventés
    faussaient le chiffre d'affaires, et le balayage de facturation aurait pu
    leur émettre de vraies factures numérotées. Rien n'est plus enregistré.
    """
    logger.warning("Webhook Verifone reçu alors qu'il est désactivé — ignoré.")
    raise HTTPException(status_code=410, detail="Verifone n'est plus utilisé : webhook désactivé.")
