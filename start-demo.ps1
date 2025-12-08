# Script de démarrage rapide pour la démo Flash Neiga
# Usage: .\start-demo.ps1

Write-Host "=== Flash Neiga - Démarrage de la démo ===" -ForegroundColor Cyan

# Variables d'environnement
$MONGO_URL = "mongodb://localhost:27017"  # À remplacer par votre MongoDB Atlas URI
$DB_NAME = "flash_neiga"
$SECRET_KEY = "demo-secret-key-change-in-production"
$BACKEND_URL = "http://localhost:8000"

Write-Host "`n1. Configuration de l'environnement..." -ForegroundColor Yellow
$env:MONGO_URL = $MONGO_URL
$env:DB_NAME = $DB_NAME
$env:SECRET_KEY = $SECRET_KEY

# Démarrer le backend
Write-Host "`n2. Démarrage du backend (FastAPI)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\backend'; ..\..venv\Scripts\Activate.ps1; `$env:MONGO_URL='$MONGO_URL'; `$env:DB_NAME='$DB_NAME'; `$env:SECRET_KEY='$SECRET_KEY'; python -m uvicorn server:app --reload --port 8000"

Start-Sleep -Seconds 3

# Démarrer le frontend
Write-Host "`n3. Démarrage du frontend (React)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; `$env:REACT_APP_BACKEND_URL='$BACKEND_URL'; npm start"

Write-Host "`n✓ Démarrage terminé!" -ForegroundColor Green
Write-Host "`nBackend: http://localhost:8000" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "`nAppuyez sur une touche pour quitter..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
