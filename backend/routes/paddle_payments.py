# backend/routes/paddle_payments.py

from fastapi import APIRouter, HTTPException, Request, Header, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import os
import requests
import hmac
import hashlib
import json
import logging

# Import database dependencies
try:
    from database import get_db
    from models import TransactionDB
except ImportError:
    from backend.database import get_db
    from backend.models import TransactionDB

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])

def _normalize_api_key(raw: str | None) -> str | None:
    """Strip quotes and whitespace from API key to avoid malformed auth."""
    if not raw:
        return None
    # Remove wrapping quotes and surrounding whitespace
    key = raw.strip().strip("\"").strip("\'")
    return key


def verify_paddle_webhook_signature(payload_body: bytes, signature: str, secret: str) -> bool:
    """
    Vérifie la signature d'un webhook Paddle.
    Doc: https://developer.paddle.com/webhooks/signature-verification
    
    Args:
        payload_body: Corps brut du webhook (bytes)
        signature: Valeur du header Paddle-Signature
        secret: PADDLE_WEBHOOK_SECRET
    
    Returns:
        True si la signature est valide, False sinon
    """
    if not secret or not signature:
        logger.warning("Signature verification skipped: missing secret or signature")
        return False
    
    try:
        # Format de la signature Paddle: ts=timestamp;h1=hash
        parts = {}
        for part in signature.split(";"):
            if "=" in part:
                key, value = part.split("=", 1)
                parts[key] = value
        
        timestamp = parts.get("ts", "")
        received_hash = parts.get("h1", "")
        
        if not timestamp or not received_hash:
            logger.warning("Invalid signature format")
            return False
        
        # Construire le payload signé: timestamp + ":" + body
        signed_payload = f"{timestamp}:{payload_body.decode('utf-8')}"
        
        # Calculer le HMAC-SHA256
        expected_hash = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Comparaison sécurisée
        return hmac.compare_digest(expected_hash, received_hash)
    
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False


class CheckoutRequest(BaseModel):
    priceId: str
    email: str | None = None

class CheckoutResponse(BaseModel):
    checkoutUrl: str
    checkoutId: str | None = None

@router.get("/paddle/health")
async def paddle_health():
    """Simple health for Paddle configuration."""
    return {"paddle_configured": bool(os.getenv("PADDLE_API_KEY"))}

@router.post("/paddle/create-checkout", response_model=CheckoutResponse)
async def create_paddle_checkout(request: CheckoutRequest):
    """
    Crée un checkout Paddle et retourne l'URL (compat avec frontend).
    Amélioration: gestion d'erreurs robuste et logging détaillé.
    """
    paddle_api_key = _normalize_api_key(os.getenv("PADDLE_API_KEY"))
    if not paddle_api_key:
        logger.error("Paddle API key not configured")
        raise HTTPException(
            status_code=400,
            detail="Paddle not configured: set PADDLE_API_KEY env var on backend"
        )

    try:
        headers = {
            "Authorization": f"Bearer {paddle_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        # Create a transaction and use returned checkout URL
        body = {
            "items": [{"price_id": request.priceId, "quantity": 1}],
        }
        
        # Optional email prefill
        if request.email:
            body["customer_email"] = request.email
        
        # Logging détaillé
        logger.info(f"Creating Paddle checkout for price: {request.priceId}")
        if request.email:
            logger.info(f"Customer email: {request.email}")

        resp = requests.post(
            "https://api.paddle.com/transactions",
            headers=headers,
            json=body,
            timeout=20
        )
        
        if resp.status_code >= 400:
            try:
                err = resp.json()
            except Exception:
                err = {"message": resp.text}
            
            logger.error(f"Paddle API error: {resp.status_code} - {err}")
            
            # Surface auth formatting issues clearly to the client
            if isinstance(err, dict) and (err.get("error") or {}).get("code") == "authentication_malformed":
                raise HTTPException(
                    status_code=400,
                    detail="Paddle authentication malformed: check PADDLE_API_KEY formatting (no quotes, starts with 'pdl_live_' or 'pdl_test_')"
                )
            
            # Permission issues (wrong project/environment or insufficient scopes)
            if isinstance(err, dict) and (err.get("error") or {}).get("code") == "forbidden":
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Paddle forbidden: key is valid but not permitted to create transactions. "
                        "Ensure the API key belongs to the same Paddle project as the `priceId`, has transaction permissions, "
                        "and matches the correct environment (live vs test)."
                    )
                )
            
            raise HTTPException(status_code=500, detail=f"Paddle error: {err}")
        
        data = resp.json().get("data", {})
        checkout_url = (data.get("checkout") or {}).get("url")
        transaction_id = data.get("id")
        
        if not checkout_url:
            logger.error(f"No checkout URL in Paddle response: {data}")
            raise HTTPException(
                status_code=500,
                detail=f"No checkout URL returned from Paddle. Response: {data}"
            )
        
        logger.info(f"Checkout created successfully: {transaction_id}")
        return CheckoutResponse(checkoutUrl=checkout_url, checkoutId=transaction_id)
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error calling Paddle API: {e}")
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating checkout: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/paddle/test-auth")
async def test_paddle_auth():
    """
    Teste l'authentification Paddle en vérifiant la clé API.
    Amélioration: teste la connexion réelle à l'API Paddle.
    """
    key = _normalize_api_key(os.getenv("PADDLE_API_KEY"))
    if not key:
        return {"key_exists": False, "message": "PADDLE_API_KEY not configured"}
    
    # Vérifier le format de la clé
    prefix_ok = (
        key.startswith("live_") or 
        key.startswith("test_") or 
        key.startswith("pdl_live_") or 
        key.startswith("pdl_test_")
    )
    
    # Tester la connexion réelle à l'API Paddle
    connection_ok = False
    api_message = ""
    
    try:
        headers = {
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        }
        # Test avec un endpoint simple qui ne crée rien
        resp = requests.get("https://api.paddle.com/prices?per_page=1", headers=headers, timeout=10)
        connection_ok = resp.status_code < 400
        
        if connection_ok:
            api_message = "Successfully connected to Paddle API"
            logger.info("Paddle API authentication test: SUCCESS")
        else:
            api_message = f"Paddle API returned status {resp.status_code}"
            logger.warning(f"Paddle API authentication test failed: {resp.status_code}")
    except Exception as e:
        api_message = f"Failed to connect: {str(e)}"
        logger.error(f"Paddle API connection test error: {e}")
    
    return {
        "key_exists": True,
        "key_length": len(key),
        "starts_with": key[:8] if len(key) >= 8 else key,
        "format_ok": prefix_ok,
        "connection_ok": connection_ok,
        "api_message": api_message
    }

