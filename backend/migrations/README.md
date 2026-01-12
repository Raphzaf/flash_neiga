# Migrations Base de Données

## 📋 Liste des Migrations

### 001_add_hyp_columns.sql
**Date**: 2026-01-12  
**Description**: Ajoute les colonnes nécessaires pour l'intégration HYP à la table `transactions` et crée la table `subscriptions`.

**Colonnes ajoutées à `transactions`**:
- `plan_id` - Identifiant du plan (code_14d, video_1m, etc.)
- `hyp_transaction_id` - ID de transaction HYP
- `hyp_internal_deal_id` - ID interne HYP
- `payment_url` - URL de la page de paiement HYP
- `callback_data` - Données du callback HYP (JSON)
- `event_data` - Données d'événement supplémentaires (JSON)

**Table créée**:
- `subscriptions` - Gestion des abonnements utilisateurs

## 🚀 Exécution sur Render

### Méthode 1: Via le Shell Render (Recommandé)

1. **Ouvrir le Shell Render**:
   - Allez sur https://dashboard.render.com
   - Sélectionnez votre service backend
   - Cliquez sur "Shell" dans le menu de gauche

2. **Installer psycopg2** (si nécessaire):
   ```bash
   pip install psycopg2-binary
   ```

3. **Exécuter la migration**:
   ```bash
   python backend/migrations/run_migration.py
   ```

4. **Confirmer** quand demandé (tapez `yes`)

5. **Vérifier** les logs pour confirmer le succès

6. **Redémarrer** le service depuis le dashboard Render

### Méthode 2: Via SQL Direct (Avancé)

Si vous avez accès à un client PostgreSQL:

1. **Récupérer l'URL de connexion externe** depuis Render Dashboard

2. **Connecter** avec psql:
   ```bash
   psql "postgresql://user:password@host/database"
   ```

3. **Exécuter** le contenu de `001_add_hyp_columns.sql`

## 🧪 Vérification Post-Migration

Après la migration, vérifiez que tout fonctionne:

```bash
# Test 1: Vérifier la configuration HYP
curl https://flash-neiga-backend.onrender.com/api/payments/hyp/verify-config

# Test 2: Vérifier les plans
curl https://flash-neiga-backend.onrender.com/api/payments/hyp/plans

# Test 3: Essayer de créer un paiement depuis le frontend
```

## 🔄 Rollback (Si Nécessaire)

Si vous devez annuler la migration:

```sql
-- ATTENTION: Cela supprime les données!
ALTER TABLE transactions DROP COLUMN IF EXISTS plan_id;
ALTER TABLE transactions DROP COLUMN IF EXISTS hyp_transaction_id;
ALTER TABLE transactions DROP COLUMN IF EXISTS hyp_internal_deal_id;
ALTER TABLE transactions DROP COLUMN IF EXISTS payment_url;
ALTER TABLE transactions DROP COLUMN IF EXISTS callback_data;
ALTER TABLE transactions DROP COLUMN IF EXISTS event_data;

DROP TABLE IF EXISTS subscriptions;
```

## 📝 Notes Importantes

- ✅ La migration utilise `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` - elle est **idempotente** (peut être exécutée plusieurs fois sans problème)
- ✅ Les colonnes Paddle existantes sont **conservées** pour la compatibilité
- ✅ Les données existantes ne sont **pas modifiées**
- ⚠️ Faites toujours une **sauvegarde** avant de modifier la base de données

## ❓ Dépannage

### Erreur: "DATABASE_URL not set"
→ La variable d'environnement n'est pas définie. Sur Render, elle est automatiquement configurée.

### Erreur: "psycopg2 not found"
→ Installez avec: `pip install psycopg2-binary`

### Erreur: "Permission denied"
→ Vérifiez que vous avez les droits d'administration sur la base de données

### La migration ne change rien
→ C'est normal si les colonnes existent déjà (migration idempotente)
