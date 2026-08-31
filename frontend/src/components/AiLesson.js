import React, { useState, useEffect, useRef } from 'react';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { GraduationCap, BookOpen, AlertTriangle, Lightbulb, Loader2, WifiOff } from 'lucide-react';
import { toast } from 'sonner';
import InlineChat from './InlineChat';
import { getCachedLesson, prefetchLesson, fetchLesson } from '../lib/aiLessonCache';

/**
 * Bouton « Petite leçon de code sur ce sujet » + dialog affichant la mini-leçon
 * générée par le coach IA pour une (question, réponse fausse).
 *
 * Dès que le composant s'affiche (donc dès que l'élève voit son erreur), on
 * demande au serveur si la leçon est DÉJÀ mémorisée — une lecture gratuite, qui
 * ne déclenche aucune génération. Quand c'est le cas, et ce sera la règle une
 * fois le cache constitué, la leçon s'ouvre instantanément au clic.
 *
 * Props :
 *  - questionId (string, requis)
 *  - selectedOptionId (string, requis) : la mauvaise réponse donnée par l'élève
 *  - label (string, optionnel)
 *  - prefetch (bool) : précharger la leçon déjà en cache (défaut : oui)
 *  - variant / className : passés au bouton
 */
export default function AiLesson({ questionId, selectedOptionId, label, prefetch = true, variant = 'outline', className = '' }) {
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const [lesson, setLesson] = useState(() => getCachedLesson(questionId, selectedOptionId));
    // Évite un setState après démontage (l'élève enchaîne souvent les questions).
    const mounted = useRef(true);

    useEffect(() => () => { mounted.current = false; }, []);

    useEffect(() => {
        // La leçon change avec la question : on repart de ce que l'on sait déjà.
        const known = getCachedLesson(questionId, selectedOptionId);
        setLesson(known);
        if (known || !prefetch || !questionId || !selectedOptionId) return;

        let cancelled = false;
        prefetchLesson(questionId, selectedOptionId).then((preloaded) => {
            if (preloaded && !cancelled && mounted.current) setLesson(preloaded);
        });
        return () => { cancelled = true; };
    }, [questionId, selectedOptionId, prefetch]);

    const loadLesson = async () => {
        setOpen(true);
        if (lesson) return; // déjà chargée (préchargement ou consultation précédente)
        setLoading(true);
        try {
            const data = await fetchLesson(questionId, selectedOptionId);
            if (mounted.current) setLesson(data);
        } catch (e) {
            const msg = e.response?.data?.detail || "Le prof est momentanément indisponible, réessaie dans un instant.";
            toast.error(msg);
            if (mounted.current) setOpen(false);
        } finally {
            if (mounted.current) setLoading(false);
        }
    };

    return (
        <>
            <Button
                type="button"
                variant={variant}
                onClick={loadLesson}
                className={`gap-2 ${className}`}
            >
                <GraduationCap className="h-4 w-4" />
                {label || '📚 Petite leçon de code sur ce sujet'}
            </Button>

            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <GraduationCap className="h-5 w-5 text-sky-600 dark:text-sky-400" />
                            La leçon de ton prof
                        </DialogTitle>
                    </DialogHeader>

                    {loading ? (
                        <div className="py-12 flex flex-col items-center justify-center gap-3 text-slate-600 dark:text-slate-300">
                            <Loader2 className="h-8 w-8 animate-spin text-sky-500" />
                            <p>Ton prof prépare ta leçon…</p>
                        </div>
                    ) : lesson ? (
                        <div className="space-y-5">
                            {/* Repli : le prof n'a pas pu être joint, on affiche la correction officielle */}
                            {lesson.degraded && (
                                <p className="flex items-start gap-2 text-xs p-2 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200">
                                    <WifiOff className="h-4 w-4 shrink-0 mt-0.5" />
                                    <span>
                                        Voici la correction officielle. Ton prof n'est pas joignable à cet instant :
                                        rouvre cette leçon dans quelques minutes pour l'explication détaillée.
                                    </span>
                                </p>
                            )}

                            {/* Explication */}
                            <section>
                                <h4 className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white mb-1">
                                    <Lightbulb className="h-4 w-4 text-amber-500" /> Explication
                                </h4>
                                <p className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-line">
                                    {lesson.explication}
                                </p>
                            </section>

                            {/* Règle */}
                            {lesson.regle && (
                                <section className="p-3 rounded-xl bg-sky-50 dark:bg-sky-950/30 border border-sky-200 dark:border-sky-800">
                                    <h4 className="flex items-center gap-2 font-semibold text-sky-900 dark:text-sky-100 mb-1">
                                        <BookOpen className="h-4 w-4" /> La règle du code israélien
                                    </h4>
                                    <p className="text-sm text-sky-900/90 dark:text-sky-100/90 whitespace-pre-line">
                                        {lesson.regle}
                                    </p>
                                </section>
                            )}

                            {/* Erreurs à éviter */}
                            {Array.isArray(lesson.erreurs_a_eviter) && lesson.erreurs_a_eviter.length > 0 && (
                                <section>
                                    <h4 className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white mb-2">
                                        <AlertTriangle className="h-4 w-4 text-red-500" /> Les erreurs à éviter la prochaine fois
                                    </h4>
                                    <ul className="space-y-1">
                                        {lesson.erreurs_a_eviter.map((err, i) => (
                                            <li key={i} className="text-sm text-slate-700 dark:text-slate-300 flex gap-2">
                                                <span className="text-red-500">•</span>
                                                <span>{err}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </section>
                            )}

                            {/* Discussion contextuelle : l'élève peut approfondir avec le prof */}
                            <section className="pt-1">
                                <InlineChat
                                    context={`Leçon en cours pour l'élève.\nExplication : ${lesson.explication}\nRègle : ${lesson.regle}`}
                                    title="💬 Poser une question sur cette leçon"
                                />
                            </section>
                        </div>
                    ) : null}
                </DialogContent>
            </Dialog>
        </>
    );
}
