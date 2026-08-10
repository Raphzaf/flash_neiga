# backend/routes/hyp_payments.py
"""
HYP Payment Integration
Intégration avec la plateforme de paiement israélienne HYP
Documentation: https://developers.hyp.co.il/
"""

from fastapi import APIRouter, HTTPException, Request, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import os
import json
import logging
import requests
from urllib.parse import parse_qsl
from pathlib import Path

# Support imports both when running from backend/ and from repo root
try:
    from database import get_db
except ImportError:
    from backend.database import get_db

try:
    from models import TransactionDB, SubscriptionDB, UserDB
    import promo as promo_lib
except ImportError:
    from backend.models import TransactionDB, SubscriptionDB, UserDB
    from backend import promo as promo_lib

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments/hyp", tags=["HYP Payments"])

# HYP Configuration
# HYP (Yaad Sarig) uses two credentials for the APISign flow:
#   - KEY   : the API signing key           -> HYP_API_KEY
#   - PassP : the terminal API password      -> HYP_PASSP (optional on some terminals)
#   - Masof : the terminal number            -> HYP_TERMINAL_ID
HYP_TERMINAL_ID = os.environ.get("HYP_TERMINAL_ID", "4502176330")
HYP_USER_ID = os.environ.get("HYP_USER_ID", "pveda")
HYP_API_KEY = os.environ.get("HYP_API_KEY", "")
HYP_PASSP = os.environ.get("HYP_PASSP", "")
HYP_API_URL = os.environ.get("HYP_API_URL", "https://icom.yaad.net/p/")
HYP_PAGE_LANG = os.environ.get("HYP_PAGE_LANG", "ENG")  # HYP supports HEB or ENG
# Les notifications de paiement non signées sont rejetées. Activé par défaut :
# sans cette vérification, une fausse notification suffirait à ouvrir un
# abonnement sans paiement. À ne désactiver qu'en développement local.
HYP_REQUIRE_SIGNATURE = os.environ.get("HYP_REQUIRE_SIGNATURE", "true").lower() in ("1", "true", "yes")
HYP_SUCCESS_URL = os.environ.get("HYP_SUCCESS_URL", "https://app.flash-neiga.com/payment/success")
HYP_ERROR_URL = os.environ.get("HYP_ERROR_URL", "https://app.flash-neiga.com/payment/failure")
HYP_CALLBACK_URL = os.environ.get("HYP_CALLBACK_URL", "http://localhost:8000/api/payments/hyp/callback")

# HYP currency code (Coin) mapping
CURRENCY_TO_COIN = {"ILS": 1, "NIS": 1, "USD": 2, "EUR": 3, "GBP": 4}

# Load HYP plans configuration
PLANS_FILE = Path(__file__).parent.parent.parent / "hyp_plans.json"
try:
    with open(PLANS_FILE, "r", encoding="utf-8") as f:
        HYP_PLANS = json.load(f)
    logger.info(f"Loaded {len(HYP_PLANS)} HYP plans from {PLANS_FILE}")
except Exception as e:
    logger.error(f"Failed to load HYP plans from {PLANS_FILE}: {e}")
    HYP_PLANS = {}


# ===== Request/Response Models =====
class CreatePaymentRequest(BaseModel):
    plan_id: str
    user_id: Optional[str] = None
    user_email: Optional[EmailStr] = None
    promo_code: Optional[str] = None


class CreatePaymentResponse(BaseModel):
    payment_url: Optional[str] = None
    transaction_id: str
    plan_id: str
    amount: float
    currency: str
    # Renseignés quand un code promo s'applique
    original_amount: Optional[float] = None
    discount_amount: Optional[float] = None
    promo_code: Optional[str] = None
    # True quand la remise couvre 100 % : aucun paiement, accès activé directement
    free: bool = False


class ValidatePromoRequest(BaseModel):
    code: str
    plan_id: str
    user_id: Optional[str] = None


