# PROMPT — Coach IA / Prof de code 24h/24 pour Flash Neiga

> Prompt complet à donner à Claude Code pour implémenter le coach pédagogique IA.
> Copier-coller tel quel (ou par phases) dans une session Claude Code sur ce repo.

---

## CONTEXTE DU PROJET

Tu travailles sur **Flash Neiga**, un site d'entraînement au code de la route **israélien** pour élèves francophones.

**Stack technique existant (à respecter, ne rien réécrire) :**
- **Backend** : FastAPI + SQLAlchemy (`backend/server.py`, `backend/models.py`, routes dans `backend/routes/`). Base SQL avec les modèles `UserDB`, `QuestionDB` (champs : `text`, `category`, `options` JSON, `explanation`, `image_url`), `ExamSessionDB` (champs : `user_id`, `status`, `answers` JSON `{question_id: selected_option_id}`, `question_ids`, `score`, `passed`), `CourseDB`, `TrafficSignDB`.
- **Frontend** : React (CRA) + Tailwind + composants Radix/shadcn dans `frontend/src/components/ui/`. Pages existantes : `Training.js`, `Exam.js`, `ExamDetails.js`, `Dashboard.js`, `Stats.js`, `Courses.js`. Appels API via axios (`frontend/src/api/`), auth JWT via `frontend/src/context/`.
- Le site est en **français**. Toutes les réponses de l'IA doivent être en français.

**Objectif produit :** l'élève doit sentir qu'il a **UN VÉRITABLE PROF DE CODE disponible 24h/24**. Le but est qu'il apprenne le cours **vite** grâce au site (pas qu'il bûche 3 mois) : chaque erreur devient une mini-leçon claire, ses fautes sont mémorisées et retravaillables, et après chaque série il reçoit un bilan pédagogique + un encouragement chiffré sur sa progression.

---

## FONCTIONNALITÉ 1 — Bouton « Petite leçon de code sur ce sujet » (coach IA sur réponse fausse)

**Comportement attendu :**
1. Dans `Training.js` et dans la revue d'examen (`ExamDetails.js`), quand l'élève a donné une **réponse fausse**, afficher sous la correction un bouton : **« 📚 Petite leçon de code sur ce sujet »**.
2. Au clic, appeler le backend qui interroge Claude et renvoie une mini-leçon structurée. Afficher la leçon dans un panneau/dialog (composants shadcn existants : `Card`, `Dialog` ou `Sheet`), avec un état de chargement (« Ton prof prépare ta leçon… »).

**Contenu de la mini-leçon (format structuré, 4 blocs) :**
- `explication` — explication **simple et claire** de pourquoi la réponse de l'élève est fausse et pourquoi la bonne réponse est correcte (ton bienveillant de prof, tutoiement, 3–6 phrases max).
- `regle` — rappel **succinct** de la règle du code de la route **israélien** concernée (2–4 phrases).
- `erreurs_a_eviter` — liste de 2 à 4 pièges/erreurs à éviter la prochaine fois sur ce type de question.
- `schema_svg` — si le sujet s'y prête (priorités, distances, intersections, signalisation), un **schéma SVG simple et autonome** (`<svg>...</svg>`, max ~300×200, couleurs lisibles, texte en français) pour mieux comprendre ; sinon `null`. Afficher le SVG via `dangerouslySetInnerHTML` **après sanitization avec DOMPurify** (déjà dans les dépendances, configurer le profil SVG).