@router.get("/paddle/price/{price_id}")
async def inspect_price(price_id: str):
    """Inspect a Paddle price to verify it belongs to the current project and environment."""
    api_key = _normalize_api_key(os.getenv("PADDLE_API_KEY"))
    if not api_key:
        raise HTTPException(status_code=400, detail="PADDLE_API_KEY not configured")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    try:
        r = requests.get(f"https://api.paddle.com/prices/{price_id}", headers=headers, timeout=15)
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="Price not found for this API key/project")
        if r.status_code >= 400:
            try:
                err = r.json()
            except Exception:
                err = {"message": r.text}
            if isinstance(err, dict) and (err.get("error") or {}).get("code") == "forbidden":
                raise HTTPException(status_code=403, detail="Forbidden: API key cannot access this price (project/environment mismatch)")
            raise HTTPException(status_code=500, detail=f"Paddle error: {err}")
        data = r.json().get("data") or {}
        return {
            "ok": True,
            "id": data.get("id"),
            "status": data.get("status"),
            "product_id": (data.get("product") or {}).get("id"),
            "currency": data.get("currency"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/paddle/prices")
async def list_prices():
    """List accessible Paddle prices for current API key."""
    api_key = _normalize_api_key(os.getenv("PADDLE_API_KEY"))
    if not api_key:
        raise HTTPException(status_code=400, detail="PADDLE_API_KEY not configured")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    try:
        r = requests.get("https://api.paddle.com/prices", headers=headers, timeout=15)
        if r.status_code >= 400:
            try:
                err = r.json()
            except Exception:
                err = {"message": r.text}
            raise HTTPException(status_code=r.status_code, detail=err)
        data = r.json().get("data") or []
        items = []
        for p in data:
            items.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "status": p.get("status"),
                "product_id": (p.get("product") or {}).get("id"),
                "currency": p.get("currency"),
                "amount": (p.get("unit_price") or {}).get("amount"),
            })
        return {"prices": items}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/paddle/webhook")
