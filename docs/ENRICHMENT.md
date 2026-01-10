# Documentation d'Enrichissement des Questions

## 📖 Vue d'ensemble

Ce document explique comment enrichir le fichier `data_v3.json` avec des informations supplémentaires provenant de `sample_questions.json`, notamment les URLs d'images.

## 🔗 Correspondance entre les fichiers

Les deux fichiers JSON contiennent **1802 questions** dans le **même ordre**. La correspondance se fait par **index de position** :

- **`data/data_v3.json`** : Contient les questions formatées avec leurs options et réponses
- **`data/sample_questions.json`** : Contient les données brutes originales avec le HTML des questions

### Structure de `data_v3.json`

```json
{
  "questions": [
    {
      "text": "0906. Comment conduirez-vous selon la situation décrite sur l'illustration?",
      "category": "Sécurité",
      "options": [
        {
          "id": "uuid-1",
          "text": "Option 1",
          "is_correct": false
        },
        {
          "id": "uuid-2",
          "text": "Option 2",
          "is_correct": true
        }
      ],
      "explanation": null
    }
  ]
}
```

### Structure de `sample_questions.json`

```json
{
  "total": 1802,
  "items": [
    {
      "index": "7/1802",
      "subject": null,
      "image": null,
      "raw": {
        "_id": 7,
        "title2": "0906. Comment conduirez-vous...",
        "description4": "<div>...<img src=\"https://example.com/image.jpg\" />...</div>",
        "category": "Sécurité"
      }
    }
  ]
}
```

## 🎯 Extraction des URLs d'images

Les URLs d'images sont extraites du champ `description4` qui contient du HTML. Le script utilise une expression régulière pour extraire l'attribut `src` des balises `<img>` :

```regex
/<img[^>]+src="([^">]+)"/
```

### Exemples d'extraction

**HTML avec image :**
```html
<div dir="ltr">
  <ul>
    <li><span>Option 1</span></li>
    <li><span>Option 2</span></li>
  </ul>
  <br>
  <img src="https://www.gov.il/BlobFolder/generalpage/tq_pic_01/he/TQ_PIC_3154.jpg" border="0" alt="integrated_street" />
</div>
```
**URL extraite :** `https://www.gov.il/BlobFolder/generalpage/tq_pic_01/he/TQ_PIC_3154.jpg`

**HTML sans image :**
```html
<div dir="ltr">
  <ul>
    <li><span>Option 1</span></li>
    <li><span>Option 2</span></li>
  </ul>
</div>
```
**URL extraite :** `null`

## 📊 Structure du fichier enrichi

Le fichier `data/data_enriched.json` contient toutes les questions de `data_v3.json` avec trois nouveaux champs :

```json
{
  "questions": [
    {
      "text": "0906. Comment conduirez-vous selon la situation décrite sur l'illustration?",
      "category": "Sécurité",
      "options": [
        {
          "id": "uuid-1",
          "text": "Option 1",
          "is_correct": false
        },
        {
          "id": "uuid-2",
          "text": "Option 2",
          "is_correct": true
        }
      ],
      "explanation": null,
      "imageUrl": "https://www.gov.il/BlobFolder/generalpage/tq_pic_01/he/TQ_PIC_906.jpg",
      "questionId": 7,
      "index": "7/1802"
    }
  ]
}
```

### Nouveaux champs ajoutés

| Champ | Type | Description | Exemple |
|-------|------|-------------|---------|
| `imageUrl` | `string \| null` | URL de l'image extraite du HTML | `"https://www.gov.il/BlobFolder/.../TQ_PIC_906.jpg"` |
| `questionId` | `number \| null` | Identifiant unique de la question (`_id` de sample_questions) | `7` |
| `index` | `string \| null` | Index formaté de la question | `"7/1802"` |

## 🚀 Utilisation

### Commande

Pour enrichir les données, exécutez la commande suivante à la racine du projet :

```bash
npm run enrich
```

### Processus d'enrichissement

1. **Chargement** : Le script charge les deux fichiers JSON
2. **Validation** : Vérification du nombre de questions (doit être 1802)
3. **Correspondance** : Association par index de position
4. **Extraction** : Extraction des URLs d'images du HTML
5. **Enrichissement** : Ajout des nouveaux champs
6. **Sauvegarde** : Génération de `data/data_enriched.json`
7. **Statistiques** : Affichage des résultats

### Exemple de sortie