**Backend — nouveau module `backend/routes/ai_coach.py` :**
- Utiliser le SDK officiel Python : `pip install anthropic` (ajouter à `backend/requirements.txt`). Client initialisé avec la clé lue depuis la variable d'environnement `ANTHROPIC_API_KEY` (ne jamais la mettre en dur ; l'ajouter au `.env` et à `render.yaml`).
- Modèle : **`claude-opus-4-8`**.
- Utiliser les **structured outputs** (`output_config={"format": {"type": "json_schema", "schema": ...}}`) pour garantir un JSON valide avec exactement les 4 champs ci-dessus. Ne PAS utiliser de prefill assistant (non supporté sur ce modèle). Ne PAS passer `temperature`/`top_p` (rejetés sur ce modèle).
- Endpoint : `POST /api/ai-coach/lesson` (auth JWT requise) avec body `{question_id, selected_option_id}`. Le backend récupère lui-même la question, ses options, la bonne réponse et le champ `explanation` en base — **ne jamais faire confiance au front pour le contenu de la question**.
- **System prompt** (à mettre dans une constante, contenu stable pour bénéficier du prompt caching avec `cache_control: {"type": "ephemeral"}`) :

  ```
  Tu es un professeur de code de la route israélien, patient et pédagogue,
  qui enseigne en français à des élèves francophones préparant l'examen
  théorique en Israël. Tu expliques simplement, tu tutoies l'élève, tu
  encourages sans infantiliser. Tes réponses sont courtes, concrètes et
  toujours exactes par rapport au code de la route israélien. Si la
  question fournit une explication officielle, appuie-toi dessus en
  priorité. Ne mentionne jamais que tu es une IA.
  ```
- Message utilisateur : texte de la question, les options, la réponse choisie (fausse), la bonne réponse, l'`explanation` officielle si présente, la `category`.
- **Cache en base** : créer une table `ai_lessons` (`id`, `question_id`, `selected_option_id`, `lesson_json`, `created_at`, index unique sur `(question_id, selected_option_id)`). Avant d'appeler Claude, vérifier le cache : une leçon pour une même question + même mauvaise réponse est réutilisable pour tous les élèves → coût API quasi nul en régime de croisière. Servir depuis le cache si présent.
- Gestion d'erreurs : encapsuler l'appel dans try/except sur les exceptions typées du SDK (`anthropic.RateLimitError`, `anthropic.APIStatusError`, `anthropic.APIConnectionError`) et renvoyer un 503 avec message français propre (« Le prof est momentanément indisponible, réessaie dans un instant »). L'échec de l'IA ne doit **jamais** casser le flux d'entraînement.

---

## FONCTIONNALITÉ 2 — Rubrique « Mes questions à retravailler » (mémoire des erreurs)

**Backend :**
- Nouvelle table `user_mistakes` : `id`, `user_id` (index), `question_id`, `times_wrong` (int, incrémenté à chaque erreur), `times_correct_since` (int), `mastered` (bool, défaut false), `first_wrong_at`, `last_wrong_at`. Contrainte unique `(user_id, question_id)`.
- Enregistrer/incrémenter une entrée à **chaque réponse fausse**, en mode entraînement (`Training`) comme en examen (au moment du calcul du résultat de la série). Réutiliser les points d'entrée existants qui traitent `TrainingAnswerRequest` et la complétion d'`ExamSessionDB` — ne pas créer un flux parallèle.
- Règle de maîtrise : quand l'élève répond **correctement 2 fois d'affilée** à une question en mode révision, passer `mastered = true` (la question sort de la liste mais reste en historique).
- Endpoints :
  - `GET /api/mistakes` → liste paginée des questions non maîtrisées de l'élève (question complète + stats + regroupement par `category`).
  - `POST /api/mistakes/review` → soumettre une réponse en mode révision, renvoie correct/incorrect + met à jour les compteurs.
- Migration : suivre le pattern existant (`backend/migrations/` / `ensure_schema_updated`).

**Frontend :**
- Nouvelle page `frontend/src/pages/Mistakes.js` (route `/mistakes`, protégée) : rubrique **« Mes questions à retravailler »**, accessible depuis le Dashboard et la navbar avec un badge indiquant le nombre de questions en attente.
- Contenu : liste groupée par catégorie, chaque question rejouable immédiatement (même UI de question que Training). Sur nouvelle erreur → bouton « Petite leçon » (Fonctionnalité 1). Sur bonne réponse → feedback positif ; à la 2e bonne réponse consécutive, animation « Maîtrisée ✅ » et retrait de la liste.
- L'élève peut retravailler ses erreurs **quand il veut**, sans limite.

