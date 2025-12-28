# 🔧 Guide de Configuration Paddle pour Flash Neiga

## 📋 Résumé du Problème

Les price IDs actuels dans `paddle_price_ids.json` ne correspondent pas à la clé API Paddle configurée. Cela cause des erreurs 403 lors de la création de checkouts.

**Cause:** Les prix (`pri_...`) et la clé API (`pdl_live_...` ou `pdl_test_...`) doivent appartenir au même projet et environnement Paddle.

## ✅ Solution en 4 Étapes

### Étape 1: Vérifier la Configuration Actuelle

```powershell
# Démarrer le backend
cd backend
python server.py

# Dans un autre terminal, tester la configuration
cd ..
.\test-paddle.ps1
```

**Résultat attendu:**
- ✅ `verify-config.status = "ok"`
- ✅ `connection_ok = true`
- Liste des prix accessibles (peut être vide)

### Étape 2: Créer les Prix dans Paddle Dashboard

1. **Se connecter à Paddle:**
   - Sandbox: https://sandbox-vendors.paddle.com/
   - Production: https://vendors.paddle.com/

2. **Créer les Produits:**
   - Aller dans **Catalog → Products**
   - Cliquer **"+ Create Product"**
   - Créer 5 produits:

   | Produit | Nom Suggéré | Description |
   |---------|-------------|-------------|
   | Code 14j | Flash Neiga - Code 14 jours | Accès au code de la route pendant 14 jours |
   | Code 30j | Flash Neiga - Code 30 jours | Accès au code de la route pendant 30 jours |
   | Vidéos 1m | Flash Neiga - Vidéos 1 mois | Accès aux vidéos pédagogiques pendant 1 mois |
   | Vidéos 2m | Flash Neiga - Vidéos 2 mois | Accès aux vidéos pédagogiques pendant 2 mois |
   | Vidéos 3m | Flash Neiga - Vidéos 3 mois | Accès aux vidéos pédagogiques pendant 3 mois |

3. **Créer les Prix pour Chaque Produit:**
   - Pour chaque produit, cliquer **"Add Price"**
   - Configurer:
     - **Billing Type:** One-time (ou Recurring si abonnement)
     - **Currency:** EUR (ou USD selon votre préférence)
     - **Amount:** Le prix de vente
   - Cliquer **"Save"**
   - **Copier le Price ID** (format: `pri_01xxxxxxxxxxxxx`)

4. **Noter les Price IDs:**
   ```
   Code 14 jours:  pri_________________
   Code 30 jours:  pri_________________
   Vidéos 1 mois:  pri_________________
   Vidéos 2 mois:  pri_________________
   Vidéos 3 mois:  pri_________________
   ```

### Étape 3: Mettre à Jour les Price IDs

**Option A: Script Automatique (Recommandé)**

```powershell
.\update-paddle-prices.ps1
```

Suivez les instructions à l'écran pour entrer les nouveaux Price IDs.

**Option B: Mise à Jour Manuelle**

1. **Éditer `paddle_price_ids.json`:**
   ```json
   {
     "code": {
       "14days": "pri_01xxxxxxxxxxxxx",
       "30days": "pri_01xxxxxxxxxxxxx"
     },
     "videos": {
       "1month": "pri_01xxxxxxxxxxxxx",
       "2months": "pri_01xxxxxxxxxxxxx",
       "3months": "pri_01xxxxxxxxxxxxx"
     }
   }
   ```

2. **Éditer `frontend/.env.production`:**
   ```env
   REACT_APP_PADDLE_PRICE_CODE_14D=pri_01xxxxxxxxxxxxx
   REACT_APP_PADDLE_PRICE_CODE_30D=pri_01xxxxxxxxxxxxx
   REACT_APP_PADDLE_PRICE_VIDEO_1M=pri_01xxxxxxxxxxxxx
   REACT_APP_PADDLE_PRICE_VIDEO_2M=pri_01xxxxxxxxxxxxx
   REACT_APP_PADDLE_PRICE_VIDEO_3M=pri_01xxxxxxxxxxxxx
   ```

3. **Si le frontend utilise un fichier paddlePrices.js, le mettre à jour aussi**

### Étape 4: Tester les Checkouts

```powershell
# Tester avec le premier prix
.\test-paddle-checkout.ps1 pri_01xxxxxxxxxxxxx

# Tester avec les autres prix
.\test-paddle-checkout.ps1 pri_01yyyyyyyyyyyyy
```

