# 🚀 Déploiement et migration sur Render

## 🎯 Enrichir les questions avec les images sur Render

### ⚡ Méthode 1 : Render Shell (RECOMMANDÉE)

La méthode la plus simple et sécurisée.

#### 1️⃣ Accéder au Shell

1. Aller sur https://dashboard.render.com
2. Sélectionner ton service `flash-neiga-backend`
3. Cliquer sur l'onglet **"Shell"**
4. Attendre que le shell se connecte

#### 2️⃣ Exécuter le script

Dans le shell Render, taper :

```bash
# Vérifier qu'on est dans le bon dossier
pwd
# Devrait afficher : /opt/render/project/src

# Aller dans le dossier backend
cd backend

# Exécuter le script
python scripts/add_images_to_questions.py
```

#### 3️⃣ Vérifier le résultat

Le script affiche les statistiques en temps réel. Tu devrais voir :

```
✅ Enrichissement terminé !
📊 Statistiques :
   • Questions avec images     : 486
   • Questions mises à jour DB : 486
```

#### ✅ Avantages
- Simple et direct
- Pas besoin de redéployer
- Aucun risque pour la production
- Logs en temps réel

---

### 🔧 Méthode 2 : Migration automatique au démarrage

Pour enrichir automatiquement à chaque déploiement.

#### 1️⃣ Modifier `backend/server.py`

Ajouter après la ligne d'initialisation de la base de données :

```python
# Enrichir les questions avec les images (une seule fois)
try:
    from scripts.add_images_to_questions import add_images_to_database
    logger.info("📝 Step 6: Enriching questions with images...")
    add_images_to_database()
    logger.info("✅ Questions enriched with images")
except Exception as e:
    logger.warning(f"⚠️ Failed to enrich images: {e}")
```

#### 2️⃣ Commit et push

```bash
git add backend/server.py
git commit -m "feat: auto-enrich questions with images on startup"
git push
```

#### 3️⃣ Render redéploie automatiquement

Render détecte le push et redéploie. Les images seront ajoutées automatiquement.

#### ⚠️ Inconvénients
- S'exécute à chaque démarrage (ralentit un peu le boot)
- Idempotent donc pas de risque, mais moins optimal

---

### 🌐 Méthode 3 : Endpoint API temporaire

Pour enrichir via une requête HTTP (déconseillé en production).

#### 1️⃣ Créer l'endpoint dans `backend/server.py`

```python
@app.post("/api/admin/enrich-images-once")
async def enrich_images_once(current_user: dict = Depends(get_current_user)):
    """Endpoint temporaire pour enrichir les images (à supprimer après usage)"""
    if not current_user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Admin only")
    
    try:
        from scripts.add_images_to_questions import add_images_to_database
        add_images_to_database()
        return {"status": "success", "message": "Images enriched"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 2️⃣ Appeler l'endpoint

```bash
# Depuis ton terminal local
curl -X POST https://flash-neiga-backend.onrender.com/api/admin/enrich-images-once \
  -H "Authorization: Bearer TON_TOKEN_ADMIN"
```

#### 3️⃣ Supprimer l'endpoint après usage

⚠️ **Important** : Supprimer cet endpoint après l'avoir utilisé (sécurité).

---

## 🎯 Recommandation

**Pour la première fois : Méthode 1 (Render Shell)**
- Simple
- Sécurisé
- Contrôle total

**Pour le futur : Méthode 2 (Auto au démarrage)**
- Automatique
- Idempotent
- Pas de maintenance

---

## 📊 Vérifier que ça fonctionne

Après enrichissement, tester via l'API :

```bash
# Récupérer une question avec image
curl https://flash-neiga-backend.onrender.com/api/questions?limit=1

# Vérifier que le champ image_url existe et contient une URL
```

Ou dans le frontend, vérifier que les images s'affichent correctement.

---

## 🐛 Dépannage sur Render

### Shell ne se connecte pas
- Attendre 30-60 secondes
- Rafraîchir la page
- Vérifier que le service est "running"

### Script échoue avec "database is locked"
```bash
# Arrêter temporairement le service, exécuter, puis redémarrer
# OU attendre que Render libère la DB (quelques secondes)
```

### Fichiers JSON manquants
```bash
# Vérifier qu'ils sont bien dans le repo
ls -la data/
# S'ils sont présents localement mais pas sur Render, vérifier .gitignore
```