class CallbackData(BaseModel):
    """Model for HYP callback data"""
    Id: Optional[str] = None
    CCode: Optional[str] = None
    Amount: Optional[str] = None
    ACode: Optional[str] = None
    Order: Optional[str] = None
    Coin: Optional[int] = None
    UserId: Optional[str] = None


# ===== Helper Functions =====
def get_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    """Get plan details from configuration"""
    return HYP_PLANS.get(plan_id)


def calculate_subscription_dates(plan_id: str, start_date: Optional[datetime] = None) -> tuple:
    """Calculate subscription start and end dates based on plan"""
    plan = get_plan(plan_id)
    if not plan:
        raise ValueError(f"Plan not found: {plan_id}")
    
    if start_date is None:
        start_date = datetime.utcnow()
    
    duration_days = plan.get("duration_days", 30)
    end_date = start_date + timedelta(days=duration_days)
    
    return start_date, end_date


def _hyp_coin(currency: str) -> int:
    """Map an ISO currency code to the HYP `Coin` code (defaults to ILS)."""
    return CURRENCY_TO_COIN.get((currency or "ILS").upper(), 1)


def _hyp_base_params() -> Dict[str, str]:
    """Common authentication parameters for APISign requests."""
    params = {
        "KEY": HYP_API_KEY,
        "Masof": HYP_TERMINAL_ID,
    }
    # PassP is required by some terminals and unused by others; only send it when
    # configured so we don't break terminals that sign with KEY + Masof alone.
    if HYP_PASSP:
        params["PassP"] = HYP_PASSP
    return params


def _build_sign_params(
    order: str,
    amount: float,
    currency: str = "ILS",
    info: str = "Flash Neiga",
    user_email: Optional[str] = None,
) -> Dict[str, str]:
    """Build the parameter set for an APISign SIGN request (shared by the payment
    URL builder and the /test-connection diagnostic)."""
    amount_value = float(amount)
    amount_str = str(int(amount_value)) if amount_value.is_integer() else f"{amount_value:.2f}"

    params = {
        "action": "APISign",
        "What": "SIGN",
        "Sign": "True",
        "Amount": amount_str,
        "Coin": str(_hyp_coin(currency)),
        "Order": order,
        "Info": info,
        "Tash": "1",
        "UTF8": "True",
        "UTF8out": "True",
        "PageLang": HYP_PAGE_LANG,
        "sendemail": "True",
        "MoreData": "True",
    }
    params.update(_hyp_base_params())
    if user_email:
        params["email"] = user_email
    return params


def create_hyp_payment_url(
    transaction_id: str,
    amount: float,
    currency: str = "ILS",
    user_email: Optional[str] = None,
    info: str = "Flash Neiga",
) -> str:
    """
    Create a HYP (Yaad Sarig) hosted payment-page URL using the official APISign flow.

    Documentation: https://developers.hyp.co.il/

    Flow:
      1. GET <HYP_API_URL>?action=APISign&What=SIGN&... which returns a URL-encoded
         query string containing every input parameter plus a `signature`.
      2. The customer's browser is redirected to <HYP_API_URL>?<signed-query-string>
         (the returned query string already carries action=pay).

    Notes:
      - `Amount` must be sent in the main currency unit (shekels), NOT agorot.
      - `Order` is our internal transaction id so we can reconcile the callback.
    """
    if not HYP_API_KEY:
        raise RuntimeError("HYP_API_KEY is not configured")

    sign_params = _build_sign_params(
        order=transaction_id,
        amount=amount,
        currency=currency,
        info=info,
        user_email=user_email,
    )

    logger.info(
        f"Requesting HYP APISign signature for order {transaction_id} "
        f"(amount={sign_params['Amount']}, coin={sign_params['Coin']})"
    )

    resp = requests.get(HYP_API_URL, params=sign_params, timeout=20)
    resp.raise_for_status()
    signed_qs = resp.text.strip()

    if "signature=" not in signed_qs:
        logger.error(f"HYP APISign returned no signature for order {transaction_id}: {signed_qs[:300]}")
        raise RuntimeError(f"HYP signing failed: {signed_qs[:200]}")

    # APISign returns the query string with action=pay already set; be defensive.
    if "action=pay" not in signed_qs:
        signed_qs = "action=pay&" + signed_qs

    payment_url = f"{HYP_API_URL}?{signed_qs}"
    logger.info(f"HYP payment URL created successfully for order {transaction_id}")
    return payment_url