**Résultat attendu:**
- ✅ Checkout créé avec succès
- ✅ URL de checkout générée
- ✅ Possibilité d'ouvrir le checkout dans le navigateur

## 🔐 Configuration du Webhook

Une fois les checkouts fonctionnels, configurez le webhook:

1. **Dans Paddle Dashboard:**
   - Developer Tools → Notifications → Webhook URLs
   - Cliquer **"+ Add Webhook Destination"**

2. **Configurer:**
   - **URL:** `https://votre-backend.onrender.com/api/payments/paddle/webhook`
   - **Events:** Sélectionner tous les événements transactions et subscriptions
   - Cliquer **"Save"**

3. **Copier le Webhook Secret** (affiché une seule fois)

4. **Mettre à jour `backend/.env`:**
   ```env
   PADDLE_WEBHOOK_SECRET=pdl_ntfset_xxxxxxxxxxxxx
   ```

5. **Redémarrer le backend** pour prendre en compte le secret

## 🧪 Tests de Bout en Bout

### Test 1: Configuration
```powershell
.\test-paddle.ps1
```
- ✅ Configuration OK
- ✅ Connexion API OK
- ✅ Prix listés

### Test 2: Création de Checkout
```powershell
.\test-paddle-checkout.ps1 <PRICE_ID>
```
- ✅ Checkout créé
- ✅ URL générée

### Test 3: Paiement Test (Sandbox Uniquement)
1. Ouvrir l'URL du checkout
2. Utiliser une carte de test Paddle:
   - Numéro: `4242 4242 4242 4242`
   - Date: n'importe quelle date future
   - CVC: n'importe quel code à 3 chiffres
3. Compléter le paiement

### Test 4: Vérifier le Webhook
1. Après le paiement test
2. Vérifier les logs du backend: `event_type=transaction.completed`
3. Vérifier la base de données:
   ```powershell
   cd backend
   python -c "from database import SessionLocal; from models import TransactionDB; db = SessionLocal(); print(f'Transactions: {db.query(TransactionDB).count()}'); db.close()"
   ```

## 🚨 Dépannage

### Erreur 403 "Forbidden"
**Cause:** La clé API et le prix ne sont pas dans le même projet/environnement

**Solution:**
1. Vérifier que la clé commence par `pdl_live_` ou `pdl_test_`
2. Vérifier que le prix commence par `pri_01`
3. S'assurer qu'ils sont créés dans le même compte Paddle
4. Recréer les prix sous la bonne clé si nécessaire

### Erreur 401 "Unauthorized"
**Cause:** Clé API invalide ou expirée

**Solution:**
1. Vérifier `backend/.env` → `PADDLE_API_KEY`
2. Régénérer une nouvelle clé dans Paddle Dashboard
3. Mettre à jour `.env` et redémarrer le backend

### Aucun prix trouvé
**Cause:** Aucun prix créé ou clé API sans permissions

**Solution:**
1. Créer les prix dans Paddle Dashboard (voir Étape 2)
2. Vérifier les permissions de la clé API (Transactions: Read)

### Webhook ne reçoit rien
**Cause:** URL incorrecte ou secret non configuré

**Solution:**
1. Vérifier l'URL du webhook dans Paddle Dashboard
2. Tester avec ngrok en local (voir README.md)
3. Configurer `PADDLE_WEBHOOK_SECRET` dans `.env`

## 📚 Ressources

- [Documentation Paddle Billing](https://developer.paddle.com/billing)
- [Créer des Produits et Prix](https://developer.paddle.com/billing/products)
- [Webhooks Paddle](https://developer.paddle.com/webhooks/overview)
- [Cartes de Test](https://developer.paddle.com/concepts/payment-methods/credit-debit-card)

## ✅ Checklist Finale

- [ ] Clé API Paddle configurée dans `backend/.env`
- [ ] 5 produits créés dans Paddle Dashboard
- [ ] 5 prix créés (1 par produit)
- [ ] Price IDs copiés depuis Paddle Dashboard
- [ ] `paddle_price_ids.json` mis à jour
- [ ] `frontend/.env.production` mis à jour
- [ ] Backend redémarré
- [ ] Tests de configuration réussis (.\test-paddle.ps1)
- [ ] Tests de checkout réussis pour au moins 1 prix
- [ ] Webhook configuré dans Paddle Dashboard
- [ ] Webhook secret configuré dans `backend/.env`
- [ ] Test de paiement réussi (sandbox)
- [ ] Transaction enregistrée dans la base de données

## 🎉 Félicitations!

Votre intégration Paddle est maintenant complète et fonctionnelle!
