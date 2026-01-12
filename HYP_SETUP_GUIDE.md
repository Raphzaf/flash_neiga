# HYP Payment Integration - Setup Guide

## 📋 Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Identifiants HYP](#identifiants-hyp)
3. [Architecture de l'intégration](#architecture-de-lintégration)
4. [Configuration](#configuration)
5. [Plans et tarification](#plans-et-tarification)
6. [Flow de paiement](#flow-de-paiement)
7. [Endpoints API](#endpoints-api)
8. [Gestion des callbacks](#gestion-des-callbacks)
9. [Tests et débogage](#tests-et-débogage)
10. [Déploiement en production](#déploiement-en-production)
11. [Troubleshooting](#troubleshooting)

---

## 🎯 Vue d'ensemble

Flash Neiga utilise **HYP** (plateforme de paiement israélienne) pour gérer les paiements et abonnements. L'intégration utilise le mode **page de paiement hébergée** avec redirection.

### Type d'intégration
- **Mode**: Page de paiement hébergée (hosted payment page)
- **Flow**: Backend crée un lien de paiement → Redirection utilisateur → Callback sur succès/échec
- **Gestion abonnements**: Logique côté backend (dates, renouvellements), HYP pour paiements uniquement

### Documentation officielle
- **HYP Developers**: https://developers.hyp.co.il/
- **Payment Page Integration**: https://developers.hyp.co.il/payment-page-integration/integrating-hyps-payment-page-and-accepting-payment

---

## 🔑 Identifiants HYP

### Credentials de production

```bash
HYP_TERMINAL_ID=4502176330
HYP_USER_ID=pveda
HYP_API_KEY=b9fe11a4da3235058399366f1a69d136a757b592
HYP_API_URL=https://icom.yaad.net/p/
```

⚠️ **IMPORTANT**: Ne jamais commiter la vraie API key dans le code. Utiliser les variables d'environnement.

---

## 🏗️ Architecture de l'intégration

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Frontend  │         │   Backend   │         │     HYP     │
│   (React)   │         │  (FastAPI)  │         │  (Payment)  │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                        │
       │ 1. Click "Subscribe"  │                        │
       ├──────────────────────>│                        │
       │                       │                        │
       │                       │ 2. Create payment      │
       │                       ├───────────────────────>│
       │                       │                        │
       │                       │ 3. Return payment URL  │
       │                       │<───────────────────────┤
       │                       │                        │
       │ 4. Redirect to HYP    │                        │
       │<──────────────────────┤                        │
       │                       │                        │
       │ 5. User pays on HYP   │                        │
       ├──────────────────────────────────────────────>│
       │                       │                        │
       │                       │ 6. Callback (webhook)  │
       │                       │<───────────────────────┤
       │                       │                        │
       │                       │ 7. Create subscription │
       │                       │    + Update transaction│
       │                       │                        │
       │ 8. Redirect to success│                        │
       │<──────────────────────────────────────────────┤
       │                       │                        │
```

---

## ⚙️ Configuration

### 1. Backend (.env)

Créer un fichier `.env` dans le dossier `backend/`:

```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/flash_neiga

# Security
SECRET_KEY=your-secret-key-here

# HYP Configuration
HYP_TERMINAL_ID=4502176330
HYP_USER_ID=pveda
HYP_API_KEY=your-api-key-here
HYP_API_URL=https://icom.yaad.net/p/

# HYP Callback URLs
HYP_SUCCESS_URL=http://localhost:3000/payment/success
HYP_ERROR_URL=http://localhost:3000/payment/failure
HYP_CALLBACK_URL=http://localhost:8000/api/payments/hyp/callback
```

### 2. Frontend (.env)

Créer un fichier `.env` dans le dossier `frontend/`:

```bash
REACT_APP_BACKEND_URL=http://localhost:8000
```

### 3. Render (Production)

Dans le dashboard Render, configurer les variables d'environnement:
- `HYP_API_KEY` (sensible, ne pas mettre dans render.yaml)
- `HYP_SUCCESS_URL` (URL frontend production)
- `HYP_ERROR_URL` (URL frontend production)
- `HYP_CALLBACK_URL` (URL backend production)

---

## 💰 Plans et tarification

Les plans sont définis dans `hyp_plans.json`:

### Abonnements Code

| Plan ID     | Nom                      | Prix | Durée    |
|-------------|--------------------------|------|----------|
| `code_14d`  | Abonnement Code 14 jours | 99₪  | 14 jours |
| `code_30d`  | Abonnement Code 30 jours | 159₪ | 30 jours |
| `code_ext`  | Extension Code 1 semaine | 59₪  | 7 jours  |

### Vidéos Pédagogiques

| Plan ID     | Nom                         | Prix | Durée    |
|-------------|-----------------------------|------|----------|
| `video_1m`  | Vidéos Pédagogiques 1 mois  | 199₪ | 30 jours |
| `video_2m`  | Vidéos Pédagogiques 2 mois  | 339₪ | 60 jours |
| `video_3m`  | Vidéos Pédagogiques 3 mois  | 419₪ | 90 jours |
| `video_ext` | Extension Vidéos 1 semaine  | 59₪  | 7 jours  |

### Format du fichier

```json
{
  "code_14d": {
    "name": "Abonnement Code 14 jours",
    "description": "Accès Web App, E-book, Questions officielles...",
    "amount": 99,
    "currency": "ILS",
    "duration_days": 14,
    "type": "code"
  }
}
```

---

## 🔄 Flow de paiement

### 1. Création du paiement

**Frontend** → **Backend**:
```javascript
POST /api/payments/hyp/create-payment
{
  "plan_id": "code_14d",
  "user_email": "user@example.com"
}
```

**Backend** → **HYP API**:
- Crée une transaction dans la DB (status: "pending")
- Génère l'URL de paiement HYP
- Retourne l'URL au frontend

**Réponse**:
```json
{
  "payment_url": "https://icom.yaad.net/p/...",
  "transaction_id": "uuid-here",
  "plan_id": "code_14d",
  "amount": 99,
  "currency": "ILS"
}
```

### 2. Redirection utilisateur

Le frontend redirige l'utilisateur vers `payment_url`.

### 3. Paiement sur HYP

L'utilisateur entre ses informations de carte sur la page HYP.

### 4. Callback

**HYP** → **Backend**:
```
POST /api/payments/hyp/callback
{
  "CCode": "0",           // 0 = success
  "ACode": "approval",
  "Id": "hyp-transaction-id",
  "Order": "transaction-id",
  "Amount": "9900"        // en agorot (99₪ × 100)
}
```

**Backend**:
- Vérifie la signature (si disponible)
- Met à jour la transaction (status: "completed")
- Crée ou étend l'abonnement
- Calcule les dates start_date et end_date

### 5. Redirection finale

**HYP** redirige l'utilisateur vers:
- `HYP_SUCCESS_URL?transaction_id=xxx` (succès)
- `HYP_ERROR_URL?transaction_id=xxx` (échec)

---

## 🔌 Endpoints API

### `GET /api/payments/hyp/verify-config`

Vérifie la configuration HYP.

**Réponse**:
```json
{
  "hyp_configured": true,
  "terminal_id": "4502176330",
  "user_id": "pveda",
  "api_url": "https://icom.yaad.net/p/",
  "plans_loaded": 7,
  "available_plans": ["code_14d", "code_30d", ...]
}
```

### `GET /api/payments/hyp/plans`

Liste tous les plans disponibles.

**Réponse**:
```json
{
  "plans": { ... },
  "count": 7
}
```

### `POST /api/payments/hyp/create-payment`

Crée un lien de paiement HYP.

**Body**:
```json
{
  "plan_id": "code_14d",
  "user_id": "optional-user-id",
  "user_email": "user@example.com"
}
```

### `POST /api/payments/hyp/callback`

Reçoit les callbacks de HYP (webhook).

### `GET /api/payments/hyp/transaction/{transaction_id}`

Récupère les détails d'une transaction.

### `GET /api/payments/hyp/subscriptions/{user_id}`

Liste tous les abonnements d'un utilisateur.

---

## 🔔 Gestion des callbacks

### Vérification de la signature

HYP envoie une signature pour vérifier l'authenticité du callback. La fonction `verify_hyp_callback()` doit être implémentée selon la documentation HYP.

### Status codes

- `CCode = 0`: Paiement réussi
- `CCode != 0`: Paiement échoué

### Gestion des extensions

Si le plan a `is_extension: true` et qu'un abonnement actif existe:
- L'extension prolonge la date de fin existante
- Sinon, crée un nouvel abonnement

### Statuts d'abonnement

- `active`: Abonnement en cours
- `expired`: Abonnement expiré
- `cancelled`: Abonnement annulé

---

## 🧪 Tests et débogage

### Script de test

```bash
cd backend
python scripts/test_hyp_integration.py
```

Ce script teste:
1. Configuration HYP
2. Endpoint verify-config
3. Endpoint get plans
4. Création de paiement
5. Récupération de transaction

### Tests manuels

1. **Lancer le backend**:
```bash
cd backend
uvicorn server:app --reload
```

2. **Lancer le frontend**:
```bash
cd frontend
npm start
```

3. **Tester un paiement**:
- Aller sur http://localhost:3000/pricing
- Cliquer sur "Souscrire"
- Vérifier la redirection vers HYP
- Tester avec une carte de test HYP

### Logs

Activer les logs détaillés:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 🚀 Déploiement en production

### 1. Configurer Render

Dans le dashboard Render:

1. Aller dans le service `flash-neiga-backend`
2. Aller dans "Environment"
3. Ajouter les variables:
   - `HYP_API_KEY` = votre clé API
   - `HYP_SUCCESS_URL` = `https://appflashneiga.netlify.app/payment/success`
   - `HYP_ERROR_URL` = `https://appflashneiga.netlify.app/payment/failure`
   - `HYP_CALLBACK_URL` = `https://flash-neiga-backend.onrender.com/api/payments/hyp/callback`

### 2. Configurer Netlify

Variables d'environnement:
- `REACT_APP_BACKEND_URL` = `https://flash-neiga-backend.onrender.com`

### 3. Vérifier le déploiement

```bash
curl https://flash-neiga-backend.onrender.com/api/payments/hyp/verify-config
```

### 4. Configurer HYP

Dans le dashboard HYP:
1. Ajouter l'URL de callback: `https://flash-neiga-backend.onrender.com/api/payments/hyp/callback`
2. Vérifier que le terminal est actif
3. Configurer les URLs de succès/échec

---

## 🔧 Troubleshooting

### Problème: "HYP API key not configured"

**Solution**: Vérifier que `HYP_API_KEY` est défini dans les variables d'environnement.

### Problème: "Invalid plan_id"

**Solution**: Vérifier que le plan existe dans `hyp_plans.json`.

### Problème: "Transaction not found"

**Solution**: Le callback n'a pas reçu le bon `transaction_id`. Vérifier les logs HYP.

### Problème: Callback non reçu

**Solutions**:
1. Vérifier que l'URL de callback est accessible publiquement
2. Vérifier les logs du backend
3. Vérifier la configuration dans le dashboard HYP
4. Utiliser un outil comme ngrok pour tester localement

### Problème: Montant incorrect

**Solution**: HYP attend le montant en **agorot** (multiplier par 100). Exemple: 99₪ = 9900 agorot.

### Problème: Redirection échoue

**Solutions**:
1. Vérifier les URLs de succès/échec
2. Vérifier les CORS
3. Tester manuellement l'URL de redirection

---

## 📚 Ressources

- **Documentation HYP**: https://developers.hyp.co.il/
- **Payment Page Integration**: https://developers.hyp.co.il/payment-page-integration/integrating-hyps-payment-page-and-accepting-payment
- **Code source**: `backend/routes/hyp_payments.py`
- **Frontend config**: `frontend/src/config/hypConfig.js`
- **Plans**: `hyp_plans.json`

---

## 🆘 Support

Pour toute question ou problème:
1. Consulter les logs backend/frontend
2. Vérifier la documentation HYP
3. Contacter le support technique HYP
4. Vérifier les variables d'environnement

---

**Dernière mise à jour**: Janvier 2026
