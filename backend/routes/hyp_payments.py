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
import hashlib
import hmac
import requests
from pathlib import Path

# Support imports both when running from backend/ and from repo root
try:
    from database import get_db
except ImportError:
    from backend.database import get_db

try:
    from models import TransactionDB, SubscriptionDB, UserDB
except ImportError:
    from backend.models import TransactionDB, SubscriptionDB, UserDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments/hyp", tags=["HYP Payments"])

# HYP Configuration
HYP_TERMINAL_ID = os.environ.get("HYP_TERMINAL_ID", "4502176330")
HYP_USER_ID = os.environ.get("HYP_USER_ID", "pveda")
HYP_API_KEY = os.environ.get("HYP_API_KEY", "")
HYP_API_URL = os.environ.get("HYP_API_URL", "https://icom.yaad.net/p/")
HYP_SUCCESS_URL = os.environ.get("HYP_SUCCESS_URL", "http://localhost:3000/payment/success")
HYP_ERROR_URL = os.environ.get("HYP_ERROR_URL", "http://localhost:3000/payment/failure")
HYP_CALLBACK_URL = os.environ.get("HYP_CALLBACK_URL", "http://localhost:8000/api/payments/hyp/callback")

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


class CreatePaymentResponse(BaseModel):
    payment_url: str
    transaction_id: str
    plan_id: str
    amount: float
    currency: str


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


def create_hyp_payment_url(
    transaction_id: str,
    amount: float,
    currency: str = "ILS",
    user_email: Optional[str] = None
) -> str:
    """
    Create HYP payment URL using doDeal API
    Documentation: https://developers.hyp.co.il/payment-page-integration/integrating-hyps-payment-page-and-accepting-payment
    """
    # Convert amount to agorot (multiply by 100)
    amount_agorot = int(amount * 100)
    
    # Build HYP payment parameters
    params = {
        "action": "APISign",
        "What": "SIGN",
        "KEY": HYP_API_KEY,
        "PassP": f"Amount={amount_agorot}&Coin=1&Currency=1&Order={transaction_id}&Info=Flash Neiga Payment&Pritim=True&ClientName=&ClientLName=&PhoneDial=&email={user_email or ''}&street=&city=&zip=&remarks=&sendemail=true&SendHesh=true&heshDesc=&pageField=&successUrl={HYP_SUCCESS_URL}?transaction_id={transaction_id}&failureUrl={HYP_ERROR_URL}?transaction_id={transaction_id}&maxPayments=1",
        "MoreData": "True",
        "sign_method": "md5"
    }
    
    # Create request to HYP API to get signed URL
    try:
        # First, get the signature
        sign_response = requests.post(
            f"{HYP_API_URL}",
            data={
                "action": "APISign",
                "What": "SIGN",
                "KEY": HYP_API_KEY,
                "PassP": params["PassP"],
                "MoreData": "True",
                "sign_method": "md5"
            },
            timeout=10
        )
        
        if sign_response.status_code != 200:
            logger.error(f"HYP sign request failed: {sign_response.text}")
            raise Exception("Failed to create HYP payment signature")
        
        # Parse response to get signature
        response_data = sign_response.text
        logger.info(f"HYP sign response: {response_data}")
        
        # Build the payment URL with all required parameters
        payment_url = (
            f"{HYP_API_URL}?action=pay"
            f"&Amount={amount_agorot}"
            f"&Coin=1"
            f"&Currency=1"
            f"&Order={transaction_id}"
            f"&terminalNumber={HYP_TERMINAL_ID}"
            f"&userName={HYP_USER_ID}"
            f"&successUrl={HYP_SUCCESS_URL}?transaction_id={transaction_id}"
            f"&failureUrl={HYP_ERROR_URL}?transaction_id={transaction_id}"
            f"&maxPayments=1"
            f"&sendemail=true"
        )
        
        if user_email:
            payment_url += f"&email={user_email}"
        
        return payment_url
        
    except requests.RequestException as e:
        logger.error(f"Failed to create HYP payment URL: {e}")
        raise Exception(f"HYP API error: {str(e)}")


def verify_hyp_callback(data: Dict[str, Any]) -> bool:
    """
    Verify HYP callback signature
    """
    # HYP sends a hash that we need to verify
    # Documentation: https://developers.hyp.co.il/
    # TODO: Implement proper signature verification when available in docs
    return True


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


@router.get("/plans")
async def get_plans():
    """Get all available HYP plans"""
    return {
        "plans": HYP_PLANS,
        "count": len(HYP_PLANS)
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
    
    # Create transaction record
    transaction = TransactionDB(
        user_id=request.user_id,
        plan_id=request.plan_id,
        amount=plan["amount"],
        currency=plan["currency"],
        status="pending",
        event_type="payment.created"
    )
    
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    logger.info(f"Created transaction {transaction.id} for plan {request.plan_id}")
    
    # Create HYP payment URL
    try:
        payment_url = create_hyp_payment_url(
            transaction_id=transaction.id,
            amount=plan["amount"],
            currency=plan["currency"],
            user_email=user_email
        )
        
        # Update transaction with payment URL
        transaction.payment_url = payment_url
        db.commit()
        
        logger.info(f"Generated HYP payment URL for transaction {transaction.id}")
        
        return CreatePaymentResponse(
            payment_url=payment_url,
            transaction_id=transaction.id,
            plan_id=request.plan_id,
            amount=plan["amount"],
            currency=plan["currency"]
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
async def hyp_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle HYP payment callback
    
    This endpoint receives callbacks from HYP after payment completion.
    It verifies the callback, updates the transaction, and creates/updates the subscription.
    """
    # Get callback data
    if request.headers.get("content-type") == "application/json":
        data = await request.json()
    else:
        # HYP might send form data
        form_data = await request.form()
        data = dict(form_data)
    
    logger.info(f"Received HYP callback: {data}")
    
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
    
    # Verify callback (TODO: implement proper signature verification)
    if not verify_hyp_callback(data):
        logger.error("Invalid callback signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid callback signature"
        )
    
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
        
        # Create or extend subscription
        if transaction.user_id and transaction.plan_id:
            # Check for existing active subscription of the same type
            plan = get_plan(transaction.plan_id)
            plan_type = plan.get("type")
            is_extension = plan.get("is_extension", False)
            
            existing_sub = db.query(SubscriptionDB).filter(
                SubscriptionDB.user_id == transaction.user_id,
                SubscriptionDB.plan_id.like(f"{plan_type}_%"),
                SubscriptionDB.status == "active"
            ).first()
            
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


@router.get("/transaction/{transaction_id}")
async def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db)
):
    """
    Get transaction details
    """
    transaction = db.query(TransactionDB).filter(
        TransactionDB.id == transaction_id
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    return {
        "id": transaction.id,
        "user_id": transaction.user_id,
        "plan_id": transaction.plan_id,
        "amount": transaction.amount,
        "currency": transaction.currency,
        "status": transaction.status,
        "payment_url": transaction.payment_url,
        "hyp_transaction_id": transaction.hyp_transaction_id,
        "created_at": transaction.created_at,
        "completed_at": transaction.completed_at,
        "callback_data": transaction.callback_data
    }


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
