# backend/scripts/create_paddle_extensions.py
"""
Script pour créer les extensions hebdomadaires (49₪) pour Paddle
Utilisation: python scripts/create_paddle_extensions.py
"""

import requests
import os
from dotenv import load_dotenv
import json
import sys

load_dotenv()

PADDLE_API_KEY = os.getenv("PADDLE_API_KEY")
PADDLE_URL = "https://api.paddle.com"

if not PADDLE_API_KEY:
    print("ERREUR: PADDLE_API_KEY non défini dans .env")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {PADDLE_API_KEY}",
    "Content-Type": "application/json"
}

def get_products():
    """Récupère les produits existants"""
    response = requests.get(f"{PADDLE_URL}/products", headers=headers)
    
    if response.status_code != 200:
        print(f"ERREUR récupération produits: {response.text}")
        return None
    
    return response.json().get("data", [])

def find_product_by_name(products, name_contains):
    """Trouve un produit par nom"""
    for product in products:
        if name_contains.lower() in product.get("name", "").lower():
            return product.get("id")
    return None

def create_price(product_id: str, currency: str, amount: str, description: str) -> str:
    """Crée un price Paddle pour une extension hebdomadaire"""
    payload = {
        "productId": product_id,
        "currencyCode": currency,
        "unitPrice": {
            "amount": amount,
            "currencyCode": currency
        },
        "billingCycle": {
            "interval": "week",
            "frequency": 1
        },
        "description": description
    }
    
    response = requests.post(f"{PADDLE_URL}/prices", json=payload, headers=headers)
    
    if response.status_code not in (200, 201):
        print(f"ERREUR création price: {response.text}")
        return None
    
    price_id = response.json().get("data", {}).get("id")
    if not price_id:
        print(f"ERREUR réponse inattendue: {response.text}")
        return None
    print(f"  Price créé: {description} - {amount} {currency} (ID: {price_id})")
    return price_id

def main():
    print("Création des extensions hebdomadaires Paddle pour Flash Neiga...\n")
    
    # Récupérer les produits existants
    products = get_products()
    if not products:
        print("ERREUR: Impossible de récupérer les produits")
        return
    
    print(f"Produits trouvés: {len(products)}")
    for p in products:
        print(f"  - {p.get('name')} (ID: {p.get('id')})")
    
    # Trouver les produits Code et Vidéos
    code_product_id = find_product_by_name(products, "code")
    video_product_id = find_product_by_name(products, "vidéo")
    
    if not code_product_id:
        print("\nERREUR: Produit Code non trouvé. Créez-le d'abord avec create_paddle_products.py")
        return
    
    if not video_product_id:
        print("\nERREUR: Produit Vidéo non trouvé. Créez-le d'abord avec create_paddle_products.py")
        return
    
    print(f"\nProduit Code ID: {code_product_id}")
    print(f"Produit Vidéo ID: {video_product_id}\n")
    
    extensions = {}
    
    # Créer l'extension Code
    print("Création extension Code...")
    code_ext_id = create_price(
        code_product_id,
        "ILS",
        "4900",  # 49₪
        "Code - Extension 1 semaine"
    )
    if code_ext_id:
        extensions["code_1week_extension"] = code_ext_id
    
    # Créer l'extension Vidéos
    print("Création extension Vidéos...")
    video_ext_id = create_price(
        video_product_id,
        "ILS",
        "4900",  # 49₪
        "Vidéos - Extension 1 semaine"
    )
    if video_ext_id:
        extensions["videos_1week_extension"] = video_ext_id
    
    # Afficher le résumé
    print("\n" + "="*60)
    print("RÉSUMÉ - Extensions hebdomadaires créées")
    print("="*60 + "\n")
    
    if extensions:
        print("Ajoutez ces IDs à votre configuration:\n")
        print("paddle_price_ids.json:")
        print(json.dumps({
            "code": {
                "1week_extension": extensions.get("code_1week_extension", "NOT_CREATED")
            },
            "videos": {
                "1week_extension": extensions.get("videos_1week_extension", "NOT_CREATED")
            }
        }, indent=2))
        
        print("\n.env.production:")
        print(f"REACT_APP_PADDLE_PRICE_CODE_EXT={extensions.get('code_1week_extension', 'NOT_CREATED')}")
        print(f"REACT_APP_PADDLE_PRICE_VIDEO_EXT={extensions.get('videos_1week_extension', 'NOT_CREATED')}")
        
        # Sauvegarder dans un fichier
        with open("paddle_extensions_output.json", "w") as f:
            json.dump(extensions, f, indent=2)
        
        print("\nConfiguration sauvegardée dans: paddle_extensions_output.json")
    else:
        print("Aucune extension créée. Vérifiez les erreurs ci-dessus.")

if __name__ == "__main__":
    main()