async def paddle_webhook(
    request: Request,
    paddle_signature: Optional[str] = Header(None, alias="Paddle-Signature"),
    db: Session = Depends(get_db)
):
    """
    Reçoit et traite les événements webhook de Paddle.
    Doc: https://developer.paddle.com/webhooks/overview
    
    Événements supportés:
    - transaction.completed: Transaction terminée avec succès
    - transaction.paid: Paiement reçu
    - subscription.created: Nouvel abonnement créé
    - subscription.updated: Abonnement modifié
    - subscription.canceled: Abonnement annulé
    - api_key.expiring: Clé API bientôt expirée
    - api_key.expired: Clé API expirée
    """
    # 1. Lire le corps brut du webhook
    try:
        body_bytes = await request.body()
        body_str = body_bytes.decode('utf-8')
        payload = json.loads(body_str)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    
    # 2. Vérifier la signature (si PADDLE_WEBHOOK_SECRET est configuré)
    webhook_secret = os.getenv("PADDLE_WEBHOOK_SECRET")
    if webhook_secret and paddle_signature:
        if not verify_paddle_webhook_signature(body_bytes, paddle_signature, webhook_secret):
            logger.warning("Invalid webhook signature - potential security issue")
            raise HTTPException(status_code=401, detail="Invalid signature")
        logger.info("Webhook signature verified successfully")
    elif webhook_secret:
        logger.warning("Webhook secret configured but no signature provided")
    else:
        logger.info("Webhook signature verification skipped (PADDLE_WEBHOOK_SECRET not configured)")
    
    # 3. Parser l'événement
    event_type = payload.get("event_type")
    event_id = payload.get("event_id")
    data = payload.get("data", {})
    
    logger.info(f"Received Paddle webhook: event_type={event_type}, event_id={event_id}")
    
    # 4. Traiter selon le type d'événement
    try:
        if event_type == "transaction.completed":
            # Transaction complétée avec succès
            transaction_id = data.get("id")
            subscription_id = data.get("subscription_id")
            customer_id = data.get("customer_id")
            
            # Extraire les détails du paiement
            amount = None
            currency = None
            details = data.get("details", {})
            if details and "totals" in details:
                totals = details["totals"]
                amount = float(totals.get("total", 0)) / 100  # Paddle utilise les centimes
                currency = totals.get("currency_code", "USD")
            
            logger.info(f"Transaction completed: {transaction_id}, amount: {amount} {currency}")
            
            # Enregistrer dans la base de données
            transaction = TransactionDB(
                paddle_transaction_id=transaction_id,
                paddle_subscription_id=subscription_id,
                user_id=customer_id,
                amount=amount,
                currency=currency,
                status="completed",
                event_type=event_type,
                event_data=data
            )
            db.add(transaction)
            db.commit()
            logger.info(f"Transaction saved to database: {transaction.id}")
        
        elif event_type == "transaction.paid":
            # Paiement reçu
            transaction_id = data.get("id")
            logger.info(f"Transaction paid: {transaction_id}")
            
            # Mettre à jour le statut si la transaction existe
            existing = db.query(TransactionDB).filter(
                TransactionDB.paddle_transaction_id == transaction_id
            ).first()
            
            if existing:
                existing.status = "paid"
                existing.metadata = data
                db.commit()
                logger.info(f"Transaction status updated to 'paid': {existing.id}")
            else:
                # Créer une nouvelle entrée
                transaction = TransactionDB(
                    paddle_transaction_id=transaction_id,
                    status="paid",
                    event_type=event_type,
                    event_data=data
                )
                db.add(transaction)
                db.commit()
                logger.info(f"New transaction created with 'paid' status: {transaction.id}")
        
        elif event_type == "subscription.created":
            # Nouvel abonnement créé
            subscription_id = data.get("id")
            customer_id = data.get("customer_id")
            status = data.get("status")
            
            logger.info(f"Subscription created: {subscription_id}, customer: {customer_id}, status: {status}")
            
            # Enregistrer l'abonnement
            transaction = TransactionDB(
                paddle_subscription_id=subscription_id,
                user_id=customer_id,
                status=status,
                event_type=event_type,
                event_data=data
            )
            db.add(transaction)
            db.commit()
            logger.info(f"Subscription saved to database: {transaction.id}")
        
        elif event_type == "subscription.updated":
            # Abonnement modifié
            subscription_id = data.get("id")
            status = data.get("status")
            
            logger.info(f"Subscription updated: {subscription_id}, new status: {status}")
            
            # Mettre à jour l'abonnement existant
            existing = db.query(TransactionDB).filter(
                TransactionDB.paddle_subscription_id == subscription_id
            ).order_by(TransactionDB.created_at.desc()).first()
            
            if existing:
                existing.status = status
                existing.metadata = data
                db.commit()
                logger.info(f"Subscription updated in database: {existing.id}")
        
        elif event_type == "subscription.canceled":
            # Abonnement annulé
            subscription_id = data.get("id")
            
            logger.info(f"Subscription canceled: {subscription_id}")
            
            # Mettre à jour le statut
            existing = db.query(TransactionDB).filter(
                TransactionDB.paddle_subscription_id == subscription_id
            ).order_by(TransactionDB.created_at.desc()).first()
            
            if existing:
                existing.status = "canceled"
                existing.metadata = data
                db.commit()
                logger.info(f"Subscription marked as canceled: {existing.id}")
        
        elif event_type in ("api_key.expiring", "api_key.expired"):
            # Clé API bientôt expirée ou expirée
            logger.warning(f"⚠️  Paddle webhook: {event_type}. Pensez à faire tourner les clés API!")
        
        else:
            # Événement non géré
            logger.info(f"Unhandled event type: {event_type}")
    
    except Exception as e:
        logger.error(f"Error processing webhook event: {e}", exc_info=True)
        db.rollback()
        # On retourne quand même 200 pour ne pas faire réessayer Paddle indéfiniment
        return {"status": "error", "message": "Failed to process event", "eventType": event_type}
    
    # 5. Retourner 200 OK pour confirmer la réception
    return {"status": "ok", "received": True, "eventType": event_type, "eventId": event_id}