```
🚀 Démarrage de l'enrichissement des questions...

📂 Chargement des fichiers...
✓ Chargé 1802 questions de data_v3.json
✓ Chargé 1802 questions de sample_questions.json

🔄 Enrichissement des questions en cours...
✓ Enrichissement terminé

💾 Sauvegarde du fichier enrichi...
✓ Fichier sauvegardé: /home/runner/work/flash_neiga/flash_neiga/data/data_enriched.json

📊 Statistiques:
──────────────────────────────────────────────────
Total de questions:        1802
Questions avec images:     850 (47%)
Questions sans images:     952 (53%)
──────────────────────────────────────────────────

✅ Enrichissement terminé avec succès!
```

## 📋 Exemples avant/après enrichissement

### Avant (data_v3.json)

```json
{
  "text": "0154. Quelle est la vitesse maximale autorisée dans une zone résidentielle",
  "category": "Code de la route",
  "options": [
    {
      "id": "7e18a5e6-bea5-4402-bf1f-ed446b224156",
      "text": "10 km/h",
      "is_correct": false
    },
    {
      "id": "a96cda0a-96f8-4982-bf7d-70ab6888e6b2",
      "text": "30 km/h",
      "is_correct": true
    }
  ],
  "explanation": null
}
```

### Après (data_enriched.json)

```json
{
  "text": "0154. Quelle est la vitesse maximale autorisée dans une zone résidentielle",
  "category": "Code de la route",
  "options": [
    {
      "id": "7e18a5e6-bea5-4402-bf1f-ed446b224156",
      "text": "10 km/h",
      "is_correct": false
    },
    {
      "id": "a96cda0a-96f8-4982-bf7d-70ab6888e6b2",
      "text": "30 km/h",
      "is_correct": true
    }
  ],
  "explanation": null,
  "imageUrl": "https://www.gov.il/BlobFolder/generalpage/tq_pic_01/he/TQ_PIC_3154.jpg",
  "questionId": 2,
  "index": "2/1802"
}
```

## 🔧 Fichiers générés

### `data/data_enriched.json`

- **Format** : JSON avec indentation (2 espaces)
- **Encodage** : UTF-8
- **Taille** : ~2-3 MB (selon les données)
- **Utilisation** : Fichier de sortie à utiliser dans l'application

⚠️ **Note** : Ce fichier est généré automatiquement et ne doit pas être commité dans le repository Git (il est ignoré dans `.gitignore`).

## 📝 Notes techniques

### Gestion des erreurs

Le script gère les cas suivants :

- **Fichiers manquants** : Erreur si `data_v3.json` ou `sample_questions.json` n'existe pas
- **Format invalide** : Erreur si la structure JSON est incorrecte
- **Nombre différent** : Avertissement si le nombre de questions ne correspond pas
- **Questions manquantes** : Les champs sont définis à `null` si pas de correspondance

### Performance

- Traitement de **1802 questions** : ~1-2 secondes
- Lecture/écriture optimisée en mémoire
- Pas de dépendances externes (utilise Node.js natif)

## 🛠️ Développement

### Modification du script

Le script se trouve dans `scripts/enrich-questions.js` et peut être modifié pour :

- Changer le regex d'extraction d'images
- Ajouter d'autres champs d'enrichissement
- Modifier le format de sortie
- Ajouter des validations supplémentaires

### Test du script

```bash
# Exécuter directement avec Node.js
node scripts/enrich-questions.js

# Ou via npm
npm run enrich
```

## ❓ FAQ

### Pourquoi utiliser l'index de position plutôt qu'un ID ?

Les deux fichiers ont été générés dans le même ordre et ne partagent pas d'identifiant commun évident. L'index de position est la méthode la plus fiable pour la correspondance.

### Que se passe-t-il si une question n'a pas d'image ?

Le champ `imageUrl` sera défini à `null`. Cela permet de distinguer les questions avec et sans images.

### Puis-je modifier le fichier enrichi manuellement ?

Oui, mais il sera écrasé lors de la prochaine exécution du script. Il est préférable de modifier les fichiers sources (`data_v3.json` ou `sample_questions.json`).

### Le script fonctionne-t-il avec d'autres formats d'images ?

Oui, tant que l'image est dans une balise `<img>` avec un attribut `src`, elle sera extraite. Le format de l'image (JPEG, PNG, etc.) n'a pas d'importance.

## 📚 Ressources

- [Dépôt GitHub](https://github.com/Raphzaf/flash_neiga)
- [Documentation principale](../README.md)
- [Script d'enrichissement](../scripts/enrich-questions.js)