def verify_hyp_callback(data: Dict[str, Any]) -> bool:
    """
    Verify a HYP callback/redirect using the official APISign VERIFY endpoint.

    HYP appends a `Sign` (signature) parameter to the transaction result. We
    resend the received parameters to `action=APISign&What=VERIFY`; HYP replies
    with `CCode=0` when the signature is authentic.

    Une notification sans signature est rejetée tant que HYP_REQUIRE_SIGNATURE
    est actif (valeur par défaut). Le mode permissif n'existe que pour le
    développement local, où aucune signature n'est disponible.
    """
    order = data.get("Order") or data.get("order")
    signature = data.get("Sign") or data.get("signature") or data.get("Signature")

    if not signature:
        if HYP_REQUIRE_SIGNATURE:
            logger.error(f"HYP callback for order {order} rejected: signature required but missing")
            return False
        logger.warning(
            f"HYP callback for order {order} received without a signature - allowing "
            "(set HYP_REQUIRE_SIGNATURE=true to enforce)"
        )
        return True

    if not HYP_API_KEY:
        logger.error("Cannot verify HYP callback: HYP_API_KEY not configured")
        return False

    # Forward the exact result fields HYP signed, adding our auth params.
    control_fields = {"action", "What", "KEY", "PassP", "Masof", "transaction_id"}
    verify_params = {"action": "APISign", "What": "VERIFY"}
    verify_params.update(_hyp_base_params())
    for key, value in data.items():
        if key not in control_fields:
            verify_params[key] = value

    try:
        resp = requests.get(HYP_API_URL, params=verify_params, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"HYP VERIFY request failed for order {order}: {e}")
        return False

    verify_result = dict(parse_qsl(resp.text.strip()))
    ccode = verify_result.get("CCode")
    if ccode == "0":
        logger.info(f"✓ HYP signature verified for order {order}")
        return True

    logger.error(f"✗ HYP signature verification failed for order {order}: CCode={ccode}")
    return False


# ===== API Endpoints =====

@router.get("/verify-config")
async def verify_hyp_config():
    """
    Verify HYP configuration
    Test endpoint to check if HYP credentials are properly configured
    """
    config_status = {
        "hyp_configured": bool(HYP_API_KEY),
        "terminal_id": HYP_TERMINAL_ID,
        "user_id": HYP_USER_ID,
        "api_url": HYP_API_URL,
        "plans_loaded": len(HYP_PLANS),
        "available_plans": list(HYP_PLANS.keys())
    }
    
    if not HYP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HYP API key not configured"
        )
    
    return config_status


