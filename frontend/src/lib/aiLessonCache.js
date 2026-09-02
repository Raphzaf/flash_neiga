/**
 * Mémoire de session des leçons du prof, côté navigateur.
 *
 * Elle complète le cache serveur (table `ai_answer_cache`) sur deux points que
 * le back ne peut pas couvrir :
 *
 *  - **Zéro aller-retour** quand l'élève rouvre une leçon déjà consultée, ou
 *    quand il revient sur la même erreur en fin de série.
 *  - **Une seule requête en vol par leçon** : deux composants montés sur la
 *    même question (correction + récapitulatif) partagent la même promesse au
 *    lieu d'interroger le serveur chacun de leur côté.
 *
 * Le cache vit le temps de l'onglet : il n'a pas vocation à durer, la
 * persistance longue est le rôle de la base.
 */
import axios from 'axios';

const lessons = new Map();   // clé -> leçon résolue
const inflight = new Map();  // clé -> promesse en cours

/** Délai au-delà duquel on considère que le prof ne répondra pas. */
const REQUEST_TIMEOUT_MS = 45000;
/** Délai court pour le préchargement : il ne doit jamais gêner la page. */
const PEEK_TIMEOUT_MS = 8000;

export const lessonKey = (questionId, selectedOptionId) => `${questionId}::${selectedOptionId}`;

/** Leçon déjà connue pour ce couple (question, mauvaise réponse), ou null. */
export function getCachedLesson(questionId, selectedOptionId) {
    if (!questionId || !selectedOptionId) return null;
    return lessons.get(lessonKey(questionId, selectedOptionId)) || null;
}

function remember(key, lesson) {
    if (lesson) lessons.set(key, lesson);
    return lesson;
}

/**
 * Précharge la leçon SANS jamais déclencher de génération payante.
 *
 * On interroge `/lesson/peek`, qui ne répond que si la leçon est déjà en base.
 * À appeler dès que la mauvaise réponse s'affiche : dans la grande majorité des
 * cas la leçon existe déjà et le clic de l'élève devient instantané.
 * Silencieux par construction — un préchargement raté n'est pas une erreur.
 */
export async function prefetchLesson(questionId, selectedOptionId) {
    if (!questionId || !selectedOptionId) return null;
    const key = lessonKey(questionId, selectedOptionId);
    if (lessons.has(key) || inflight.has(key)) return lessons.get(key) || null;

    try {
        const res = await axios.post(
            '/api/ai-coach/lesson/peek',
            { question_id: questionId, selected_option_id: selectedOptionId },
            { timeout: PEEK_TIMEOUT_MS },
        );
        if (res.data?.available && res.data.lesson) {
            return remember(key, res.data.lesson);
        }
    } catch (e) {
        // Hors ligne, non abonné, session expirée… : on n'affiche rien, le clic
        // de l'élève repassera par le chemin normal qui, lui, remonte l'erreur.
    }
    return null;
}

/**
 * Récupère la leçon : mémoire de session, puis serveur (qui sert son cache ou
 * génère). Les appels concurrents sur la même leçon partagent une requête.
 */
export function fetchLesson(questionId, selectedOptionId) {
    const key = lessonKey(questionId, selectedOptionId);

    const known = lessons.get(key);
    if (known) return Promise.resolve(known);

    const pending = inflight.get(key);
    if (pending) return pending;

    const promise = axios
        .post(
            '/api/ai-coach/lesson',
            { question_id: questionId, selected_option_id: selectedOptionId },
            { timeout: REQUEST_TIMEOUT_MS },
        )
        .then((res) => remember(key, res.data))
        .finally(() => inflight.delete(key));

    inflight.set(key, promise);
    return promise;
}

/** Oublie une leçon (utile après correction d'une question). */
export function forgetLesson(questionId, selectedOptionId) {
    lessons.delete(lessonKey(questionId, selectedOptionId));
}
