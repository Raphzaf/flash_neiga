# 🖼️ Enrichissement des questions avec les images

## 📋 Vue d'ensemble

Ce guide explique comment enrichir les questions en base de données avec les URLs d'images extraites de `sample_questions.json`.

## 🚀 Utilisation locale

### Prérequis
- Python 3.8+
- Base de données SQLite existante (`backend/flash_neiga.db`)
- Fichiers JSON présents dans `data/`

### Exécution

```bash
cd backend
python scripts/add_images_to_questions.py
```

### Résultat attendu

```
🎨 Enrichissement des questions avec les images
============================================================

📖 Chargement des fichiers...
✅ data_v3.json chargé (1802 questions)
✅ sample_questions.json chargé (1802 items)

💾 Connexion à la base de données : backend/flash_neiga.db

🔧 Vérification du schéma de la table...
✅ Colonne 'image_url' ajoutée à la table 'questions'

🖼️  Extraction et mise à jour des images...
   Progression : 200/1802 questions traitées...
   Progression : 400/1802 questions traitées...
   [...]

============================================================
✅ Enrichissement terminé !
============================================================

📊 Statistiques :
   • Questions traitées        : 1802
   • Questions avec images     : 486
   • Questions sans images     : 1316
   • Questions mises à jour DB : 486

💡 Pourcentage avec images : 27.0%
```

## 🔄 Idempotence

Le script peut être relancé plusieurs fois sans risque :
- Ne duplique pas les données
- Met à jour uniquement si nécessaire
- Affiche toujours les mêmes statistiques

## 🐛 Dépannage

### Erreur : `database is locked`
```bash
# Arrêter le serveur FastAPI puis réessayer
pkill -f uvicorn
python scripts/add_images_to_questions.py
```

### Erreur : `FileNotFoundError`
```bash
# Vérifier que les fichiers JSON existent
ls -la data/data_v3.json
ls -la data/sample_questions.json
```

## 📊 Vérification

Pour vérifier que les images ont été ajoutées :

```python
import sqlite3

conn = sqlite3.connect('backend/flash_neiga.db')
cursor = conn.cursor()

# Compter les questions avec images
cursor.execute('SELECT COUNT(*) FROM questions WHERE image_url IS NOT NULL')
with_images = cursor.fetchone()[0]

# Exemple de question avec image
cursor.execute('SELECT text, image_url FROM questions WHERE image_url IS NOT NULL LIMIT 1')
example = cursor.fetchone()

print(f"Questions avec images : {with_images}")
print(f"\nExemple :")
print(f"  Question : {example[0][:80]}...")
print(f"  Image URL : {example[1]}")

conn.close()
```
