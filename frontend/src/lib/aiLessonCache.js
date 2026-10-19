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

/**
 * Délai au-delà duquel on considère que le prof ne répondra pas. Le proxy qui
 * sert le site coupe toute requête à 26 s, et le serveur rend la main bien
 * avant (explication ou correction officielle) : attendre davantage ne
 * servirait qu'à laisser l'élève devant un sablier.
 */
const REQUEST_TIMEOUT_MS = 30000;
/** Relectures de la leçon produite en arrière-plan après un repli (ms, cumulées). */
const BACKGROUND_POLL_DELAYS_MS = [0, 5000, 8000, 12000];
/** Délai court pour le préchargement : il ne doit jamais gêner la page. */
const PEEK_TIMEOUT_MS = 8000;

export const lessonKey = (questionId, selectedOptionId) => `${questionId}::${selectedOptionId}`;

/** Une leçon affichable : un texte d'explication non vide. Rien d'autre ne s'affiche. */
export function isValidLesson(lesson) {
    return Boolean(lesson && typeof lesson.explication === 'string' && lesson.explication.trim());
}

/** Leçon déjà connue pour ce couple (question, mauvaise réponse), ou null. */
export function getCachedLesson(questionId, selectedOptionId) {
    if (!questionId || !selectedOptionId) return null;
    return lessons.get(lessonKey(questionId, selectedOptionId)) || null;
}

/**
 * Ne mémorise QUE les vraies leçons.
 *
 * Un repli (la correction officielle, servie quand le prof n'a pas répondu à
 * temps) ne doit jamais être gardé : la vraie leçon arrive quelques secondes
 * plus tard en base, et la mettre en cache ici la rendrait inaccessible pour
 * tout le reste de la session.
 */
function remember(key, lesson) {
    if (isValidLesson(lesson) && !lesson.degraded) lessons.set(key, lesson);
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
        if (res.data?.available && isValidLesson(res.data.lesson)) {
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
        .then((res) => {
            // Une réponse sans explication n'est jamais présentée comme réussie.
            if (!isValidLesson(res.data)) {
                const error = new Error("Réponse du prof incomplète.");
                error.malformed = true;
                throw error;
            }
            return remember(key, res.data);
        })
        .finally(() => inflight.delete(key));

    inflight.set(key, promise);
    return promise;
}

/**
 * Attend que la leçon produite en arrière-plan soit disponible, puis la renvoie.
 *
 * Après un repli, le serveur a mis la vraie leçon en file : elle arrive en base
 * quelques secondes plus tard. On repasse par `peek` (lecture gratuite, jamais
 * de génération) à quelques reprises, puis on abandonne. Renvoie null si elle
 * n'est pas prête ou si `signal` a été annulé (l'élève est passé à autre chose).
 */
export async function awaitBackgroundLesson(questionId, selectedOptionId, firstDelayMs, signal) {
    const delays = BACKGROUND_POLL_DELAYS_MS.map((extra, i) => (i === 0 ? firstDelayMs : extra));
    for (const delay of delays) {
        await new Promise((resolve) => setTimeout(resolve, delay));
        if (signal?.aborted) return null;
        const lesson = await prefetchLesson(questionId, selectedOptionId);
        if (signal?.aborted) return null;
        if (lesson) return lesson;
    }
    return null;
}

/** Oublie une leçon (utile après correction d'une question). */
export function forgetLesson(questionId, selectedOptionId) {
    lessons.delete(lessonKey(questionId, selectedOptionId));
}
