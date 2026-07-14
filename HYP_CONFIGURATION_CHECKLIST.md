# HYP — Checklist de configuration (production)

Guide pas-à-pas pour brancher HYP (Yaad Sarig) **parfaitement**, avec les vraies
valeurs de Flash Neiga. Suivre dans l'ordre. Chaque étape a une vérification.

- **Frontend (canonique)** : `https://app.flash-neiga.com`
- **Backend** : `https://flash-neiga-backend.onrender.com`
- **Terminal HYP (Masof)** : `4502176330`
- **API HYP** : `https://icom.yaad.net/p/`

---

## 1. Identifiants HYP

HYP utilise **trois** identifiants pour le flux « APISign » :

| Rôle | Variable | Où le trouver |
|------|----------|---------------|
| Terminal (Masof) | `HYP_TERMINAL_ID` = `4502176330` | Déjà connu |
| Clé de signature (KEY) | `HYP_API_KEY` | Dashboard HYP → API / מפתח API |
| Mot de passe API (PassP) | `HYP_PASSP` | Dashboard HYP → paramètres API. **Peut être facultatif** selon le terminal |

> ℹ️ Le code n'envoie `PassP` que s'il est renseigné. Si ton terminal signe avec
> `KEY` seul, laisse `HYP_PASSP` vide. L'étape 5 (`/test-connection`) te dira
> immédiatement si le PassP est nécessaire.

---

## 2. Variables d'environnement — Render (backend)

Dashboard Render → service `flash-neiga-backend` → **Environment**. La plupart
sont déjà déclarées dans `render.yaml` ; renseigne manuellement les secrets
(`sync: false`).

```bash
HYP_TERMINAL_ID=4502176330
HYP_USER_ID=pveda
HYP_API_KEY=<ta clé API HYP>            # secret — à saisir dans Render
HYP_PASSP=<mot de passe API HYP>        # secret — laisser vide si non requis
HYP_API_URL=https://icom.yaad.net/p/
HYP_PAGE_LANG=ENG                       # HEB ou ENG
HYP_REQUIRE_SIGNATURE=false             # passer à true à l'étape 8

HYP_SUCCESS_URL=https://app.flash-neiga.com/payment/success
HYP_ERROR_URL=https://app.flash-neiga.com/payment/failure
HYP_CALLBACK_URL=https://flash-neiga-backend.onrender.com/api/payments/hyp/callback

ALLOWED_ORIGINS=https://app.flash-neiga.com,https://appflashneiga.netlify.app
```

**Vérification** : après redéploiement,
`curl https://flash-neiga-backend.onrender.com/api/payments/hyp/verify-config`
doit renvoyer `"hyp_configured": true` et `"plans_loaded": 7`.

---

## 3. Frontend — Netlify

Le frontend appelle l'API en relatif (`/api/...`) ; `netlify.toml` proxifie
`/api/*` vers le backend Render (pas de CORS, pas de variable à définir).

- Netlify → **Domain settings** : vérifier que `app.flash-neiga.com` est bien un
  domaine du site (custom domain) et que le HTTPS est actif.
- Aucun `REACT_APP_BACKEND_URL` n'est nécessaire (appels relatifs).

**Vérification** : `https://app.flash-neiga.com/api/payments/hyp/plans` doit
renvoyer les 7 plans (preuve que le proxy Netlify → Render fonctionne).

---

## 4. Dashboard HYP — URLs de retour et notification

Dans le back-office HYP du terminal `4502176330` :

1. **URL de notification serveur-à-serveur** (IPN / נוטיפיקציה) :
   `https://flash-neiga-backend.onrender.com/api/payments/hyp/callback`
   → c'est ici que l'abonnement est provisionné et vérifié (APISign VERIFY).
2. **URL de retour succès** (חזרה):
   `https://app.flash-neiga.com/payment/success`
3. **URL de retour échec** :
   `https://app.flash-neiga.com/payment/failure`
4. Vérifier que le terminal est **actif** et autorisé pour l'API.

> Le paramètre `Order` (= notre `transaction_id`) est renvoyé automatiquement par
> HYP sur ces URLs ; le frontend et le callback s'en servent pour réconcilier la
> transaction. Même si l'IPN n'est pas configuré, la page succès transmet le
> résultat au callback — mais configurer l'IPN reste recommandé (fiabilité).

---

## 5. Test des identifiants (le contrôle décisif)

Un endpoint de diagnostic effectue un **vrai** appel APISign SIGN :

```bash
curl https://flash-neiga-backend.onrender.com/api/payments/hyp/test-connection
```

- ✅ `"ok": true, "message": "APISign signature generated successfully…"`
  → identifiants parfaits, tu peux passer au test de paiement.
- ❌ `"ok": false` avec un `hyp_ccode` / `hyp_response`
  → identifiants incomplets. Le plus souvent : il manque `HYP_PASSP`, ou la
  `KEY`/le Masof ne correspondent pas. Corrige puis relance.

---

## 6. Test d'un paiement de bout en bout

1. Aller sur `https://app.flash-neiga.com/pricing`.
2. Cliquer sur un plan → redirection vers la page HYP.
3. Payer avec une **carte de test HYP** :
   - Numéro : `4580458045804580`
   - CVV : `123`
   - Expiration : une date future
4. Vérifier :
   - Retour sur `/payment/success` avec les détails.
   - Transaction passée à `completed`
     (`GET /api/payments/hyp/transaction/<id>`).
   - Abonnement créé (`GET /api/payments/hyp/subscriptions/<user_id>`) avec les
     bonnes dates `start_date` / `end_date`.

---

## 7. Rattachement au compte utilisateur

Pour que l'abonnement soit lié au compte, l'utilisateur doit être **connecté**
au moment du paiement (le frontend transmet alors `user_id`). Sinon la
transaction est créée sans utilisateur et devra être rattachée manuellement.
→ Recommandation : exiger la connexion avant l'accès à `/pricing`, ou faire
créer le compte avant le paiement.

---

## 8. Passage en production sécurisée

Une fois qu'un paiement de test aboutit et que le terminal **signe** ses
notifications (présence d'un paramètre `Sign` dans le callback) :

```bash
HYP_REQUIRE_SIGNATURE=true
```

→ Tout callback sans signature valide (vérifiée via APISign VERIFY) sera rejeté.
C'est la configuration cible en production.

---

## Récapitulatif des endpoints de diagnostic

| Endpoint | Usage |
|----------|-------|
| `GET /api/payments/hyp/verify-config` | Config présente (clé, plans) |
| `GET /api/payments/hyp/test-connection` | **Test réel** des identifiants (APISign SIGN) |
| `GET /api/payments/hyp/plans` | Liste des 7 plans |
| `POST /api/payments/hyp/create-payment` | Crée un lien de paiement |
| `GET /api/payments/hyp/transaction/{id}` | État d'une transaction + abonnement |
| `GET /api/payments/hyp/subscriptions/{user_id}` | Abonnements d'un utilisateur |
