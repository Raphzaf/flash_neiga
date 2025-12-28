# Script de test Paddle pour Flash Neiga
# Usage: .\test-paddle.ps1

Write-Host "🔍 Test de l'intégration Paddle pour Flash Neiga" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

$baseUrl = "http://localhost:8000"

# Fonction pour afficher les résultats JSON
function Show-JsonResult {
    param($response)
    $response | ConvertTo-Json -Depth 10 | Write-Host
}

# Test 1: Vérifier la configuration
Write-Host "1️⃣  Vérification de la configuration Paddle..." -ForegroundColor Yellow
try {
    $config = Invoke-RestMethod -Method GET -Uri "$baseUrl/api/payments/paddle/verify-config"
    Show-JsonResult $config
    
    if ($config.status -eq "ok") {
        Write-Host "✅ Configuration Paddle OK" -ForegroundColor Green
    } else {
        Write-Host "❌ Problèmes de configuration détectés:" -ForegroundColor Red
        $config.issues | ForEach-Object { Write-Host "   - $_" -ForegroundColor Red }
        exit 1
    }
} catch {
    Write-Host "❌ Erreur lors de la vérification: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Test 2: Lister les prix accessibles
Write-Host "2️⃣  Liste des prix Paddle accessibles..." -ForegroundColor Yellow
try {
    $prices = Invoke-RestMethod -Method GET -Uri "$baseUrl/api/payments/paddle/prices"
    
    if ($prices.prices.Count -eq 0) {
        Write-Host "⚠️  Aucun prix trouvé. Vous devez créer des prix dans Paddle Dashboard." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "📝 Instructions pour créer des prix:" -ForegroundColor Cyan
        Write-Host "   1. Aller sur https://vendors.paddle.com/ (ou sandbox.paddle.com)" -ForegroundColor White
        Write-Host "   2. Catalog → Products → Create Product" -ForegroundColor White
        Write-Host "   3. Créer les produits suivants:" -ForegroundColor White
        Write-Host "      - Code 14 jours" -ForegroundColor White
        Write-Host "      - Code 30 jours" -ForegroundColor White
        Write-Host "      - Vidéos 1 mois" -ForegroundColor White
        Write-Host "      - Vidéos 2 mois" -ForegroundColor White
        Write-Host "      - Vidéos 3 mois" -ForegroundColor White
        Write-Host "   4. Pour chaque produit, créer un prix (Price)" -ForegroundColor White
        Write-Host "   5. Copier les prix IDs (format: pri_...)" -ForegroundColor White
        Write-Host ""
    } else {
        Write-Host "✅ Trouvé $($prices.prices.Count) prix:" -ForegroundColor Green
        $prices.prices | ForEach-Object {
            Write-Host "   📦 ID: $($_.id)" -ForegroundColor White
            Write-Host "      Nom: $($_.name)" -ForegroundColor Gray
            Write-Host "      Montant: $($_.amount) $($_.currency)" -ForegroundColor Gray
            Write-Host "      Status: $($_.status)" -ForegroundColor Gray
            Write-Host ""
        }
    }
} catch {
    Write-Host "❌ Erreur lors de la récupération des prix: $_" -ForegroundColor Red
}

Write-Host ""

# Test 3: Tester l'authentification
Write-Host "3️⃣  Test de l'authentification Paddle..." -ForegroundColor Yellow
try {
    $auth = Invoke-RestMethod -Method GET -Uri "$baseUrl/api/payments/paddle/test-auth"
    
    if ($auth.connection_ok) {
        Write-Host "✅ Connexion à l'API Paddle OK" -ForegroundColor Green
        Write-Host "   Clé commence par: $($auth.starts_with)" -ForegroundColor Gray
    } else {
        Write-Host "⚠️  Connexion API: $($auth.api_message)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Erreur lors du test d'authentification: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "✅ Tests terminés" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Prochaines étapes:" -ForegroundColor Cyan
Write-Host "   1. Si aucun prix n'est trouvé, créez-les dans Paddle Dashboard" -ForegroundColor White
Write-Host "   2. Mettez à jour paddle_price_ids.json avec les nouveaux IDs" -ForegroundColor White
Write-Host "   3. Testez la création d'un checkout:" -ForegroundColor White
Write-Host "      .\test-paddle-checkout.ps1 <PRI_ID>" -ForegroundColor Gray
Write-Host ""
