import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { GraduationCap, Lightbulb, Loader2, WifiOff, AlertTriangle, RotateCcw } from 'lucide-react';
import InlineChat from './InlineChat';
import {
    getCachedLesson, prefetchLesson, fetchLesson, awaitBackgroundLesson, isValidLesson, lessonKey,
} from '../lib/aiLessonCache';

/**
 * Bouton « Petite leçon de code sur ce sujet » + fenêtre affichant l'explication
 * courte du prof pour une (question, réponse fausse).
 *
 * Dès que le composant s'affiche (donc dès que l'élève voit son erreur), on
 * demande au serveur si l'explication est DÉJÀ mémorisée — une lecture
 * gratuite, qui ne déclenche aucune génération. Quand c'est le cas, elle
 * s'ouvre instantanément au clic.
 *
 * Fiabilité :
 *  - chaque réponse est rattachée à la question qui l'a demandée : une réponse
 *    tardive ne remplace jamais l'explication de la question affichée ;
 *  - un seul chargement à la fois (bouton désactivé, requêtes mutualisées) ;
 *  - une réponse vide ou mal formée est traitée comme une erreur, avec un
 *    bouton « Réessayer » — jamais affichée comme une explication.
 *
 * Props :
 *  - questionId (string, requis)
 *  - selectedOptionId (string, requis) : la mauvaise réponse donnée par l'élève
 *  - label (string, optionnel)
 *  - prefetch (bool) : précharger l'explication déjà en cache (défaut : oui)
 *  - variant / className : passés au bouton
 */
