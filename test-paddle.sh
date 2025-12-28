#!/bin/bash
# Script de test Paddle pour Flash Neiga
# Usage: ./test-paddle.sh

echo "🔍 Test de l'intégration Paddle pour Flash Neiga"
echo "================================================="
echo ""

BASE_URL="http://localhost:8000"

# Fonction pour afficher JSON formaté
show_json() {
    echo "$1" | python3 -m json.tool 2>/dev/null || echo "$1"
}

# Test 1: Vérifier la configuration
echo "1️⃣  Vérification de la configuration Paddle..."
config=$(curl -s "$BASE_URL/api/payments/paddle/verify-config")
show_json "$config"

status=$(echo "$config" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null)

if [ "$status" = "ok" ]; then
    echo "✅ Configuration Paddle OK"
else
    echo "❌ Problèmes de configuration détectés"
    echo "$config" | python3 -c "import sys, json; issues = json.load(sys.stdin).get('issues', []); [print(f'   - {issue}') for issue in issues]" 2>/dev/null
    exit 1
fi

echo ""

# Test 2: Lister les prix accessibles
echo "2️⃣  Liste des prix Paddle accessibles..."
prices=$(curl -s "$BASE_URL/api/payments/paddle/prices")
price_count=$(echo "$prices" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('prices', [])))" 2>/dev/null)

if [ "$price_count" = "0" ]; then
    echo "⚠️  Aucun prix trouvé. Vous devez créer des prix dans Paddle Dashboard."
    echo ""
    echo "📝 Instructions pour créer des prix:"
    echo "   1. Aller sur https://vendors.paddle.com/ (ou sandbox.paddle.com)"
    echo "   2. Catalog → Products → Create Product"
    echo "   3. Créer les produits suivants:"
    echo "      - Code 14 jours"
    echo "      - Code 30 jours"
    echo "      - Vidéos 1 mois"
    echo "      - Vidéos 2 mois"
    echo "      - Vidéos 3 mois"
    echo "   4. Pour chaque produit, créer un prix (Price)"
    echo "   5. Copier les prix IDs (format: pri_...)"
    echo ""
else
    echo "✅ Trouvé $price_count prix:"
    echo "$prices" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for price in data.get('prices', []):
    print(f\"   📦 ID: {price.get('id')}\")
    print(f\"      Nom: {price.get('name')}\")
    print(f\"      Montant: {price.get('amount')} {price.get('currency')}\")
    print(f\"      Status: {price.get('status')}\")
    print()
" 2>/dev/null
fi

echo ""

# Test 3: Tester l'authentification
echo "3️⃣  Test de l'authentification Paddle..."
auth=$(curl -s "$BASE_URL/api/payments/paddle/test-auth")
connection_ok=$(echo "$auth" | python3 -c "import sys, json; print(json.load(sys.stdin).get('connection_ok', False))" 2>/dev/null)

if [ "$connection_ok" = "True" ]; then
    echo "✅ Connexion à l'API Paddle OK"
    starts_with=$(echo "$auth" | python3 -c "import sys, json; print(json.load(sys.stdin).get('starts_with', 'N/A'))" 2>/dev/null)
    echo "   Clé commence par: $starts_with"
else
    api_message=$(echo "$auth" | python3 -c "import sys, json; print(json.load(sys.stdin).get('api_message', 'Unknown error'))" 2>/dev/null)
    echo "⚠️  Connexion API: $api_message"
fi

echo ""
echo "================================================="
echo "✅ Tests terminés"
echo ""
echo "📋 Prochaines étapes:"
echo "   1. Si aucun prix n'est trouvé, créez-les dans Paddle Dashboard"
echo "   2. Mettez à jour paddle_price_ids.json avec les nouveaux IDs"
echo "   3. Testez la création d'un checkout:"
echo "      ./test-paddle-checkout.sh <PRI_ID>"
echo ""
