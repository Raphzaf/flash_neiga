# 📚 Guide de Déploiement - Paddle Integration

Ce guide explique comment configurer et déployer l'intégration Paddle pour Flash Neiga.

## 📋 Prérequis

1. Compte Paddle actif (https://paddle.com)
2. Compte Render pour le backend (https://render.com)
3. Compte Netlify pour le frontend (https://netlify.com)
4. Accès au repository GitHub

## 🔧 Configuration Paddle

### 1. Obtenir les clés API Paddle

1. Connectez-vous à votre [Paddle Dashboard](https://vendors.paddle.com/)
2. Allez dans **Developer Tools** → **Authentication**
3. Créez une nouvelle clé API:
   - Cliquez sur "Generate Key"
   - Donnez-lui un nom (ex: "Flash Neiga Backend")
   - Sélectionnez les permissions nécessaires:
     - ✅ **Transactions**: Read & Write
     - ✅ **Subscriptions**: Read & Write
     - ✅ **Prices**: Read
     - ✅ **Products**: Read
   - Cliquez sur "Create Key"
4. **IMPORTANT**: Copiez immédiatement la clé et sauvegardez-la en sécurité (elle ne sera affichée qu'une seule fois)

### 2. Obtenir le Webhook Secret

1. Dans le Paddle Dashboard, allez dans **Developer Tools** → **Notifications**
2. Cliquez sur "Add Notification Destination"
3. Configurez le webhook:
   - **URL**: `https://flash-neiga-backend.onrender.com/api/payments/paddle/webhook`
   - **Description**: "Flash Neiga Production Webhook"
   - Sélectionnez les événements à écouter:
     - ✅ `transaction.completed`
     - ✅ `transaction.paid`
     - ✅ `subscription.created`
     - ✅ `subscription.updated`
     - ✅ `subscription.canceled`
4. Cliquez sur "Save Destination"
5. Une fois créé, le **Secret Key** sera affiché - copiez-le et sauvegardez-le

### 3. Créer les produits et prix

#### a. Créer les produits de base

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configurer les variables d'environnement
export PADDLE_API_KEY="votre_clé_api"  # Sur Windows: set PADDLE_API_KEY=votre_clé_api

# Créer les produits et prix de base
python scripts/create_paddle_products.py
```

Ce script créera:
- Produit "Flash Neiga - Code Subscription" avec prix pour 14 et 30 jours
- Produit "Flash Neiga - Vidéos Pédagogiques" avec prix pour 1, 2 et 3 mois

Les price IDs seront affichés dans la console et sauvegardés dans `paddle_prices_output.json`.

#### b. Créer les extensions hebdomadaires

```bash
# Même environnement que ci-dessus
python scripts/create_paddle_extensions.py
```

Ce script créera:
- Extension Code 1 semaine (49₪)
- Extension Vidéos 1 semaine (49₪)

Les price IDs seront affichés et sauvegardés dans `paddle_extensions_output.json`.

#### c. Mettre à jour la configuration

1. Mettez à jour `paddle_price_ids.json` avec les nouveaux price IDs
2. Mettez à jour `frontend/.env.production` avec les price IDs des extensions

## 🚀 Configuration Render (Backend)

### 1. Via le Dashboard Render

1. Connectez-vous à [Render Dashboard](https://dashboard.render.com/)
2. Sélectionnez votre service "flash-neiga-backend"
3. Allez dans **Environment** → **Environment Variables**
4. Ajoutez les variables suivantes:

```
PADDLE_API_KEY=pdl_live_xxxxxxxxxxxxxxxxxxxxxxxx
PADDLE_WEBHOOK_SECRET=pdl_ntfset_xxxxxxxxxxxxxxxxxxxxxxxx
ALLOWED_ORIGINS=https://appflashneiga.netlify.app,https://flash-neiga.netlify.app
```

5. Cliquez sur "Save Changes"
6. Le service redémarrera automatiquement

### 2. Via render.yaml (déjà configuré)

Le fichier `render.yaml` est déjà configuré pour inclure ces variables.
Elles doivent être définies manuellement dans le dashboard Render car elles contiennent des secrets.

```yaml
envVars:
  - key: PADDLE_API_KEY
    sync: false  # À définir manuellement
  - key: PADDLE_WEBHOOK_SECRET
    sync: false  # À définir manuellement
  - key: ALLOWED_ORIGINS
    value: "https://appflashneiga.netlify.app,https://flash-neiga.netlify.app"
```

## 🌐 Configuration Netlify (Frontend)

### 1. Mise à jour des variables d'environnement

Le fichier `frontend/.env.production` contient déjà les price IDs.
Assurez-vous de mettre à jour les extensions si vous les avez créées:

```env
REACT_APP_PADDLE_PRICE_CODE_EXT=pri_xxxxxxxxxxxxx
REACT_APP_PADDLE_PRICE_VIDEO_EXT=pri_xxxxxxxxxxxxx
```

### 2. Redéploiement

1. Committez les changements:
```bash
git add .
git commit -m "Update Paddle extension price IDs"
git push
```

2. Netlify redéploiera automatiquement le frontend

## 🧪 Tests et Vérification

### 1. Vérifier la configuration backend

```bash
# Test 1: Vérifier que Paddle est configuré
curl https://flash-neiga-backend.onrender.com/api/payments/paddle/health

# Devrait retourner: {"paddle_configured": true}

# Test 2: Vérifier la configuration complète
curl https://flash-neiga-backend.onrender.com/api/payments/paddle/verify-config

# Devrait retourner:
# {
#   "api_key_configured": true,
#   "webhook_secret_configured": true,
#   "api_connection_ok": true,
#   "price_ids_accessible": true,
#   "status": "ok",
#   "issues": []
# }

# Test 3: Tester l'authentification
curl https://flash-neiga-backend.onrender.com/api/payments/paddle/test-auth

# Devrait retourner:
# {
#   "key_exists": true,
#   "key_length": XX,
#   "starts_with": "pdl_live" ou "pdl_test",
#   "format_ok": true,
#   "connection_ok": true,
#   "api_message": "Successfully connected to Paddle API"
# }
```

### 2. Tester la création de checkout

1. Allez sur https://appflashneiga.netlify.app/pricing
2. Cliquez sur un bouton de souscription
3. Vérifiez que vous êtes redirigé vers la page de paiement Paddle
4. **NE PAS** compléter le paiement en test à moins d'utiliser des cartes de test

### 3. Tester les webhooks

1. Effectuez un paiement test sur Paddle (utilisez une carte de test)
2. Vérifiez les logs du backend Render pour voir les événements webhook:
   - `transaction.completed`
   - `transaction.paid`
3. Vérifiez que les transactions sont enregistrées dans la base de données

### 4. Tester l'offre combinée

Pour tester l'offre combinée:

1. Créez un compte utilisateur
2. Souscrivez au Code (14 ou 30 jours)
3. Souscrivez aux Vidéos 3 mois
4. Vérifiez dans les logs backend que vous voyez:
   ```
   🎁 COMBO OFFER ELIGIBLE: User {user_id} qualifies for 2 free lessons
   ```

## 🐛 Troubleshooting

### Erreur: "Paddle not configured: set PADDLE_API_KEY env var on backend"

**Cause**: La variable d'environnement `PADDLE_API_KEY` n'est pas définie sur Render.

**Solution**:
1. Vérifiez que `PADDLE_API_KEY` est définie dans le dashboard Render
2. Vérifiez que la clé commence par `pdl_live_` ou `pdl_test_`
3. Vérifiez qu'il n'y a pas de guillemets ou d'espaces autour de la clé
4. Redémarrez le service Render

### Erreur: "Paddle authentication malformed"

**Cause**: La clé API contient des caractères invalides (guillemets, espaces).

**Solution**:
1. Dans Render, éditez `PADDLE_API_KEY`
2. Supprimez tous les guillemets et espaces
3. La clé doit ressembler à: `pdl_live_1234567890abcdef...`
4. Sauvegardez et redémarrez

### Erreur: "Paddle forbidden: key is valid but not permitted"

**Cause**: La clé API n'a pas les permissions nécessaires ou est dans le mauvais environnement.

**Solutions**:
1. Vérifiez que la clé API a les permissions **Transactions: Read & Write**
2. Vérifiez que vous utilisez le bon environnement (live vs test)
3. Vérifiez que les price IDs correspondent au même environnement que la clé
4. Recréez la clé API si nécessaire

### Erreur: "Price not found for this API key/project"

**Cause**: Le price ID n'existe pas ou appartient à un autre projet/environnement.

**Solutions**:
1. Vérifiez que le price ID existe dans votre Paddle Dashboard
2. Vérifiez que vous utilisez le bon environnement (live vs test)
3. Recréez les prix avec le script `create_paddle_products.py`

### Les webhooks ne sont pas reçus

**Causes possibles**:
1. L'URL du webhook est incorrecte
2. Le webhook secret est incorrect
3. Le backend n'est pas accessible publiquement

**Solutions**:
1. Vérifiez l'URL du webhook dans Paddle Dashboard:
   - Doit être: `https://flash-neiga-backend.onrender.com/api/payments/paddle/webhook`
2. Vérifiez que `PADDLE_WEBHOOK_SECRET` est correctement défini
3. Testez l'endpoint manuellement:
   ```bash
   curl -X POST https://flash-neiga-backend.onrender.com/api/payments/paddle/webhook
   # Devrait retourner une erreur 400 (normal sans signature)
   ```
4. Vérifiez les logs Render pour voir les requêtes webhook

### Extension hebdomadaire affiche "TO_BE_CREATED"

**Cause**: Les price IDs des extensions n'ont pas été créés.

**Solution**:
1. Exécutez le script `backend/scripts/create_paddle_extensions.py`
2. Mettez à jour `paddle_price_ids.json` avec les nouveaux IDs
3. Mettez à jour `frontend/.env.production`
4. Redéployez le frontend

## 📊 Monitoring

### Logs Backend (Render)

1. Allez dans le dashboard Render
2. Sélectionnez "flash-neiga-backend"
3. Cliquez sur "Logs"
4. Recherchez:
   - `Creating Paddle checkout` - création de checkout
   - `Received Paddle webhook` - réception de webhooks
   - `🎁 COMBO OFFER` - offre combinée détectée

### Dashboard Paddle

1. Connectez-vous au Paddle Dashboard
2. Allez dans **Transactions** pour voir les paiements
3. Allez dans **Subscriptions** pour voir les abonnements actifs
4. Allez dans **Developer Tools** → **Events** pour voir l'historique des webhooks

## 🔒 Sécurité

### Bonnes pratiques

1. **Ne jamais committer les clés API**:
   - Utilisez uniquement les variables d'environnement
   - Ajoutez `.env*` au `.gitignore`

2. **Rotation des clés**:
   - Changez les clés API tous les 90 jours
   - Utilisez le système de rotation de Paddle

3. **Vérification des webhooks**:
   - `PADDLE_WEBHOOK_SECRET` doit toujours être défini
   - Vérifiez les signatures webhook (déjà implémenté)

4. **Environnements séparés**:
   - Utilisez des clés de test en développement
   - Utilisez des clés live uniquement en production

## 📞 Support

Si vous rencontrez des problèmes non couverts par ce guide:

1. **Documentation Paddle**: https://developer.paddle.com/
2. **Support Paddle**: https://paddle.com/support
3. **Repository GitHub**: Ouvrez une issue avec les logs d'erreur

## ✅ Checklist de déploiement

- [ ] Clé API Paddle créée avec les bonnes permissions
- [ ] Webhook Paddle configuré
- [ ] Webhook secret récupéré
- [ ] Produits et prix créés via `create_paddle_products.py`
- [ ] Extensions créées via `create_paddle_extensions.py`
- [ ] `PADDLE_API_KEY` définie sur Render
- [ ] `PADDLE_WEBHOOK_SECRET` définie sur Render
- [ ] `ALLOWED_ORIGINS` définie sur Render
- [ ] `paddle_price_ids.json` mis à jour
- [ ] `frontend/.env.production` mis à jour
- [ ] Tests de configuration passés (`/paddle/verify-config`)
- [ ] Test de checkout réussi
- [ ] Test de webhook réussi
- [ ] Offre combinée testée et fonctionnelle

## 🎯 Résumé des URLs

- **Frontend Production**: https://appflashneiga.netlify.app
- **Backend Production**: https://flash-neiga-backend.onrender.com
- **Paddle Dashboard**: https://vendors.paddle.com
- **Endpoint Health**: `/api/payments/paddle/health`
- **Endpoint Verify Config**: `/api/payments/paddle/verify-config`
- **Endpoint Test Auth**: `/api/payments/paddle/test-auth`
- **Endpoint Webhook**: `/api/payments/paddle/webhook`