@router.get("/paddle/verify-config")
async def verify_paddle_config():
    """
    Vérifie que la configuration Paddle est complète et fonctionnelle.
    
    Vérifie:
    - PADDLE_API_KEY est définie
    - PADDLE_WEBHOOK_SECRET est définie
    - Les price IDs sont accessibles
    - La connexion à l'API fonctionne
    """
    api_key = _normalize_api_key(os.getenv("PADDLE_API_KEY"))
    webhook_secret = os.getenv("PADDLE_WEBHOOK_SECRET")
    
    checks = {
        "api_key_configured": bool(api_key),
        "webhook_secret_configured": bool(webhook_secret),
        "api_connection_ok": False,
        "price_ids_accessible": False,
        "issues": []
    }
    
    # Vérifier l'API key
    if not api_key:
        checks["issues"].append("PADDLE_API_KEY not configured")
    else:
        # Tester la connexion
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            }
            resp = requests.get("https://api.paddle.com/prices?per_page=1", headers=headers, timeout=10)
            checks["api_connection_ok"] = resp.status_code < 400
            
            if resp.status_code < 400:
                checks["price_ids_accessible"] = True
            else:
                checks["issues"].append(f"API connection failed with status {resp.status_code}")
        except Exception as e:
            checks["issues"].append(f"Failed to connect to Paddle API: {str(e)}")
    
    # Vérifier le webhook secret
    if not webhook_secret:
        checks["issues"].append("PADDLE_WEBHOOK_SECRET not configured - webhook signature verification disabled")
    
    # Déterminer le statut global
    checks["status"] = "ok" if checks["api_key_configured"] and checks["api_connection_ok"] else "error"
    
    logger.info(f"Configuration verification: {checks['status']}")
    
    return checks


@router.get("/paddle/subscription/{subscription_id}")
async def get_subscription_status(subscription_id: str):
    """
    Vérifie le statut d'un abonnement Paddle.
    
    Args:
        subscription_id: ID de l'abonnement Paddle
    
    Returns:
        Détails de l'abonnement depuis l'API Paddle
    """
    api_key = _normalize_api_key(os.getenv("PADDLE_API_KEY"))
    if not api_key:
        raise HTTPException(status_code=400, detail="PADDLE_API_KEY not configured")
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        
        logger.info(f"Fetching subscription status: {subscription_id}")
        
        resp = requests.get(
            f"https://api.paddle.com/subscriptions/{subscription_id}",
            headers=headers,
            timeout=15
        )
        
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        if resp.status_code >= 400:
            try:
                err = resp.json()
            except Exception:
                err = {"message": resp.text}
            
            logger.error(f"Paddle API error: {resp.status_code} - {err}")
            raise HTTPException(status_code=resp.status_code, detail=f"Paddle error: {err}")
        
        data = resp.json().get("data", {})
        
        # Extraire les informations importantes
        result = {
            "id": data.get("id"),
            "status": data.get("status"),
            "customer_id": data.get("customer_id"),
            "current_billing_period": data.get("current_billing_period"),
            "next_billed_at": data.get("next_billed_at"),
            "canceled_at": data.get("canceled_at"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        }
        
        logger.info(f"Subscription status retrieved: {subscription_id} - {result['status']}")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))
