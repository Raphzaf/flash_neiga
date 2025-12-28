#!/bin/bash
# Script pour tester la création d'un checkout Paddle
# Usage: ./test-paddle-checkout.sh <PRICE_ID> [EMAIL]

PRICE_ID="$1"
EMAIL="${2:-test@example.com}"

if [ -z "$PRICE_ID" ]; then
    echo "Usage: $0 <PRICE_ID> [EMAIL]"
    echo "Example: $0 pri_01xxxxxxxxxxxxx user@example.com"
    exit 1
fi

echo "🛒 Test de création de checkout Paddle"
echo "======================================"
echo ""
echo "Price ID: $PRICE_ID"
echo "Email: $EMAIL"
echo ""

BASE_URL="http://localhost:8000"

# Créer le payload JSON
PAYLOAD=$(cat <<EOF
{
  "priceId": "$PRICE_ID",
  "email": "$EMAIL"
}
EOF
)

# Tester la création du checkout
echo "1️⃣  Création du checkout..."
response=$(curl -s -X POST "$BASE_URL/api/payments/paddle/create-checkout" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

# Vérifier si le checkout a été créé
checkout_url=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('checkoutUrl', ''))" 2>/dev/null)

if [ -n "$checkout_url" ]; then
    echo "✅ Checkout créé avec succès!"
    echo ""
    echo "📋 Détails:"
    checkout_id=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('checkoutId', 'N/A'))" 2>/dev/null)
    echo "   Checkout URL: $checkout_url"
    echo "   Checkout ID: $checkout_id"
    echo ""
    echo "🌐 Ouvrir dans le navigateur:"
    echo "   $checkout_url"
    echo ""
    
    # Demander si on veut ouvrir le navigateur (MacOS/Linux)
    read -p "Voulez-vous ouvrir le checkout dans le navigateur? (o/N): " open_browser
    if [ "$open_browser" = "o" ] || [ "$open_browser" = "O" ] || [ "$open_browser" = "oui" ]; then
        if command -v xdg-open > /dev/null; then
            xdg-open "$checkout_url"
        elif command -v open > /dev/null; then
            open "$checkout_url"
        else
            echo "Impossible d'ouvrir automatiquement. Copiez l'URL ci-dessus."
        fi
    fi
else
    echo "❌ Erreur lors de la création du checkout"
    echo "   Réponse: $response"
    echo ""
    echo "💡 Causes possibles:"
    echo "   - Le Price ID n'existe pas dans votre projet Paddle"
    echo "   - Le Price ID appartient à un autre projet/environnement"
    echo "   - La clé API n'a pas les permissions nécessaires"
    echo ""
    echo "📝 Solution:"
    echo "   1. Vérifier le Price ID dans Paddle Dashboard"
    echo "   2. S'assurer que la clé API et le prix sont dans le même projet"
    echo "   3. Vérifier que la clé a les permissions 'Transactions: Write'"
    exit 1
fi

echo ""
echo "✅ Test terminé avec succès"
