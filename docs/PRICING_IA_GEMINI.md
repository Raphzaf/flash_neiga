# Dossier de pricing — Coût de l'IA (Google Gemini) pour Flash Neiga

> Objectif : chiffrer précisément ce que coûte le coach IA (Gemini) selon l'usage,
> et donner les leviers pour maîtriser la facture. Modèle utilisé en production :
> **`gemini-flash-latest`** (= la dernière version stable de **Gemini 2.5 Flash**).
>
> ⚠️ Les tarifs Google sont exacts (source officielle, voir fin de document).
> Les **nombres de tokens par opération sont des estimations** raisonnables : le
> coût réel dépend de la longueur des questions/leçons. Voir §7 pour mesurer le réel.

---

## 1. Tarifs officiels Gemini (payant, « Standard tier »)

Prix par **1 million de tokens** (texte). L'entrée = ce qu'on envoie (prompt),
la sortie = ce que le modèle génère.

| Modèle | Entrée /1M | Sortie /1M | Cache contexte /1M |
|---|---|---|---|
| **Gemini 2.5 Flash** *(notre modèle)* | **0,30 $** | **2,50 $** | 0,03 $ |
| Gemini 2.5 Flash‑Lite | 0,10 $ | 0,40 $ | 0,01 $ |
| Gemini 2.5 Pro (≤200k) | 1,25 $ | 10,00 $ | 0,125 $ |

- **Mode Batch / Flex : ‑50 %** sur entrée et sortie (utile pour les tâches non temps‑réel, ex. la synthèse des questions pièges).
- Le **« thinking » est désactivé** dans notre code (`thinking_budget=0`) → **aucun token de réflexion facturé en plus**. C'est un point important : sans ça, un modèle 2.5 peut facturer 2 à 5× plus de tokens de sortie.
- On n'utilise **pas** le cache de contexte payant de Google : on a notre **propre cache en base** (voir §4), plus efficace pour notre cas.

---

## 2. Coût par opération (estimation, Gemini 2.5 Flash)

Hypothèses de tokens (prompt système + contenu + sortie) :

