# Migration de la base de données pour HYP

## 🎯 Objectif

Ajouter les colonnes nécessaires à PostgreSQL pour supporter l'intégration HYP.

## 📋 Prérequis

- Accès au dashboard Render
- Backend déployé sur Render
- Base de données PostgreSQL configurée

## 🚀 Exécution sur Render

### Option 1: Via le Shell Render (Recommandé)

1. **Aller sur Render Dashboard**: https://dashboard.render.com
2. **Sélectionner votre service backend** `flash-neiga-backend`
3. **Cliquer sur "Shell"** (onglet en haut)
4. **Exécuter la migration**:
   ```bash
   cd /opt/render/project/src
   python backend/scripts/run_hyp_migration.py
   ```

5. **Vérifier la sortie**:
   ```
   ✅ Migration completed successfully!
   📊 Verifying database schema...
      Table 'transactions' columns:
        - id: character varying
        - user_id: character varying
        - plan_id: character varying     ← NOUVELLE
        - hyp_transaction_id: character varying  ← NOUVELLE
        ...
   ```

6. **Redémarrer le service**:
   - Cliquer sur "Manual Deploy" → "Clear build cache & deploy"

### Option 2: Via connexion PostgreSQL directe

1. **Obtenir l'URL de connexion**:
   - Dashboard Render → Votre base de données → "Connections"
   - Copier "External Database URL"

2. **Installer psql localement** (si pas déjà installé):
   ```bash
   # macOS
   brew install postgresql
   
   # Ubuntu/Debian
   sudo apt-get install postgresql-client
   ```

3. **Se connecter**:
   ```bash
   psql "postgresql://YOUR_USER:YOUR_PASSWORD@YOUR_HOST/YOUR_DATABASE"
   ```
   
   > **Note**: Remplacez les valeurs par celles obtenues depuis le dashboard Render

4. **Exécuter le SQL manuellement**:
   ```sql
   -- Copier-coller le contenu de backend/migrations/002_add_hyp_support.sql
   ```

## 🧪 Vérification

Après la migration, testez l'endpoint:

```bash
curl https://flash-neiga-backend.onrender.com/api/payments/hyp/create-payment \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"plan_id": "code_14d"}'
```

**Attendu**: Pas d'erreur 500, création de la transaction réussie.

## ⚠️ En cas d'erreur

### Erreur: "relation does not exist"

```sql
-- Vérifier que les tables existent
\dt

-- Si 'transactions' manque, créer avec
CREATE TABLE transactions (
  id VARCHAR PRIMARY KEY,
  ...
);
```

### Erreur: "column already exists"

C'est normal! Le script utilise `ADD COLUMN IF NOT EXISTS`, donc c'est sécurisé.

## 🔄 Rollback (si nécessaire)

Si vous devez annuler la migration:

```sql
-- Supprimer les colonnes HYP
ALTER TABLE transactions DROP COLUMN IF EXISTS plan_id;
ALTER TABLE transactions DROP COLUMN IF EXISTS hyp_transaction_id;
ALTER TABLE transactions DROP COLUMN IF EXISTS hyp_internal_deal_id;
ALTER TABLE transactions DROP COLUMN IF EXISTS payment_url;
ALTER TABLE transactions DROP COLUMN IF EXISTS callback_data;

-- Supprimer la table subscriptions
DROP TABLE IF EXISTS subscriptions CASCADE;
```

## 📝 Notes

- La migration est **idempotente** : elle peut être exécutée plusieurs fois sans danger
- Les colonnes Paddle existantes sont **conservées** pour compatibilité
- La table `subscriptions` remplace la gestion manuelle des abonnements
