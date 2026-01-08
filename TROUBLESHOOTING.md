# TROUBLESHOOTING - Flash Neiga

Ce document contient les solutions aux problèmes courants rencontrés avec l'application Flash Neiga.

## Table des matières

- [Erreurs de base de données](#erreurs-de-base-de-données)
- [Problèmes d'authentification](#problèmes-dauthentification)
- [Problèmes de démarrage](#problèmes-de-démarrage)
- [Outils de diagnostic](#outils-de-diagnostic)

---

## Erreurs de base de données

### Erreur 500 sur `/api/admin/signs`

**Symptômes:**
```
Failed to load resource: the server responded with a status of 500
Error fetching signs: ...
column traffic_signs.created_at does not exist
```

**Cause:**
Des colonnes requises sont manquantes dans la table `traffic_signs` (par exemple: `explanation`, `created_at`). Ces colonnes ont été ajoutées au modèle mais la base de données existante n'a pas été migrée.

**Solutions:**

#### Solution 1: Redémarrage de l'application (Recommandé)
L'application vérifie et corrige automatiquement le schéma au démarrage:

```bash
# En développement local:
cd backend
uvicorn server:app --reload

# En production (Render):
# Le redémarrage se fait automatiquement lors du déploiement
# Ou manuellement via le dashboard Render
```

L'application effectue maintenant ces étapes au démarrage:
1. ✅ Initialisation des tables de la base de données
2. ✅ Vérification et mise à jour du schéma
3. ✅ Création de l'utilisateur admin
4. ✅ Chargement des questions si la base est vide
5. ✅ Chargement des panneaux de signalisation si la base est vide

#### Solution 2: Script de réparation de production (Recommandé pour production)
Utilisez le script dédié pour réparer la base de données PostgreSQL en production:

```bash
# Vérifier le schéma sans faire de changements (sûr)
python backend/scripts/fix_production_db.py --dry-run

# Réparer la base de données (ajoute les colonnes manquantes)
python backend/scripts/fix_production_db.py

# Avec une URL de base de données personnalisée
python backend/scripts/fix_production_db.py --db-url "postgresql://user:pass@host/db"
```

Ce script:
- ✅ Vérifie les colonnes actuelles de `traffic_signs`
- ✅ Ajoute toutes les colonnes manquantes avec les bons types
- ✅ Crée les index nécessaires
- ✅ Vérifie la structure finale
- ✅ Fournit un journal détaillé de toutes les opérations

#### Solution 3: Vérification du schéma (lecture seule)
Vérifiez l'état du schéma sans modifier quoi que ce soit:

```bash
# Vérifier toutes les tables
python backend/scripts/verify_db_schema.py

# Vérifier une table spécifique
python backend/scripts/verify_db_schema.py --table traffic_signs

# Mode verbeux avec détails de toutes les colonnes
python backend/scripts/verify_db_schema.py --verbose
```

#### Solution 4: Vérification et réparation complète
Utilisez le script de vérification de l'intégrité:

```bash
# Vérifier l'intégrité de la base de données
python backend/scripts/check_and_fix_db.py

# Prévisualiser les corrections sans les appliquer
python backend/scripts/check_and_fix_db.py --dry-run

# Corriger automatiquement les problèmes détectés
python backend/scripts/check_and_fix_db.py --fix
```

#### Solution 5: Option nucléaire - Recréer la table (DESTRUCTIF)
⚠️  **ATTENTION:** Cette option supprime et recrée la table. À utiliser en dernier recours uniquement!

```bash
# Prévisualiser ce qui sera fait (sûr)
python backend/scripts/recreate_traffic_signs_table.py --dry-run

# Recréer la table (nécessite confirmation)
python backend/scripts/recreate_traffic_signs_table.py --confirm
```

Ce script:
- 💾 Sauvegarde les données existantes
- 🗑️  Supprime la table `traffic_signs`
- 🔧 Recrée la table avec le schéma correct
- ♻️  Restaure les données sauvegardées
- 📥 Charge depuis JSON si la table était vide

#### Solution 6: SQL manuel (Dernier recours)

**Pour SQLite (développement local):**
```bash
sqlite3 backend/flash_neiga.db
```
```sql
-- Vérifier si la colonne existe
PRAGMA table_info(traffic_signs);

-- Ajouter les colonnes manquantes
ALTER TABLE traffic_signs ADD COLUMN explanation TEXT;
ALTER TABLE traffic_signs ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;

-- Vérifier
PRAGMA table_info(traffic_signs);
.quit
```

**Pour PostgreSQL (production):**
```sql
-- Se connecter à la base de données
-- Via Render dashboard ou psql

-- Vérifier les colonnes
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'traffic_signs'
ORDER BY ordinal_position;

-- Ajouter les colonnes manquantes
ALTER TABLE traffic_signs ADD COLUMN explanation TEXT;
ALTER TABLE traffic_signs ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Vérifier
\d traffic_signs
```

### Connexion à la base de données de production

**URLs de connexion Render:**

- **URL interne** (pour les services Render):
  ```
  postgresql://flash_neiga_user:XbM2WHVQLhAShKB8axTj2DPkbquOxDX6@dpg-d4v0ld6uk2gs7394fbm0-a/flash_neiga
  ```

- **URL externe** (pour connexion locale):
  ```
  postgresql://flash_neiga_user:XbM2WHVQLhAShKB8axTj2DPkbquOxDX6@dpg-d4v0ld6uk2gs7394fbm0-a.oregon-postgres.render.com/flash_neiga
  ```

**Connexion via psql:**
```bash
psql "postgresql://flash_neiga_user:XbM2WHVQLhAShKB8axTj2DPkbquOxDX6@dpg-d4v0ld6uk2gs7394fbm0-a.oregon-postgres.render.com/flash_neiga"
```

**Via le dashboard Render:**
1. Allez sur https://dashboard.render.com
2. Sélectionnez votre service de base de données
3. Cliquez sur "Shell" pour accéder à un terminal psql

### Autres colonnes manquantes

Si d'autres colonnes sont manquantes, les scripts peuvent les détecter et les corriger:

```bash
# Vérifier toutes les tables
python backend/scripts/verify_db_schema.py

# Corriger automatiquement
python backend/scripts/check_and_fix_db.py --fix
```

**Schéma attendu des tables principales:**

**traffic_signs:**
- id (VARCHAR PRIMARY KEY)
- number (VARCHAR NOT NULL)
- name (VARCHAR NOT NULL)
- description (TEXT NOT NULL)
- image_url (VARCHAR)
- category (VARCHAR NOT NULL)
- explanation (TEXT)
- created_at (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)

**questions:**
- id (VARCHAR PRIMARY KEY)
- text (TEXT NOT NULL)
- category (VARCHAR NOT NULL)
- options (JSON NOT NULL)
- explanation (TEXT)
- created_at (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)

---

## Problèmes d'authentification

### Token JWT invalide

**Symptômes:**
```
401 Unauthorized
Could not validate credentials
```

**Solutions:**

1. **Vérifier la clé secrète:**
   ```bash
   # Vérifier que SECRET_KEY est défini
   echo $SECRET_KEY  # Linux/Mac
   echo %SECRET_KEY%  # Windows
   ```

2. **Se reconnecter:**
   - Déconnectez-vous de l'application
   - Reconnectez-vous avec vos identifiants

3. **Vérifier l'expiration du token:**
   Les tokens expirent après 24 heures. Reconnectez-vous si nécessaire.

### Impossible de se connecter en tant qu'admin

**Identifiants par défaut:**
- Email: `admin@gmail.com`
- Mot de passe: `admin.`

**Si les identifiants ne fonctionnent pas:**

```bash
# Réinitialiser le mot de passe admin via Python
cd backend
python
```
```python
from database import SessionLocal
from models import UserDB
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
db = SessionLocal()

admin = db.query(UserDB).filter(UserDB.email == "admin@gmail.com").first()
if admin:
    admin.hashed_password = pwd_context.hash("admin.")
    db.commit()
    print("✅ Mot de passe réinitialisé")
else:
    print("❌ Admin non trouvé")

db.close()
```

---

## Problèmes de démarrage

### L'application ne démarre pas

**Vérifications:**

1. **Dépendances installées:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Base de données accessible:**
   ```bash
   # SQLite - vérifier que le fichier est accessible
   ls -l backend/flash_neiga.db
   
   # PostgreSQL - vérifier DATABASE_URL
   echo $DATABASE_URL
   ```

3. **Variables d'environnement:**
   ```bash
   # Créer .env si nécessaire
   cp backend/.env.example backend/.env
   # Éditer et renseigner les valeurs
   ```

### Erreurs au démarrage

**Regarder les logs de démarrage:**

```bash
cd backend
uvicorn server:app --log-level debug
```

Recherchez:
- ✅ Database tables created
- ✅ Database schema verified
- ✅ Application startup complete

Si vous voyez:
- ❌ Error checking/updating schema
- ❌ Error during startup

Consultez les messages d'erreur détaillés et référez-vous aux sections appropriées de ce guide.

---

## Outils de diagnostic

### Scripts de gestion de la base de données

L'application dispose de plusieurs scripts pour gérer et dépanner la base de données:

#### 1. `verify_db_schema.py` - Vérification du schéma (lecture seule)

**Objectif:** Vérifier que le schéma de la base de données correspond aux modèles attendus, sans faire de modifications.

**Usage:**
```bash
# Vérifier toutes les tables
python backend/scripts/verify_db_schema.py

# Vérifier une table spécifique
python backend/scripts/verify_db_schema.py --table traffic_signs

# Mode verbeux avec tous les détails
python backend/scripts/verify_db_schema.py --verbose

# Avec une URL de base personnalisée
python backend/scripts/verify_db_schema.py --db-url "postgresql://..."
```

**Sortie attendue:**
```
🔍 DATABASE SCHEMA VERIFICATION
✅ Connected to PostgreSQL
📋 Table: traffic_signs
  ✅ Table exists
  📊 Row count: 117
  ✅ All expected columns present
✅ All tables verified successfully - schema is correct!
```

#### 2. `fix_production_db.py` - Réparation de la base de production

**Objectif:** Ajouter les colonnes manquantes et créer les index dans la base de données PostgreSQL de production.

**Usage:**
```bash
# Mode dry-run (prévisualisation sans changements)
python backend/scripts/fix_production_db.py --dry-run

# Réparer la base de données
python backend/scripts/fix_production_db.py

# Avec DATABASE_URL personnalisée
export DATABASE_URL="postgresql://user:pass@host/db"
python backend/scripts/fix_production_db.py

# Ignorer la création d'index
python backend/scripts/fix_production_db.py --skip-indexes
```

**Ce que fait le script:**
- ✅ Se connecte à PostgreSQL
- ✅ Vérifie les colonnes actuelles
- ✅ Identifie les colonnes manquantes
- ✅ Ajoute les colonnes manquantes avec les bons types
- ✅ Crée les index recommandés
- ✅ Vérifie le schéma final

#### 3. `check_and_fix_db.py` - Vérification et réparation

**Objectif:** Vérifier l'intégrité de toutes les tables et optionnellement corriger les problèmes.

**Usage:**
```bash
# Vérifier uniquement (sans corrections)
python backend/scripts/check_and_fix_db.py

# Prévisualiser les corrections
python backend/scripts/check_and_fix_db.py --dry-run

# Corriger automatiquement
python backend/scripts/check_and_fix_db.py --fix
```

**Tables vérifiées:**
- users, questions, traffic_signs
- exam_sessions, transactions, payments, subscriptions

#### 4. `recreate_traffic_signs_table.py` - Recréation de la table (DESTRUCTIF)

**Objectif:** Option nucléaire pour recréer complètement la table `traffic_signs` avec le bon schéma.

⚠️  **ATTENTION:** Cette option supprime et recrée la table. À utiliser uniquement si les autres méthodes ont échoué!

**Usage:**
```bash
# Prévisualiser ce qui sera fait (sûr)
python backend/scripts/recreate_traffic_signs_table.py --dry-run

# Recréer la table (nécessite --confirm)
python backend/scripts/recreate_traffic_signs_table.py --confirm
```

**Ce que fait le script:**
1. 💾 Sauvegarde les données existantes dans `backend/backups/`
2. 🗑️  Supprime la table `traffic_signs`
3. 🔧 Recrée la table avec le schéma correct
4. ♻️  Restaure les données sauvegardées
5. 📥 Charge depuis `data/signs_israel_fr_117.json` si la table était vide

### 1. Vérification de l'intégrité de la base de données

```bash
python backend/scripts/check_and_fix_db.py
```

**Sortie attendue:**
```
🔍 Checking database integrity...
📋 Checking table: traffic_signs
   ✅ All expected columns present
📋 Checking table: questions
   ✅ All expected columns present
...
✅ Database integrity check passed - no issues found!
```

### 2. Logs de l'application

Les logs incluent maintenant des informations détaillées:

```python
# Dans les logs, recherchez:
logger.info("📋 Admin signs request - missingOnly=True, limit=50, offset=0")
logger.info("✅ Successfully retrieved 25 traffic signs")
```

**Activer les logs détaillés:**
```bash
# Modifier logging level dans server.py
logging.basicConfig(level=logging.DEBUG)
```

### 3. Tester l'endpoint admin signs

```bash
# Obtenir un token JWT
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@gmail.com","password":"admin."}'

# Utiliser le token pour appeler l'endpoint
TOKEN="votre_token_ici"
curl -X GET "http://localhost:8000/api/admin/signs?missingOnly=false&limit=10&offset=0" \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Vérifier les colonnes de la base de données

**SQLite:**
```bash
sqlite3 backend/flash_neiga.db ".schema traffic_signs"
```

**PostgreSQL (Render):**
Via le dashboard Render:
1. Aller sur votre service database
2. Cliquer sur "Shell"
3. Exécuter:
   ```sql
   \d traffic_signs
   ```

---

## Obtenir de l'aide

Si aucune de ces solutions ne fonctionne:

1. **Vérifier les logs:**
   - Logs du serveur backend
   - Logs de la console du navigateur
   - Logs de Render (en production)

2. **Créer un rapport de bug avec:**
   - Description du problème
   - Messages d'erreur complets
   - Étapes pour reproduire
   - Sortie de `python backend/scripts/check_and_fix_db.py`
   - Version de Python et dépendances

3. **Informations système utiles:**
   ```bash
   python --version
   pip freeze > installed_packages.txt
   ```

---

## Maintenance préventive

### Vérifications régulières

1. **Vérifier l'intégrité de la base de données:**
   ```bash
   python backend/scripts/check_and_fix_db.py
   ```

2. **Sauvegarder la base de données:**
   ```bash
   # SQLite
   cp backend/flash_neiga.db backend/flash_neiga.db.backup
   
   # PostgreSQL (via Render)
   # Utiliser les backups automatiques de Render
   ```

3. **Mettre à jour les dépendances:**
   ```bash
   cd backend
   pip install -U -r requirements.txt
   ```

### Avant une migration

1. Sauvegarder la base de données
2. Tester la migration en local
3. Vérifier les logs de migration
4. Tester l'application après migration

---

*Dernière mise à jour: Janvier 2026*
