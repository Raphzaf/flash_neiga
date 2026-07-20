import React, { useState } from 'react';
import axios from 'axios';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { GraduationCap, BookOpen, AlertTriangle, Lightbulb, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import InlineChat from './InlineChat';

/**
 * Bouton « Petite leçon de code sur ce sujet » + dialog affichant la mini-leçon
 * générée par le coach IA pour une (question, réponse fausse).
 *
 * Props :
 *  - questionId (string, requis)
 *  - selectedOptionId (string, requis) : la mauvaise réponse donnée par l'élève
 *  - label (string, optionnel)
 *  - variant / className : passés au bouton
 */
export default function AiLesson({ questionId, selectedOptionId, label, variant = 'outline', className = '' }) {
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const [lesson, setLesson] = useState(null);

    const loadLesson = async () => {
        setOpen(true);
        if (lesson) return; // déjà chargée
        setLoading(true);
        try {
            const res = await axios.post('/api/ai-coach/lesson', {
                question_id: questionId,
                selected_option_id: selectedOptionId,
            });
            setLesson(res.data);
        } catch (e) {
            const msg = e.response?.data?.detail || "Le prof est momentanément indisponible, réessaie dans un instant.";
            toast.error(msg);
            setOpen(false);
        } finally {
            setLoading(false);
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
