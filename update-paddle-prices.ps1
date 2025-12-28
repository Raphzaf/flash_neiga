# Script pour mettre à jour les Price IDs Paddle
# Usage: .\update-paddle-prices.ps1

Write-Host "🔄 Mise à jour des Price IDs Paddle" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Lire les prix actuels
$priceIdsFile = "paddle_price_ids.json"
if (Test-Path $priceIdsFile) {
    $currentPrices = Get-Content $priceIdsFile | ConvertFrom-Json
    Write-Host "📋 Prix actuels:" -ForegroundColor Yellow
    Write-Host ($currentPrices | ConvertTo-Json -Depth 10)
    Write-Host ""
}

Write-Host "Veuillez entrer les nouveaux Price IDs depuis votre Paddle Dashboard" -ForegroundColor Cyan
Write-Host "(Format: pri_xxxxxxxxxxxxxxxxxxxxx)" -ForegroundColor Gray
Write-Host ""

# Demander les nouveaux IDs
$newPrices = @{
    code = @{
        "14days" = Read-Host "Code 14 jours (pri_...)"
        "30days" = Read-Host "Code 30 jours (pri_...)"
    }
    videos = @{
        "1month" = Read-Host "Vidéos 1 mois (pri_...)"
        "2months" = Read-Host "Vidéos 2 mois (pri_...)"
        "3months" = Read-Host "Vidéos 3 mois (pri_...)"
    }
}

Write-Host ""
Write-Host "📝 Nouveaux prix:" -ForegroundColor Yellow
Write-Host ($newPrices | ConvertTo-Json -Depth 10)
Write-Host ""

# Confirmation
$confirm = Read-Host "Voulez-vous sauvegarder ces prix? (o/N)"
if ($confirm -ne "o" -and $confirm -ne "O" -and $confirm -ne "oui") {
    Write-Host "❌ Annulé" -ForegroundColor Red
    exit 0
}

# Sauvegarder paddle_price_ids.json
$newPrices | ConvertTo-Json -Depth 10 | Set-Content $priceIdsFile
Write-Host "✅ Sauvegardé dans $priceIdsFile" -ForegroundColor Green

# Mettre à jour frontend/.env.production
$frontendEnvProd = "frontend/.env.production"
$envContent = @"
# Production environment variables for Netlify deployment
# Backend URL is handled by Netlify proxy (see netlify.toml)
# Do NOT set REACT_APP_BACKEND_URL in production

# Paddle Price IDs from paddle_price_ids.json
# Code access subscriptions
REACT_APP_PADDLE_PRICE_CODE_14D=$($newPrices.code."14days")
REACT_APP_PADDLE_PRICE_CODE_30D=$($newPrices.code."30days")

# Video access subscriptions
REACT_APP_PADDLE_PRICE_VIDEO_1M=$($newPrices.videos."1month")
REACT_APP_PADDLE_PRICE_VIDEO_2M=$($newPrices.videos."2months")
REACT_APP_PADDLE_PRICE_VIDEO_3M=$($newPrices.videos."3months")
"@

$envContent | Set-Content $frontendEnvProd
Write-Host "✅ Mis à jour $frontendEnvProd" -ForegroundColor Green

# Chercher et mettre à jour paddlePrices.js
$paddlePricesFiles = Get-ChildItem -Path "frontend/src" -Filter "*paddle*.js" -Recurse -ErrorAction SilentlyContinue

if ($paddlePricesFiles.Count -gt 0) {
    Write-Host ""
    Write-Host "⚠️  Fichiers Paddle trouvés dans le frontend:" -ForegroundColor Yellow
    $paddlePricesFiles | ForEach-Object {
        Write-Host "   - $($_.FullName)" -ForegroundColor White
    }
    Write-Host ""
    Write-Host "💡 Vous devez mettre à jour manuellement ces fichiers avec les nouveaux IDs" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "ℹ️  Aucun fichier paddle*.js trouvé dans frontend/src" -ForegroundColor Gray
}

Write-Host ""
Write-Host "✅ Mise à jour terminée!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Prochaines étapes:" -ForegroundColor Cyan
Write-Host "   1. Vérifier paddle_price_ids.json" -ForegroundColor White
Write-Host "   2. Vérifier frontend/.env.production" -ForegroundColor White
Write-Host "   3. Mettre à jour manuellement les fichiers JS si nécessaire" -ForegroundColor White
Write-Host "   4. Tester avec: .\test-paddle-checkout.ps1 <PRICE_ID>" -ForegroundColor White
Write-Host ""
