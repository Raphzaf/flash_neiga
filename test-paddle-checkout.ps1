# Script pour tester la création d'un checkout Paddle
# Usage: .\test-paddle-checkout.ps1 <PRICE_ID> [EMAIL]

param(
    [Parameter(Mandatory=$true)]
    [string]$PriceId,
    
    [Parameter(Mandatory=$false)]
    [string]$Email = "test@example.com"
)

Write-Host "🛒 Test de création de checkout Paddle" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Price ID: $PriceId" -ForegroundColor White
Write-Host "Email: $Email" -ForegroundColor White
Write-Host ""

$baseUrl = "http://localhost:8000"

# Créer le payload
$body = @{
    priceId = $PriceId
    email = $Email
} | ConvertTo-Json

# Tester la création du checkout
Write-Host "1️⃣  Création du checkout..." -ForegroundColor Yellow
try {
    $checkout = Invoke-RestMethod -Method POST -Uri "$baseUrl/api/payments/paddle/create-checkout" `
        -ContentType "application/json" `
        -Body $body
    
    Write-Host "✅ Checkout créé avec succès!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📋 Détails:" -ForegroundColor Cyan
    Write-Host "   Checkout URL: $($checkout.checkoutUrl)" -ForegroundColor White
    Write-Host "   Checkout ID: $($checkout.checkoutId)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "🌐 Ouvrir dans le navigateur:" -ForegroundColor Cyan
    Write-Host "   $($checkout.checkoutUrl)" -ForegroundColor Blue
    Write-Host ""
    
    # Demander si on veut ouvrir le navigateur
    $open = Read-Host "Voulez-vous ouvrir le checkout dans le navigateur? (o/N)"
    if ($open -eq "o" -or $open -eq "O" -or $open -eq "oui") {
        Start-Process $checkout.checkoutUrl
    }
    
} catch {
    Write-Host "❌ Erreur lors de la création du checkout" -ForegroundColor Red
    
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "   Détails: $responseBody" -ForegroundColor Red
    } else {
        Write-Host "   Détails: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "💡 Causes possibles:" -ForegroundColor Yellow
    Write-Host "   - Le Price ID n'existe pas dans votre projet Paddle" -ForegroundColor White
    Write-Host "   - Le Price ID appartient à un autre projet/environnement" -ForegroundColor White
    Write-Host "   - La clé API n'a pas les permissions nécessaires" -ForegroundColor White
    Write-Host ""
    Write-Host "📝 Solution:" -ForegroundColor Cyan
    Write-Host "   1. Vérifier le Price ID dans Paddle Dashboard" -ForegroundColor White
    Write-Host "   2. S'assurer que la clé API et le prix sont dans le même projet" -ForegroundColor White
    Write-Host "   3. Vérifier que la clé a les permissions 'Transactions: Write'" -ForegroundColor White
    
    exit 1
}

Write-Host ""
Write-Host "✅ Test terminé avec succès" -ForegroundColor Green