| Opération | Entrée (~tokens) | Sortie (~tokens) | **Coût unitaire** | Mise en cache |
|---|---:|---:|---:|---|
| **Mini‑leçon** (réponse fausse) | ~520 | ~450 | **≈ 0,0013 $** | ✅ par (question + mauvaise réponse) |
| **Bilan de série** (fin d'examen) | ~1 300 | ~1 200 | **≈ 0,0034 $** | ✅ par examen (`session_id`) |
| **Message de chat** (prof 24/24) | ~800 | ~250 | **≈ 0,0009 $** | ❌ (conversation unique) |
| **Synthèse questions pièges** | ~1 400 | ~800 | **≈ 0,0024 $** | ✅ (1 seule, régénérable) |

Repère simple : **1 000 tokens d'entrée = 0,0003 $**, **1 000 tokens de sortie = 0,0025 $**.

**Traduction concrète :** il faut environ **~770 mini‑leçons** ou **~1 100 messages de chat** pour dépenser **1 $**.

---

## 3. L'effet décisif du cache : la plupart des coûts sont « one‑shot »

Trois des quatre opérations sont **mises en cache en base** et **réutilisées pour tous les élèves** :

- **Mini‑leçons** : une leçon générée pour « question X + mauvaise réponse Y » ressert à **tous** les élèves qui feront la même erreur. En régime établi, presque toutes les leçons sont déjà en cache → **coût marginal ≈ 0**.
  - Pré‑générer **toutes** les combinaisons plausibles (ex. 1 000 questions × ~3 mauvaises réponses fréquentes = 3 000 leçons) coûterait **une seule fois ≈ 3 000 × 0,0013 $ ≈ 4 $**.
- **Bilans de série** : mis en cache par examen ; un même bilan n'est jamais regénéré.
- **Synthèse pièges** : une seule ligne en base, régénérée à la demande (admin) — quelques centimes par régénération.

➡️ **Le seul coût vraiment récurrent et proportionnel au nombre d'élèves, c'est le chat** (chaque conversation est unique).

---

## 4. Projections mensuelles à l'échelle

On raisonne par **élève actif / mois**, avec deux profils :

**Profil modéré** (~0,07 $/élève/mois)
- 8 examens → 8 bilans : 8 × 0,0034 $ = 0,027 $
- 40 messages de chat : 40 × 0,0009 $ = 0,036 $
- ~5 nouvelles leçons non encore en cache : 5 × 0,0013 $ = 0,007 $

**Profil intensif** (~0,21 $/élève/mois)
- 15 bilans : 0,051 $
- 150 messages de chat : 0,135 $
- 15 nouvelles leçons : 0,020 $

| Élèves actifs / mois | Profil modéré | Profil intensif |
|---:|---:|---:|
| 100 | **≈ 7 $** | **≈ 21 $** |
| 1 000 | **≈ 70 $** | **≈ 210 $** |
| 10 000 | **≈ 700 $** | **≈ 2 100 $** |

*(+ un coût unique de pré‑génération des leçons de l'ordre de quelques dollars, négligeable.)*

**Lecture business :** si l'accès est vendu, disons, 10–30 € à l'élève, un coût IA de
**0,07 à 0,21 $/élève/mois** représente **bien moins de 1–2 % du revenu**. La marge est très saine ; le chat est le seul poste à surveiller si l'usage explose.

---

## 5. Tier gratuit vs payant — ce qu'il faut savoir

**Tier gratuit** (clé AI Studio sans facturation liée), pour Gemini 2.5 Flash — ordres de grandeur, **à vérifier dans la console** car Google ajuste par projet :
- **~10 requêtes/minute (RPM)**
- **~1 500 requêtes/jour (RPD)**
- **~250 000 tokens/minute (TPM)**

➡️ **Suffisant pour démarrer / tester** (quelques dizaines d'utilisateurs peu simultanés).
➡️ **Bloquant en production** : 10 RPM = au plus ~10 leçons/chats **par minute** tous élèves confondus. Une classe qui s'entraîne en même temps sature tout de suite (erreurs 429).

**Tier 1** (facturation liée à la clé) :
- Limites bien plus hautes, activation quasi instantanée.
- **Plafond de dépense par défaut : 250 $/mois** (ajustable) — cohérent avec les projections ci‑dessus jusqu'à plusieurs milliers d'élèves.
- Limite de débit ~10 $/10 min au départ.

**Recommandation :** garder le tier gratuit pour les tests, **lier une facturation (Tier 1) pour la prod**, et **fixer un plafond mensuel** (garde‑fou budget). Notre code gère déjà les erreurs proprement : si le quota/débit est dépassé, l'élève voit « le prof est momentanément indisponible » et **le reste du site continue de marcher**.

---

## 6. Leviers pour réduire la facture (par ordre d'impact)

1. **Le cache en base est déjà en place** — c'est le plus gros levier, il neutralise le coût des leçons/bilans répétés. ✅ fait.
2. **Thinking désactivé** — évite de payer des tokens de réflexion invisibles. ✅ fait.
3. **Chat = le vrai poste variable** :
   - On plafonne déjà l'historique à **20 messages** (évite que chaque tour renvoie une conversation qui gonfle). ✅ fait.
   - Option : basculer **le chat** sur **Gemini 2.5 Flash‑Lite** (0,10 $ / 0,40 $) → **~5× moins cher** sur ce poste, en gardant Flash pour les leçons/bilans où la qualité compte. Réglable via `GEMINI_MODEL` (ou en séparant le modèle du chat).
4. **Mode Batch (‑50 %)** pour la **synthèse des questions pièges** (tâche non temps‑réel).
5. **Pré‑générer les leçons hors ligne** (script) plutôt qu'à la volée : même coût total, mais lissé et jamais ressenti par l'élève.
6. **Plafond de dépense Google** + alerte de budget : sécurité anti‑dérapage.

**Comparatif modèle (coût du poste chat, 1 000 élèves, profil intensif ~150 msg) :**

| Modèle du chat | Coût / message | ~/élève/mois | 1 000 élèves |
|---|---:|---:|---:|
| Gemini 2.5 Flash *(actuel)* | 0,0009 $ | 0,135 $ | ~135 $ |
| Gemini 2.5 Flash‑Lite | ~0,0002 $ | ~0,027 $ | ~27 $ |

---

## 7. Mesurer le coût **réel** (recommandé)

Les chiffres ci‑dessus sont des estimations. Pour suivre le vrai coût :

- Chaque réponse Gemini renvoie un **`usage_metadata`** (`prompt_token_count`, `candidates_token_count`, `total_token_count`). On peut **logger ces valeurs** à chaque appel (leçon / bilan / chat / synthèse) et sommer par jour.
- Côté Google : **AI Studio / Cloud Billing** donne la conso réelle par jour et par modèle, et permet de poser des **alertes de budget**.
- Je peux ajouter un **compteur d'usage** dans le backend (table `ai_usage` : date, type d'opération, tokens in/out) + un petit écran admin, pour voir le coût en temps réel. **Dis‑le‑moi si tu veux que je l'ajoute.**

---

## 8. Synthèse en une phrase

Grâce au **cache en base** et au **thinking désactivé**, le coach IA coûte de l'ordre de
**0,07 à 0,21 $ par élève actif et par mois** sur Gemini 2.5 Flash — soit **~70 à 210 $/mois pour 1 000 élèves** — le **chat** étant le seul poste vraiment proportionnel à l'usage (et divisible par ~5 en passant le chat sur Flash‑Lite si besoin). Pour la prod : **lier une facturation (Tier 1) et fixer un plafond mensuel**.

---

## Sources

- [Gemini API — Pricing (Google)](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini API — Rate limits (Google)](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Gemini API Free Tier 2026 — limites/quotas (analyse tierce)](https://tokenmix.ai/blog/gemini-api-free-tier-limits)
- [Gemini API Free Tier Rate Limits 2026 (analyse tierce)](https://www.aifreeapi.com/en/posts/gemini-api-free-tier-rate-limits)

*Tarifs relevés en juillet 2026 — à re‑vérifier périodiquement, Google fait évoluer sa grille.*
