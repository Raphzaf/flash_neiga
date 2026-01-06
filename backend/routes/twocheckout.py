# backend/routes/twocheckout.py

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import os
import hmac
import hashlib
import base64
import json
import logging
from urllib.parse import urlencode
from datetime import datetime

# Import database dependencies
try:
    from database import get_db
    from models import PaymentDB, SubscriptionDB
except ImportError:
    from backend.database import get_db
    from backend.models import PaymentDB, SubscriptionDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["payments", "2checkout"])

# === Env helpers ===

def _env(name: str) -> Optional[str]:
    v = os.getenv(name)
    return v.strip() if v else None

MERCHANT_CODE = _env("VERIFONE_MERCHANT_CODE")
SECRET_KEY = _env("VERIFONE_SECRET_KEY")
SECRET_WORD = _env("VERIFONE_SECRET_WORD")

# === Buy-link helper (Hosted Checkout) ===

def build_buy_link(
    product_id: int,
    currency: str,
    quantity: int = 1,
    name: Optional[str] = None,
    return_url: Optional[str] = None,
    customer_email: Optional[str] = None,
    lang: str = "fr",
    test: bool = False,
) -> str:
    """
    Construct a Verifone/2Checkout hosted checkout link using preconfigured product.
    Uses dynamic line item params and merchant code.
    """
    if not MERCHANT_CODE:
        raise ValueError("VERIFONE_MERCHANT_CODE is not set")

    params = {
        "merchant": MERCHANT_CODE,
        "li_0_type": "product",
        "li_0_product_id": product_id,
        "li_0_name": name or "Flash Neiga Subscription",
        "li_0_quantity": quantity,
        "currency": currency,
        "lang": lang,
    }
    if return_url:
        params["return-url"] = return_url
    if customer_email:
        params["customer-email"] = customer_email
    if test:
        params["test"] = "true"

    base = "https://secure.2checkout.com/checkout/purchase"
    return f"{base}?{urlencode(params)}"


# === Request/Response Schemas ===

class CreateOrderRequest(BaseModel):
    productId: int
    currency: str
    quantity: int = 1
    name: Optional[str] = None
    email: Optional[str] = None
    returnUrl: Optional[str] = None
    lang: Optional[str] = "fr"
    test: Optional[bool] = False

class CreateOrderResponse(BaseModel):
    checkoutUrl: str


# === Signature verification (IPN/LCN) ===

def verify_webhook_hmac(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """Verify HMAC-SHA256 signature from Verifone webhook.

    Verifone sends 'X-Avangate-Webhook-Signature' = base64(HMAC_SHA256(secret_word, raw_body)).
    """
    if not SECRET_WORD or not signature_header:
        return False
    try:
        expected = hmac.new(SECRET_WORD.encode("utf-8"), raw_body, hashlib.sha256).digest()
        provided = base64.b64decode(signature_header)
        return hmac.compare_digest(expected, provided)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


# === Endpoints ===

@router.post("/payments/2checkout/create", response_model=CreateOrderResponse)
async def create_2checkout_order(req: CreateOrderRequest):
    """Create a Hosted Checkout buy-link for a preconfigured product.
    Returns the checkout URL to redirect the customer.
    """
    try:
        url = build_buy_link(
            product_id=req.productId,
            currency=req.currency,
            quantity=req.quantity,
            name=req.name,
            return_url=req.returnUrl,
            customer_email=req.email,
            lang=req.lang or "fr",
            test=bool(req.test),
        )
        return CreateOrderResponse(checkoutUrl=url)
    except Exception as e:
        logger.error(f"Failed to create buy-link: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhooks/2checkout/ipn")
async def twocheckout_ipn(request: Request, db: Session = Depends(get_db)):
    """IPN: Payment notifications for orders/payments.
    Verifies HMAC signature and stores payment event.
    """
    raw = await request.body()
    sig = request.headers.get("X-Avangate-Webhook-Signature")
    if not verify_webhook_hmac(raw, sig):
        # Return 403 if signature invalid
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        payload = json.loads(raw.decode("utf-8")) if raw else {}

    try:
        # Example IPN fields mapping (adjust based on exact payload):
        order_id = payload.get("orderId") or payload.get("sale_id")
        status = payload.get("status") or payload.get("order_status") or "received"
        currency = payload.get("currency") or payload.get("orderCurrency")
        amount = None
        if "amount" in payload:
            try:
                amount = float(payload.get("amount"))
            except Exception:
                amount = None
        product_id = None
        items = payload.get("items") or payload.get("lineItems") or []
        if isinstance(items, list) and items:
            # Take first item product_id if present
            product_id = items[0].get("productId") or items[0].get("product_id")

        payment = PaymentDB(
            order_id=order_id,
            product_id=product_id,
            amount=amount,
            currency=currency,
            status=status,
            event_type="ipn",
            event_data=payload,
        )
        db.add(payment)
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing IPN: {e}", exc_info=True)
        db.rollback()
        # Return 200 to avoid repeated retries if desired
        return {"status": "error", "message": str(e)}


@router.post("/webhooks/2checkout/lcn")
async def twocheckout_lcn(request: Request, db: Session = Depends(get_db)):
    """LCN: License/subscription change notifications.
    Verifies HMAC signature and updates subscription records.
    """
    raw = await request.body()
    sig = request.headers.get("X-Avangate-Webhook-Signature")
    if not verify_webhook_hmac(raw, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        payload = json.loads(raw.decode("utf-8")) if raw else {}

    try:
        # Example LCN fields mapping (adjust to your payload):
        license_id = payload.get("licenseId") or payload.get("subscriptionId")
        product_id = payload.get("productId") or payload.get("product_id")
        status = payload.get("status") or "active"
        next_renewal_raw = payload.get("nextRenewal") or payload.get("next_renewal")
        next_renewal = None
        if next_renewal_raw:
            try:
                next_renewal = datetime.fromisoformat(next_renewal_raw.replace("Z", "+00:00"))
            except Exception:
                next_renewal = None
        canceled_at = None
        canceled_raw = payload.get("canceledAt") or payload.get("cancelled_at")
        if canceled_raw:
            try:
                canceled_at = datetime.fromisoformat(canceled_raw.replace("Z", "+00:00"))
            except Exception:
                canceled_at = None

        # Upsert subscription by license_id
        sub = db.query(SubscriptionDB).filter(SubscriptionDB.license_id == license_id).first()
        if sub:
            sub.status = status
            sub.product_id = product_id
            sub.next_renewal = next_renewal
            sub.canceled_at = canceled_at
        else:
            sub = SubscriptionDB(
                license_id=license_id,
                product_id=product_id,
                status=status,
                next_renewal=next_renewal,
                canceled_at=canceled_at,
            )
            db.add(sub)
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing LCN: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "message": str(e)}
