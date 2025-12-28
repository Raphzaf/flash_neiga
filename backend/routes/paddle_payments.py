# backend/routes/paddle_payments.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import requests

router = APIRouter(prefix="/api/payments", tags=["payments"])

def _normalize_api_key(raw: str | None) -> str | None:
    """Strip quotes and whitespace from API key to avoid malformed auth."""
    if not raw:
        return None
    # Remove wrapping quotes and surrounding whitespace
    key = raw.strip().strip("\"").strip("\'")
    return key

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
    """Crée un checkout Paddle et retourne l'URL (compat avec frontend)."""
    paddle_api_key = _normalize_api_key(os.getenv("PADDLE_API_KEY"))
    if not paddle_api_key:
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
        # Debug aids
        try:
            print(f"API key prefix: {paddle_api_key[:8] if paddle_api_key else 'NONE'}")
            print(f"Request body: {body}")
        except Exception:
            pass

        resp = requests.post("https://api.paddle.com/transactions", headers=headers, json=body, timeout=20)
        if resp.status_code >= 400:
            try:
                err = resp.json()
            except Exception:
                err = {"message": resp.text}
            # Surface auth formatting issues clearly to the client
            if isinstance(err, dict) and (err.get("error") or {}).get("code") == "authentication_malformed":
                raise HTTPException(status_code=400, detail="Paddle authentication malformed: check PADDLE_API_KEY formatting (no quotes, starts with 'pdl_live_' or 'pdl_test_')")
            # Permission issues (wrong project/environment or insufficient scopes)
            if isinstance(err, dict) and (err.get("error") or {}).get("code") == "forbidden":
                raise HTTPException(status_code=403, detail=(
                    "Paddle forbidden: key is valid but not permitted to create transactions. "
                    "Ensure the API key belongs to the same Paddle project as the `priceId`, has transaction permissions, "
                    "and matches the correct environment (live vs test)."
                ))
            raise HTTPException(status_code=500, detail=f"Paddle error: {err}")
        data = resp.json().get("data", {})
        try:
            print(f"Status: {resp.status_code}")
            print(f"Short response: {str(resp.text)[:500]}")
        except Exception:
            pass
        checkout_url = (data.get("checkout") or {}).get("url")
        transaction_id = data.get("id")
        if not checkout_url:
            raise HTTPException(status_code=500, detail=f"No checkout URL returned from Paddle. Response: {data}")
        return CheckoutResponse(checkoutUrl=checkout_url, checkoutId=transaction_id)
    
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/paddle/test-auth")
async def test_paddle_auth():
    """Teste l'authentification Paddle."""
    key = os.getenv("PADDLE_API_KEY")
    if not key:
        return {"key_exists": False}
    # ✅ Accepte les anciens et nouveaux formats
    prefix_ok = (
        key.startswith("live_") or 
        key.startswith("test_") or 
        key.startswith("pdl_live_") or 
        key.startswith("pdl_test_")
    )
    return {
        "key_exists": True,
        "key_length": len(key),
        "starts_with": key[:8],
        "format_ok": prefix_ok,
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
async def paddle_webhook(payload: dict):
    """Webhook basique: accepte et loggue l'événement (à étendre si besoin)."""
    # TODO: Verify signature when enabling webhooks in production.
    event_type = payload.get("eventType")
    # Key lifecycle notifications to support rotation
    if event_type in ("api_key.expiring", "api_key.expired"):
        try:
            print(f"[Paddle] Webhook reçu: {event_type}. Pensez à faire tourner les clés API.")
        except Exception:
            pass
    return {"status": "ok", "received": True, "eventType": event_type}
