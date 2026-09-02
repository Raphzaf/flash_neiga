# Précharger toutes les explications du prof

But : qu'aucun élève n'attende jamais. Les explications sont générées une fois,
écrites en base, puis servies instantanément — et gratuitement — à tous.

## Voir où l'on en est

```
GET /api/ai-coach/cache-coverage
```

Renvoie le nombre d'explications attendues (chaque couple question / mauvaise
réponse), combien sont déjà en cache, et ce qui manque par catégorie.

## Lancer le préchargement

Le script se lance depuis un shell sur le serveur (Render) ou en local avec la
même base :

```bash
# Ce qui serait généré, sans rien appeler ni dépenser :
python backend/scripts/warm_ai_cache.py --dry-run

# Un petit lot d'abord, pour mesurer le coût réel :
python backend/scripts/warm_ai_cache.py --limit 20

# Le préchargement complet :
python backend/scripts/warm_ai_cache.py
```

Avec ~1 800 questions à 3 mauvaises réponses chacune, compter environ
5 400 explications, soit à peu près une heure avec le réglage par défaut
(4 tâches en parallèle).

Options : `--workers N` (parallélisme), `--delay S` (pause entre deux appels,
0,5 s par défaut — c'est ce qui évite les 429), `--category "Panneaux"`,
`--limit N`.

## Ce qu'il faut savoir

- **Relançable sans risque.** Le script saute tout ce qui est déjà en cache.
  Interrompu (Ctrl-C, coupure, redéploiement), il reprend où il en était.
- **Un échec isolé n'arrête rien.** Les couples en erreur sont comptés et
  signalés en fin de passage ; il suffit de relancer.
- **Ça ne se lance pas depuis une requête web.** Plusieurs milliers d'appels ne
  tiennent pas dans un appel HTTP qu'un redéploiement interromprait — d'où le
  script, et l'endpoint de couverture pour suivre l'avancement.
- **Une question corrigée doit être repréchargée.** L'énoncé entre dans la clé
  de cache : modifier une question rend son explication caduque (c'est voulu).
  Purge-la avec `POST /api/ai-coach/cache/invalidate {"question_id": "..."}`,
  puis relance le script.

## Après le préchargement

Le front interroge `/api/ai-coach/lesson/peek` dès que l'élève voit son erreur :
c'est une simple lecture en base, qui ne déclenche jamais de génération. Quand
l'explication est déjà là — ce qui devient la règle une fois le script passé —
la leçon s'ouvre instantanément.

Rendement du cache (entrées mémorisées, appels économisés) :

```
GET /api/ai-coach/cache-stats
```
