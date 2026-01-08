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
```

**Cause:**
La colonne `explanation` est manquante dans la table `traffic_signs`. Cette colonne a été ajoutée récemment au modèle mais la base de données existante n'a pas été migrée.

**Solutions:**

#### Solution 1: Redémarrage de l'application (Recommandé)
L'application vérifie et corrige automatiquement le schéma au démarrage depuis la dernière mise à jour:

```bash
# Arrêter et redémarrer l'application
# En développement:
cd backend
uvicorn server:app --reload

# En production (Render):
# Le redémarrage se fait automatiquement lors du déploiement
```

#### Solution 2: Script de migration manuel
Si le redémarrage ne résout pas le problème:

```bash
# Depuis la racine du projet
python backend/migrations/add_explanation_column.py
```

Ce script:
- Vérifie si la colonne `explanation` existe
- L'ajoute si elle est manquante
- Supporte SQLite et PostgreSQL
- Affiche des logs détaillés

#### Solution 3: Vérification et réparation complète
Utilisez le script de vérification de l'intégrité:

```bash
# Vérifier l'intégrité de la base de données
python backend/scripts/check_and_fix_db.py

# Corriger automatiquement les problèmes détectés
python backend/scripts/check_and_fix_db.py --fix
```

#### Solution 4: SQL manuel (Dernier recours)

**Pour SQLite (développement local):**
```bash
sqlite3 backend/flash_neiga.db
```
```sql
-- Vérifier si la colonne existe
PRAGMA table_info(traffic_signs);

-- Ajouter la colonne si manquante
ALTER TABLE traffic_signs ADD COLUMN explanation TEXT;

-- Vérifier
PRAGMA table_info(traffic_signs);
.quit
```

**Pour PostgreSQL (production):**
```sql
-- Se connecter à la base de données
-- Via Render dashboard ou psql

-- Vérifier les colonnes
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'traffic_signs';

-- Ajouter la colonne si manquante
ALTER TABLE traffic_signs ADD COLUMN explanation TEXT;

-- Vérifier
\d traffic_signs
```

### Autres colonnes manquantes

Si d'autres colonnes sont manquantes, le script `check_and_fix_db.py` peut les détecter et les corriger:

```bash
python backend/scripts/check_and_fix_db.py --fix
```

Tables vérifiées:
- `traffic_signs`: id, number, name, description, image_url, category, explanation, created_at
- `questions`: id, text, category, options, explanation, created_at
- `users`: id, email, hashed_password, created_at, is_premium, premium_until
- `exam_sessions`: id, user_id, started_at, ended_at, score, total_questions, passed, answers
- `transactions`: id, user_id, transaction_id, amount, currency, provider, status, created_at, metadata

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