---

## FONCTIONNALITÉ 3 — Bilan de série par le prof IA (après chaque série)

À la fin de **chaque série** (examen blanc terminé ou série d'entraînement d'au moins 10 questions) :

**Backend — `POST /api/ai-coach/series-report` (auth requise, body `{session_id}`) :**
- Rassembler : score de la série, liste des questions ratées (texte, catégorie, réponse donnée vs bonne réponse, explication officielle), répartition des erreurs par catégorie, et les **titres des cours existants** (`CourseDB`) correspondant à ces catégories.
- Appeler `claude-opus-4-8` avec structured outputs, schéma :
  - `notions_maitrisees` : liste de notions/catégories où l'élève est solide (basé sur ses bonnes réponses).
  - `notions_a_retravailler` : liste `{notion, conseil, cours_recommande}` — `cours_recommande` doit pointer vers un **cours réel du site** (id + titre passés dans le prompt) : on conseille explicitement à l'élève d'aller renforcer ses connaissances avec MON contenu de cours.
  - `mini_cours` : pour **chaque erreur** de la série, un objet `{question_resume, explication_claire}` — un petit cours rapide avec des **EXPLICATIONS BIEN CLAIRES** sur l'erreur commise. C'est le cœur du bilan : l'élève doit comprendre chaque faute sans effort.
  - `message_prof` : 2–3 phrases de synthèse motivante du prof.
- Persister le bilan dans une table `series_reports` (`id`, `user_id`, `session_id` unique, `report_json`, `created_at`) pour pouvoir le réafficher sans rappeler l'API.

**Encouragement chiffré (calculé en SQL, PAS par l'IA — les chiffres doivent être exacts) :**
- Calculer le taux de réussite moyen de l'élève sur les 7 derniers jours vs les 7 jours précédents (à partir d'`ExamSessionDB` et des réponses d'entraînement).
- Injecter ces deux pourcentages dans le prompt du bilan pour que `message_prof` les reprenne, ET les afficher en dur dans l'UI sous la forme : **« Tu progresses ! La semaine dernière tu étais à 65 %, aujourd'hui 82 % de réussite 🎉 »**. S'il n'y a pas assez d'historique, message de bienvenue adapté (« Première semaine — continue, tes stats arrivent ! »).

**Frontend :**
- À l'écran de résultats de série (fin d'`Exam.js` / fin de série dans `Training.js`) : section « 🎓 Le bilan de ton prof » qui charge le rapport (avec skeleton de chargement), affiche : bandeau d'encouragement chiffré, notions maîtrisées (badges verts), notions à retravailler (badges orange + lien direct vers le cours recommandé sur `/courses`), puis la liste dépliable (Accordion) des mini-cours par erreur.
- Chaque question ratée de la série est aussi automatiquement ajoutée à « Mes questions à retravailler » (Fonctionnalité 2).

---

## FONCTIONNALITÉ 4 — Rubrique « Les questions pièges les plus fréquentes » (tous élèves confondus)

**Backend :**
- Agréger les erreurs de **tous les élèves confondus** à partir de `user_mistakes` : pour chaque question, `total_wrong` (somme des `times_wrong`), nombre d'élèves distincts l'ayant ratée, taux d'erreur estimé.
- Endpoint public authentifié `GET /api/trap-questions?limit=30` → top des questions qui collectent le plus de réponses fausses, avec la question complète, ses stats, et — si déjà générée — la « petite leçon » en cache (table `ai_lessons`) pour la mauvaise réponse la plus fréquente.
- Faire une **synthèse par Claude** : endpoint admin `POST /api/admin/trap-questions/synthesis` (réservé admin, comme les autres routes admin existantes) qui envoie le top 30 à `claude-opus-4-8` et génère une synthèse pédagogique : les grands thèmes pièges, pourquoi les élèves tombent dedans, conseils généraux. Stocker dans une table `trap_synthesis` (une ligne, régénérable). Option : recalcul hebdomadaire via un cron/script dans `backend/scripts/`.