@router.get("/test-connection")
async def test_hyp_connection():
    """
    Live connectivity/credentials test against the HYP APISign endpoint.

    Performs a real SIGN dry-run (amount = 1 ILS, throwaway order) and reports
    whether the terminal credentials produce a valid signature. This is the
    definitive "is my HYP configuration correct?" check — call it after setting
    HYP_API_KEY / HYP_PASSP.
    """
    diagnostics: Dict[str, Any] = {
        "api_url": HYP_API_URL,
        "terminal_id": HYP_TERMINAL_ID,
        "api_key_configured": bool(HYP_API_KEY),
        "passp_configured": bool(HYP_PASSP),
        "require_signature": HYP_REQUIRE_SIGNATURE,
        "page_lang": HYP_PAGE_LANG,
    }

    if not HYP_API_KEY:
        diagnostics["ok"] = False
        diagnostics["message"] = "HYP_API_KEY is not configured"
        return JSONResponse(status_code=500, content=diagnostics)

    sign_params = _build_sign_params(
        order="test-connection",
        amount=1,
        currency="ILS",
        info="Flash Neiga connection test",
    )

    try:
        resp = requests.get(HYP_API_URL, params=sign_params, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        diagnostics["ok"] = False
        diagnostics["message"] = f"Could not reach HYP APISign endpoint: {e}"
        return JSONResponse(status_code=502, content=diagnostics)

    parsed = dict(parse_qsl(resp.text.strip()))

    if parsed.get("signature"):
        diagnostics["ok"] = True
        diagnostics["message"] = "APISign signature generated successfully — HYP credentials are valid."
        diagnostics["signature_preview"] = parsed["signature"][:12] + "..."
        return diagnostics

    # HYP returns an error code (e.g. CCode=902 for bad terminal/key) instead of a signature.
    diagnostics["ok"] = False
    diagnostics["message"] = "HYP did not return a signature — check terminal, KEY and PassP."
    diagnostics["hyp_ccode"] = parsed.get("CCode")
    diagnostics["hyp_response"] = resp.text.strip()[:300]
    return JSONResponse(status_code=502, content=diagnostics)


@router.get("/plans")
async def get_plans():
    """Get all available HYP plans"""
    return {
        "plans": HYP_PLANS,
        "count": len(HYP_PLANS)
    }


@router.post("/validate-promo")
async def validate_promo(request: ValidatePromoRequest, db: Session = Depends(get_db)):
    """Vérifie un code promo et renvoie le montant remisé, sans rien engager.

    Sert à afficher le prix final à l'élève avant qu'il ne paie. La remise est
    recalculée au moment du paiement : ce retour est purement informatif.
    """
    plan = get_plan(request.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Formule inconnue : {request.plan_id}")

    original_amount = float(plan["amount"])
    try:
        promo, discount, final_amount = promo_lib.validate(
            db, request.code, request.plan_id, original_amount, request.user_id
        )
    except promo_lib.PromoError as exc:
        return {"valid": False, "message": str(exc)}

    return {
        "valid": True,
        "code": promo.code,
        "description": promo.description,
        "discount_type": promo.discount_type,
        "original_amount": original_amount,
        "discount_amount": discount,
        "final_amount": final_amount,
        "currency": plan["currency"],
        "free": final_amount <= 0,
        "message": (
            "Accès offert !" if final_amount <= 0
            else f"Code appliqué : -{discount:g} {plan['currency'] == 'ILS' and '₪' or plan['currency']}"
        ),
    }


@router.post("/create-payment", response_model=CreatePaymentResponse)
async def create_payment(
    request: CreatePaymentRequest,
    db: Session = Depends(get_db)
):
    """
    Create a HYP payment link
    
    This endpoint:
    1. Validates the plan
    2. Creates a transaction record
    3. Generates a HYP payment URL
    4. Returns the URL for user redirection
    """
    # Validate plan
    plan = get_plan(request.plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan_id: {request.plan_id}"
        )
    
    # Verify user exists if user_id provided
    if request.user_id:
        user = db.query(UserDB).filter(UserDB.id == request.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user_email = request.user_email or user.email
    else:
        user_email = request.user_email

    # Code promo : le montant est TOUJOURS recalculé côté serveur à partir du
    # catalogue ; le client n'envoie qu'un code, jamais un prix.
    original_amount = float(plan["amount"])
    amount = original_amount
    discount = 0.0
    applied_promo = None
    if request.promo_code:
        try:
            applied_promo, discount, amount = promo_lib.validate(
                db, request.promo_code, request.plan_id, original_amount, request.user_id
            )
        except promo_lib.PromoError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Create transaction record
    transaction = TransactionDB(
        user_id=request.user_id,
        plan_id=request.plan_id,
        amount=amount,
        currency=plan["currency"],
        status="pending",
        event_type="payment.created",
        event_data=(
            {"promo_code": applied_promo.code, "original_amount": original_amount,
             "discount_amount": discount, "user_email": user_email}
            if applied_promo else None
        ),
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    logger.info(f"Created transaction {transaction.id} for plan {request.plan_id}")

    # Remise de 100 % : rien à encaisser, l'accès est ouvert immédiatement.
    if amount <= 0:
        if not request.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un compte est nécessaire pour utiliser un code d'accès offert.",
            )
        transaction.status = "completed"
        transaction.completed_at = datetime.utcnow()
        transaction.event_type = "payment.free"
        start_date, end_date = calculate_subscription_dates(request.plan_id)
        for old in db.query(SubscriptionDB).filter(
            SubscriptionDB.user_id == request.user_id,
            SubscriptionDB.status == "active",
        ).all():
            old.status = "expired"
            old.updated_at = datetime.utcnow()
            db.add(old)
        db.add(SubscriptionDB(
            user_id=request.user_id,
            plan_id=request.plan_id,
            start_date=start_date,
            end_date=end_date,
            status="active",
            transaction_id=transaction.id,
        ))
        promo_lib.redeem(
            db, applied_promo, request.plan_id, original_amount, discount, amount,
            user_id=request.user_id, user_email=user_email, transaction_id=transaction.id,
        )
        db.commit()
        logger.info("Accès offert via le code %s pour %s", applied_promo.code, user_email)
        return CreatePaymentResponse(
            payment_url=None,
            transaction_id=transaction.id,
            plan_id=request.plan_id,
            amount=0.0,
            currency=plan["currency"],
            original_amount=original_amount,
            discount_amount=discount,
            promo_code=applied_promo.code,
            free=True,
        )

    # Create HYP payment URL
    try:
        payment_url = create_hyp_payment_url(
            transaction_id=transaction.id,
            amount=amount,
            currency=plan["currency"],
            user_email=user_email,
            info=plan.get("name", "Flash Neiga"),
        )

        # Update transaction with payment URL. Le code promo n'est PAS consommé
        # ici : il ne l'est qu'au paiement effectif (callback), sinon un panier
        # abandonné brûlerait le code de l'élève.
        transaction.payment_url = payment_url
        db.commit()

        logger.info(f"Generated HYP payment URL for transaction {transaction.id}")

        return CreatePaymentResponse(
            payment_url=payment_url,
            transaction_id=transaction.id,
            plan_id=request.plan_id,
            amount=amount,
            currency=plan["currency"],
            original_amount=original_amount if applied_promo else None,
            discount_amount=discount if applied_promo else None,
            promo_code=applied_promo.code if applied_promo else None,
        )
        
    except Exception as e:
        logger.error(f"Failed to create HYP payment URL: {e}")
        transaction.status = "failed"
        transaction.event_data = {"error": str(e)}
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment URL: {str(e)}"
        )


@router.post("/callback")
async def hyp_callback_post(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle HYP payment callback (POST)
    
    This endpoint receives callbacks from HYP after payment completion via POST request.
    """
    # Get callback data from POST request
    if request.headers.get("content-type") == "application/json":
        data = await request.json()
    else:
        # HYP might send form data
        form_data = await request.form()
        data = dict(form_data)
    
    logger.info(f"Received HYP callback (POST): {data}")
    
    return await process_hyp_callback(data, db)


@router.get("/callback")
async def hyp_callback_get(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle HYP payment callback (GET)
    
    This endpoint receives callbacks from HYP after payment completion via GET request.
    HYP may use GET requests with query parameters instead of POST.
    """
    # Get callback data from query parameters
    data = dict(request.query_params)
    
    logger.info(f"Received HYP callback (GET): {data}")
    
    return await process_hyp_callback(data, db)


async def process_hyp_callback(data: Dict[str, Any], db: Session):
    """
    Process HYP callback data (shared logic for GET and POST)
    
    This function verifies the callback, updates the transaction, and creates/updates the subscription.
    """
    
    # Extract transaction ID from Order field
    transaction_id = data.get("Order") or data.get("order")
    if not transaction_id:
        logger.error("No transaction ID in callback")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing transaction ID"
        )
    
    # Find transaction
    transaction = db.query(TransactionDB).filter(
        TransactionDB.id == transaction_id
    ).first()
    
    if not transaction:
        logger.error(f"Transaction not found: {transaction_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    # Verify callback authenticity via HYP APISign VERIFY
    if not verify_hyp_callback(data):
        logger.error("Invalid callback signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid callback signature"
        )

    # Idempotence : HYP peut renvoyer la même notification plusieurs fois (et une
    # notification authentique pourrait être rejouée). Sans ce garde-fou, chaque
    # rejeu ouvrirait un abonnement supplémentaire.
    if transaction.status == "completed":
        logger.info(f"Transaction {transaction_id} déjà traitée — notification ignorée")
        return {"status": "success", "message": "Payment already processed"}


    # Check payment status
    ccode = data.get("CCode") or data.get("ccode")
    acode = data.get("ACode") or data.get("acode")
    hyp_transaction_id = data.get("Id") or data.get("id")
    
    # Update transaction
    transaction.callback_data = data
    transaction.hyp_transaction_id = hyp_transaction_id
    
    # CCode 0 means success
    if ccode == "0" or ccode == 0:
        transaction.status = "completed"
        transaction.completed_at = datetime.utcnow()
        transaction.event_type = "payment.completed"

        # Le code promo n'est comptabilisé qu'ici, au paiement confirmé.
        promo_info = transaction.event_data or {}
        promo_code_used = promo_info.get("promo_code") if isinstance(promo_info, dict) else None
        if promo_code_used:
            promo_obj = (
                db.query(promo_lib.PromoCodeDB)
                .filter(promo_lib.PromoCodeDB.code == promo_code_used)
                .first()
            )
            already_counted = (
                db.query(promo_lib.PromoRedemptionDB)
                .filter(promo_lib.PromoRedemptionDB.transaction_id == transaction.id)
                .first()
            )
            if promo_obj and not already_counted:
                promo_lib.redeem(
                    db, promo_obj, transaction.plan_id,
                    promo_info.get("original_amount", transaction.amount),
                    promo_info.get("discount_amount", 0),
                    transaction.amount,
                    user_id=transaction.user_id,
                    user_email=(promo_info.get("user_email")),
                    transaction_id=transaction.id,
                )

        # Create or extend subscription
        if transaction.user_id and transaction.plan_id:
            # Check for existing active subscription of the same type
            plan = get_plan(transaction.plan_id)
            plan_type = plan.get("type")
            is_extension = plan.get("is_extension", False)
            
            # Use startswith() to avoid SQL injection with LIKE
            # Only match subscriptions where plan_id starts with plan_type
            existing_sub = db.query(SubscriptionDB).filter(
                SubscriptionDB.user_id == transaction.user_id,
                SubscriptionDB.status == "active"
            ).all()
            
            # Filter in Python to avoid SQL injection
            existing_sub = [
                sub for sub in existing_sub 
                if sub.plan_id and sub.plan_id.startswith(f"{plan_type}_")
            ]
            existing_sub = existing_sub[0] if existing_sub else None
            
            if existing_sub and is_extension:
                # Extend existing subscription
                if existing_sub.end_date:
                    start_date = existing_sub.end_date
                else:
                    start_date = datetime.utcnow()
                
                start_date, end_date = calculate_subscription_dates(
                    transaction.plan_id,
                    start_date
                )
                
                existing_sub.end_date = end_date
                existing_sub.updated_at = datetime.utcnow()
                
                logger.info(f"Extended subscription {existing_sub.id} to {end_date}")
            else:
                # Create new subscription
                start_date, end_date = calculate_subscription_dates(transaction.plan_id)
                
                # Deactivate old subscriptions of the same type
                if existing_sub:
                    existing_sub.status = "expired"
                    existing_sub.updated_at = datetime.utcnow()
                
                subscription = SubscriptionDB(
                    user_id=transaction.user_id,
                    plan_id=transaction.plan_id,
                    start_date=start_date,
                    end_date=end_date,
                    status="active",
                    transaction_id=transaction.id
                )
                
                db.add(subscription)
                logger.info(f"Created new subscription for user {transaction.user_id}")
        
        db.commit()
        logger.info(f"Transaction {transaction_id} completed successfully")
        
        return {"status": "success", "message": "Payment completed"}
    else:
        # Payment failed
        transaction.status = "failed"
        transaction.event_type = "payment.failed"
        transaction.event_data = {
            "ccode": ccode,
            "acode": acode,
            "error": "Payment declined or failed"
        }
        db.commit()
        
        logger.warning(f"Transaction {transaction_id} failed with CCode={ccode}")
        
        return {"status": "failed", "message": "Payment failed"}


@router.get("/result")
async def hyp_result_get(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Alternative HYP result endpoint
    
    Some HYP configurations may redirect to /result instead of /callback.
    This endpoint forwards to the main callback handler.
    """
    # Get result data from query parameters
    data = dict(request.query_params)
    
    logger.info(f"Received HYP result (GET) - forwarding to callback handler: {data}")
    
    return await process_hyp_callback(data, db)


@router.get("/transaction/{transaction_id}")
async def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db)
):
    """
    Get transaction details including subscription information
    """
    transaction = db.query(TransactionDB).filter(
        TransactionDB.id == transaction_id
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    # Build base response
    response = {
        "id": transaction.id,
        "user_id": transaction.user_id,
        "plan_id": transaction.plan_id,
        "amount": transaction.amount,
        "currency": transaction.currency,
        "status": transaction.status,
        "payment_url": transaction.payment_url,
        "hyp_transaction_id": transaction.hyp_transaction_id,
        "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
        "completed_at": transaction.completed_at.isoformat() if transaction.completed_at else None,
        "callback_data": transaction.callback_data
    }
    
    # If transaction is completed, try to fetch associated subscription
    if transaction.status == "completed" and transaction.user_id:
        subscription = db.query(SubscriptionDB).filter(
            SubscriptionDB.transaction_id == transaction_id
        ).first()
        
        if subscription:
            # Get plan details for name
            plan = get_plan(subscription.plan_id)
            plan_name = plan.get("name") if plan else subscription.plan_id
            
            response["subscription"] = {
                "id": subscription.id,
                "plan_id": subscription.plan_id,
                "plan_name": plan_name,
                "start_date": subscription.start_date.isoformat() if subscription.start_date else None,
                "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
                "status": subscription.status,
                "created_at": subscription.created_at.isoformat() if subscription.created_at else None
            }
            logger.debug(f"Added subscription details to transaction {transaction_id}")
    
    return response


@router.get("/subscriptions/{user_id}")
async def get_user_subscriptions(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Get all subscriptions for a user
    """
    subscriptions = db.query(SubscriptionDB).filter(
        SubscriptionDB.user_id == user_id
    ).order_by(SubscriptionDB.created_at.desc()).all()
    
    return {
        "subscriptions": [
            {
                "id": sub.id,
                "plan_id": sub.plan_id,
                "start_date": sub.start_date,
                "end_date": sub.end_date,
                "status": sub.status,
                "created_at": sub.created_at
            }
            for sub in subscriptions
        ],
        "count": len(subscriptions)
    }
