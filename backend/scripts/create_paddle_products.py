# backend/scripts/create_paddle_products.py
"""
Script pour créer les produits et prices Paddle pour Flash Neiga
Utilisation: python scripts/create_paddle_products.py
"""

import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

PADDLE_API_KEY = os.getenv("PADDLE_API_KEY")
PADDLE_URL = "https://api.paddle.com"

if not PADDLE_API_KEY:
    print("ERREUR: PADDLE_API_KEY non défini dans .env")
    exit(1)

headers = {
    "Authorization": f"Bearer {PADDLE_API_KEY}",
    "Content-Type": "application/json"
}

def create_product(name: str, description: str) -> str:
    """Crée un produit Paddle et retourne son ID"""
    payload = {
        "name": name,
        "description": description,
        "taxCategory": "standard"
    }
    
    response = requests.post(f"{PADDLE_URL}/products", json=payload, headers=headers)
    
    if response.status_code not in (200, 201):
        print(f"ERREUR creation produit {name}: {response.text}")
        return None
    
    product_id = response.json().get("data", {}).get("id")
    if not product_id:
        print(f"ERREUR reponse inattendue: {response.text}")
        return None
    print(f"Produit cree: {name} (ID: {product_id})")
    return product_id

def create_price(product_id: str, currency: str, amount: str, billing_cycle: dict, description: str) -> str:
    """Crée un price Paddle et retourne son ID"""
    payload = {
        "productId": product_id,
        "currencyCode": currency,
        "unitPrice": {
            "amount": amount,
            "currencyCode": currency
        },
        "billingCycle": billing_cycle,
        "description": description
    }
    
    response = requests.post(f"{PADDLE_URL}/prices", json=payload, headers=headers)
    
    if response.status_code not in (200, 201):
        print(f"ERREUR creation price: {response.text}")
        return None
    
    price_id = response.json().get("data", {}).get("id")
    if not price_id:
        print(f"ERREUR reponse inattendue: {response.text}")
        return None
    print(f"  Price cree: {description} - {amount} {currency} (ID: {price_id})")
    return price_id

def main():
    print("Creation des produits et prices Paddle pour Flash Neiga...\n")
    
    # ===== PRODUIT 1 : CODE SUBSCRIPTION =====
    code_product_id = create_product(
        "Flash Neiga - Code Subscription",
        "Accès à la Web App, E-book, Questions officielles, Examens blancs, Coaching"
    )
    
    if not code_product_id:
        return
    
    code_prices = {}
    
    # 14 jours
    price_id = create_price(
        code_product_id,
        "ILS",
        "11900",  # 119₪
        {"interval": "day", "frequency": 14},
        "Code - 14 jours"
    )
    if price_id:
        code_prices["14days"] = price_id
    
    # 30 jours
    price_id = create_price(
        code_product_id,
        "ILS",
        "18900",  # 189₪ (réduit de 238₪)
        {"interval": "day", "frequency": 30},
        "Code - 30 jours"
    )
    if price_id:
        code_prices["30days"] = price_id
    
    # ===== PRODUIT 2 : VIDEOS PEDAGOGIQUES =====
    video_product_id = create_product(
        "Flash Neiga - Vidéos Pédagogiques",
        "28 objectifs + parcours examens filmés + Conduite Commentée"
    )
    
    if not video_product_id:
        return
    
    video_prices = {}
    
    # 1 mois
    price_id = create_price(
        video_product_id,
        "ILS",
        "19900",  # 199₪
        {"interval": "month", "frequency": 1},
        "Vidéos - 1 mois"
    )
    if price_id:
        video_prices["1month"] = price_id
    
    # 2 mois
    price_id = create_price(
        video_product_id,
        "ILS",
        "34900",  # 349₪ (réduit de 398₪)
        {"interval": "month", "frequency": 2},
        "Vidéos - 2 mois"
    )
    if price_id:
        video_prices["2months"] = price_id
    
    # 3 mois
    price_id = create_price(
        video_product_id,
        "ILS",
        "48900",  # 489₪ (réduit de 597₪)
        {"interval": "month", "frequency": 3},
        "Vidéos - 3 mois"
    )
    if price_id:
        video_prices["3months"] = price_id
    
    # ===== AFFICHAGE DU RÉSUMÉ =====
    print("\n" + "="*60)
    print("RESUME - COPIE CECI DANS TON paddlePrices.js")
    print("="*60 + "\n")
    
    output = {
        "CODE": code_prices,
        "VIDEOS": video_prices,
        "PRODUCTS": {
            "CODE": code_product_id,
            "VIDEOS": video_product_id
        }
    }
    
    print("export const PADDLE_PRICES = {")
    print("  CODE: {")
    for key, value in code_prices.items():
        print(f"    {key.upper()}: '{value}',")
    print("  },")
    print("  VIDEOS: {")
    for key, value in video_prices.items():
        print(f"    {key.upper()}: '{value}',")
    print("  }")
    print("};")
    
    # Sauvegarde aussi dans un fichier
    with open("paddle_prices_output.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print("\nConfiguration complete!")
    print("IDs sauvegardes dans: paddle_prices_output.json")

if __name__ == "__main__":
    main()