**Frontend :**
- Nouvelle page `frontend/src/pages/TrapQuestions.js` (route `/questions-pieges`) : rubrique spéciale **« ⚠️ Les questions pièges les plus fréquentes au code »**.
- En haut : la synthèse pédagogique de Claude. En dessous : le classement des questions pièges (avec le % d'élèves piégés pour créer l'effet « attention, 73 % se trompent ici ! »), chacune jouable directement ; si l'élève se trompe → bouton « Petite leçon ».
- Lien depuis le Dashboard et la navbar.

---

## RÈGLES D'INTÉGRATION API CLAUDE (à respecter partout)

1. SDK officiel `anthropic` (Python), client `anthropic.Anthropic()` — jamais d'appel HTTP brut.
2. Modèle : `claude-opus-4-8` pour tous les appels.
3. Structured outputs via `output_config.format` (json_schema, `additionalProperties: false`, tous les champs `required`) pour chaque endpoint IA → parsing fiable, zéro regex.
4. `max_tokens` : 2048 pour une mini-leçon, 8000 pour un bilan de série ou la synthèse.
5. Prompt caching : system prompt stable en premier avec `cache_control: {"type": "ephemeral"}`, contenu variable (question, réponses de l'élève) toujours après.
6. Toujours brancher sur `response.stop_reason` avant de lire le contenu ; gérer les exceptions typées du SDK avec des messages d'erreur français côté client.
7. Coût maîtrisé : cache DB systématique (`ai_lessons`, `series_reports`, `trap_synthesis`) — on ne rappelle jamais Claude pour un contenu déjà généré.
8. Aucune donnée personnelle de l'élève (email, nom) dans les prompts — uniquement le contenu pédagogique.

---

## CRITÈRES D'ACCEPTATION

- [ ] Réponse fausse en Training → bouton « Petite leçon de code sur ce sujet » → leçon en < 10 s avec explication + règle israélienne + erreurs à éviter + schéma SVG quand pertinent.
- [ ] La même leçon redemandée est servie instantanément depuis le cache DB (aucun 2e appel API).
- [ ] Toute réponse fausse (Training ET Examen) atterrit dans « Mes questions à retravailler » ; 2 bonnes réponses consécutives en révision la font sortir.
- [ ] Fin de série → bilan du prof : notions maîtrisées, notions à retravailler avec lien vers un cours réel du site, mini-cours clair pour CHAQUE erreur, message d'encouragement.
- [ ] L'encouragement affiche des pourcentages réels calculés en SQL (semaine passée vs actuelle), jamais inventés par l'IA.
- [ ] Page « Questions pièges » : classement réel toutes-erreurs-confondues + synthèse pédagogique générée par Claude, régénérable par l'admin.
- [ ] Si l'API Claude est indisponible : le site fonctionne normalement, seuls les blocs IA affichent un message de réessai.
- [ ] Tout est en français, ton prof bienveillant, tutoiement.
- [ ] Tests backend pour : cache des leçons, enregistrement des erreurs, règle de maîtrise (2 bonnes réponses), calcul des pourcentages de progression, agrégation des questions pièges.

## ORDRE D'IMPLÉMENTATION SUGGÉRÉ

1. **Phase 1** : table `user_mistakes` + enregistrement des erreurs + page « Mes questions à retravailler » (aucune dépendance IA, valeur immédiate).
2. **Phase 2** : module `ai_coach.py` + bouton « Petite leçon » + cache `ai_lessons`.
3. **Phase 3** : bilan de série + encouragement chiffré.
4. **Phase 4** : questions pièges + synthèse admin.

Commence par la Phase 1 et vérifie chaque phase (backend testé + parcours frontend) avant de passer à la suivante.