export default function AiLesson({ questionId, selectedOptionId, label, prefetch = true, variant = 'outline', className = '' }) {
    const key = questionId && selectedOptionId ? lessonKey(questionId, selectedOptionId) : null;
    const [open, setOpen] = useState(false);
    // État rattaché à une clé : ce qui appartient à une autre question est ignoré.
    const [state, setState] = useState(() => ({
        key,
        status: getCachedLesson(questionId, selectedOptionId) ? 'ready' : 'idle',
        lesson: getCachedLesson(questionId, selectedOptionId),
        error: null,
        waiting: false,
    }));
    const keyRef = useRef(key);
    const abortRef = useRef(null);

    // Question (ou réponse) différente : on repart de zéro et on oublie les
    // requêtes en cours de l'ancienne — leurs réponses seront ignorées.
    useEffect(() => {
        keyRef.current = key;
        abortRef.current?.abort();
        abortRef.current = null;
        const known = getCachedLesson(questionId, selectedOptionId);
        setState({ key, status: known ? 'ready' : 'idle', lesson: known, error: null, waiting: false });
        setOpen(false);
        if (known || !prefetch || !key) return undefined;

        let cancelled = false;
        prefetchLesson(questionId, selectedOptionId).then((preloaded) => {
            if (!cancelled && preloaded && keyRef.current === key) {
                setState((s) => (s.key === key && s.status !== 'ready'
                    ? { ...s, status: 'ready', lesson: preloaded, error: null } : s));
            }
        });
        return () => { cancelled = true; };
    }, [key, questionId, selectedOptionId, prefetch]);

    // Démontage : plus aucune mise à jour à faire.
    useEffect(() => () => { keyRef.current = null; abortRef.current?.abort(); }, []);

    const update = useCallback((forKey, patch) => {
        if (keyRef.current !== forKey) return; // réponse d'une autre question
        setState((s) => (s.key === forKey ? { ...s, ...patch } : s));
    }, []);

    const load = useCallback(async () => {
        const forKey = key;
        if (!forKey) return;
        update(forKey, { status: 'loading', error: null, waiting: false });
        try {
            const data = await fetchLesson(questionId, selectedOptionId);
            update(forKey, { status: 'ready', lesson: data, error: null });

            // Repli : le prof n'a pas répondu dans le temps imparti, mais le
            // serveur termine la vraie explication en arrière-plan. On va la
            // chercher et on la substitue sous les yeux de l'élève.
            if (data.degraded && data.retry_after_s) {
                const controller = new AbortController();
                abortRef.current = controller;
                update(forKey, { waiting: true });
                const better = await awaitBackgroundLesson(
                    questionId, selectedOptionId, data.retry_after_s * 1000, controller.signal,
                );
                if (controller.signal.aborted) return;
                update(forKey, better
                    ? { lesson: better, waiting: false }
                    : { waiting: false });
            }
        } catch (e) {
            const detail = e.response?.data?.detail;
            let message = "Le prof n'a pas pu répondre. Vérifie ta connexion et réessaie.";
            if (e.code === 'ECONNABORTED') message = "Le prof met trop de temps à répondre. Réessaie dans un instant.";
            else if (e.malformed) message = "La réponse du prof était incomplète. Réessaie.";
            else if (e.response?.status === 400 && detail) message = detail;
            else if (e.response?.status === 402 || e.response?.status === 403) message = detail || "Cette fonction n'est pas incluse dans ta formule.";
            update(forKey, { status: 'error', error: message, waiting: false });
        }
    }, [key, questionId, selectedOptionId, update]);

    const openLesson = () => {
        setOpen(true);
        const current = state.key === key ? state : null;
        if (current?.status === 'loading') return; // déjà en route : pas de 2e requête
        if (current?.status === 'ready' && isValidLesson(current.lesson) && !current.lesson.degraded) return;
        if (current?.status === 'ready' && current.waiting) return;
        load();
    };

    const view = state.key === key ? state : { status: 'idle', lesson: null, error: null, waiting: false };
    const { lesson } = view;
    const loading = view.status === 'loading';

    return (
        <>
            <Button
                type="button"
                variant={variant}
                onClick={openLesson}
                disabled={!key}
                aria-busy={loading}
                className={`gap-2 ${className}`}
            >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <GraduationCap className="h-4 w-4" />}
                {label || '📚 Petite leçon de code sur ce sujet'}
            </Button>

            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <GraduationCap className="h-5 w-5 text-sky-600 dark:text-sky-400" />
                            La leçon de ton prof
                        </DialogTitle>
                        <DialogDescription className="sr-only">
                            Explication de ton erreur sur cette question.
                        </DialogDescription>
                    </DialogHeader>

                    {(loading || view.status === 'idle') && (
                        <div className="py-10 flex flex-col items-center justify-center gap-3 text-slate-600 dark:text-slate-300" role="status">
                            <Loader2 className="h-8 w-8 animate-spin text-sky-500" />
                            <p>Ton prof prépare ton explication…</p>
                        </div>
                    )}

                    {view.status === 'error' && (
                        <div className="py-6 flex flex-col items-center text-center gap-3" role="alert">
                            <AlertTriangle className="h-8 w-8 text-amber-500" />
                            <p className="text-sm text-slate-700 dark:text-slate-300">{view.error}</p>
                            <Button type="button" onClick={load} className="gap-2">
                                <RotateCcw className="h-4 w-4" /> Réessayer
                            </Button>
                        </div>
                    )}

                    {view.status === 'ready' && isValidLesson(lesson) && (
                        <div className="space-y-4">
                            {/* Repli : la correction officielle, en attendant l'explication du prof */}
                            {lesson.degraded && (
                                <div className="flex items-start gap-2 text-xs p-2 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200">
                                    <WifiOff className="h-4 w-4 shrink-0 mt-0.5" />
                                    <span className="flex-1">
                                        {view.waiting
                                            ? "Voici la correction officielle. Ton prof rédige son explication : elle remplacera ce texte dès qu'elle sera prête."
                                            : "Voici la correction officielle. Ton prof n'a pas pu répondre à temps."}
                                    </span>
                                    {view.waiting ? (
                                        <Loader2 className="h-4 w-4 shrink-0 mt-0.5 animate-spin" />
                                    ) : (
                                        <button type="button" onClick={load} className="shrink-0 font-medium underline">
                                            Réessayer
                                        </button>
                                    )}
                                </div>
                            )}

                            {/* Données de la question insuffisantes : on le dit, sans inventer */}
                            {lesson.donnees_suffisantes === false && (
                                <p className="flex items-start gap-2 text-xs p-2 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200">
                                    <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                                    <span>Cette question ne peut pas être expliquée de façon fiable.</span>
                                </p>
                            )}

                            <section>
                                <h4 className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white mb-1.5">
                                    <Lightbulb className="h-4 w-4 text-amber-500" /> Explication
                                </h4>
                                <p className="text-[15px] leading-relaxed text-slate-700 dark:text-slate-300 whitespace-pre-line">
                                    {lesson.explication}
                                </p>
                            </section>

                            {/* Discussion contextuelle : l'élève peut approfondir avec le prof */}
                            <section className="pt-1">
                                <InlineChat
                                    context={`Explication de l'erreur de l'élève : ${lesson.explication}`}
                                    title="💬 Poser une question sur cette explication"
                                />
                            </section>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </>
    );
}
