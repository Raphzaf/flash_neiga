import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../components/ui/accordion';
import { CheckCircle, XCircle, Info, ArrowLeft, RefreshCw, Trophy } from 'lucide-react';
import { toast } from 'sonner';
import { ExplanationWithLinks } from '../components/ExplanationWithLinks';
import AiLesson from '../components/AiLesson';

// Carte d'une question à retravailler, rejouable sur place.
function MistakeCard({ item, onMastered }) {
    const q = item.question;
    const [selected, setSelected] = useState(null);
    const [feedback, setFeedback] = useState(null); // { is_correct, correct_option_id, explanation, mastered, times_correct_since }
    const [submitting, setSubmitting] = useState(false);

    const handleAnswer = async (optionId) => {
        if (feedback || submitting) return;
        setSelected(optionId);
        setSubmitting(true);
        try {
            const res = await axios.post('/api/mistakes/review', {
                question_id: q.id,
                selected_option_id: optionId,
            });
            setFeedback(res.data);
            if (res.data.mastered) {
                toast.success('Question maîtrisée ✅');
                // Laisse le temps de voir le feedback avant de retirer la carte
                setTimeout(() => onMastered(q.id), 1200);
            }
        } catch (e) {
            toast.error('Erreur lors de la vérification');
            setSelected(null);
        } finally {
            setSubmitting(false);
        }
    };

    const retry = () => {
        setSelected(null);
        setFeedback(null);
    };

    return (
        <Card className="border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
            {q.image_url && (
                <div className="h-48 bg-black flex items-center justify-center">
                    <img src={q.image_url} alt="Contexte" className="h-full object-contain" />
                </div>
            )}
            <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3 mb-4">
                    <h3 className="text-base font-semibold text-slate-900 dark:text-white">{q.text}</h3>
                    <Badge variant="destructive" className="shrink-0">
                        raté {item.stats.times_wrong}×
                    </Badge>
                </div>

                <div className="grid grid-cols-1 gap-2">
                    {q.options.map((opt) => {
                        let cls = 'border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white hover:border-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/30';
                        let icon = null;
                        if (feedback) {
                            if (opt.id === feedback.correct_option_id) {
                                cls = 'border-sky-500 bg-sky-100 dark:bg-sky-950/30 text-sky-900 dark:text-sky-100 ring-1 ring-sky-500';
                                icon = <CheckCircle className="h-5 w-5 text-sky-600 dark:text-sky-400 ml-auto" />;
                            } else if (opt.id === selected && opt.id !== feedback.correct_option_id) {
                                cls = 'border-red-500 bg-red-100 dark:bg-red-950/30 text-red-900 dark:text-red-100 ring-1 ring-red-500';
                                icon = <XCircle className="h-5 w-5 text-red-600 dark:text-red-400 ml-auto" />;
                            } else {
                                cls = 'opacity-50';
                            }
                        } else if (selected === opt.id) {
                            cls = 'border-primary bg-primary/5 ring-1 ring-primary';
                        }
                        return (
                            <div
                                key={opt.id}
                                onClick={() => handleAnswer(opt.id)}
                                className={`p-3 rounded-xl border-2 cursor-pointer transition-all flex items-center ${cls}`}
                            >
                                <span className="font-medium text-sm">{opt.text}</span>
                                {icon}
                            </div>
                        );
                    })}
                </div>

                {feedback && (
                    <div className={`mt-4 p-4 rounded-xl border ${
                        feedback.mastered
                            ? 'bg-emerald-100 dark:bg-emerald-950/30 border-emerald-300 dark:border-emerald-700 text-emerald-900 dark:text-emerald-100'
                            : feedback.is_correct
                                ? 'bg-sky-100 dark:bg-sky-950/30 border-sky-300 dark:border-sky-700 text-sky-900 dark:text-sky-100'
                                : 'bg-yellow-100 dark:bg-yellow-950/30 border-yellow-300 dark:border-yellow-700 text-yellow-900 dark:text-yellow-100'
                    }`}>
                        <div className="flex items-start gap-3">
                            {feedback.mastered
                                ? <Trophy className="h-5 w-5 mt-0.5 flex-shrink-0" />
                                : <Info className="h-5 w-5 mt-0.5 flex-shrink-0" />}
                            <div className="flex-1">
                                <div className="font-bold mb-1">
                                    {feedback.mastered
                                        ? 'Bravo, question maîtrisée !'
                                        : feedback.is_correct
                                            ? `Correct ! Encore une bonne réponse et elle sort de ta liste (${feedback.times_correct_since}/2).`
                                            : 'Pas encore — recommence pour la maîtriser.'}
                                </div>
                                <ExplanationWithLinks explanation={feedback.explanation} onCourseClick={() => {}} />
                            </div>
                        </div>
                        {!feedback.is_correct && (
                            <div className="mt-3">
                                <AiLesson
                                    questionId={q.id}
                                    selectedOptionId={selected}
                                    className="w-full justify-center"
                                />
                            </div>
                        )}
                        {!feedback.mastered && (
                            <Button
                                onClick={retry}
                                variant="outline"
                                className="mt-3 w-full"
                            >
                                <RefreshCw className="mr-2 h-4 w-4" /> Réessayer
                            </Button>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

export default function Mistakes() {
    const [loading, setLoading] = useState(true);
    const [categories, setCategories] = useState([]);
    const [total, setTotal] = useState(0);

    const fetchMistakes = useCallback(async () => {
        setLoading(true);
        try {
            const res = await axios.get('/api/mistakes?limit=200');
            setCategories(res.data.categories || []);
            setTotal(res.data.total || 0);
        } catch (e) {
            toast.error('Impossible de charger tes questions à retravailler');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchMistakes();
    }, [fetchMistakes]);

    // Retire une question maîtrisée de la liste sans recharger toute la page.
    const handleMastered = (questionId) => {
        setCategories((prev) =>
            prev
                .map((cat) => ({
                    ...cat,
                    questions: cat.questions.filter((it) => it.question.id !== questionId),
                }))
                .filter((cat) => cat.questions.length > 0)
        );
        setTotal((t) => Math.max(0, t - 1));
    };

    return (
        <div className="min-h-screen pb-20">
            <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 sticky top-0 z-30 p-4">
                <div className="max-w-4xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Link to="/">
                            <Button variant="ghost" size="icon"><ArrowLeft className="h-5 w-5" /></Button>
                        </Link>
                        <h1 className="text-xl font-heading font-bold text-slate-900 dark:text-white">
                            Mes questions à retravailler
                        </h1>
                    </div>
                    <Badge variant="secondary">{total} en attente</Badge>
                </div>
            </header>

            <main className="max-w-4xl mx-auto p-4 mt-4">
                {loading ? (
                    <div className="text-center p-12 text-slate-600 dark:text-slate-300">Chargement…</div>
                ) : total === 0 ? (
                    <div className="text-center p-12 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-2xl">
                        <Trophy className="h-10 w-10 mx-auto mb-4 text-emerald-500" />
                        <p className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
                            Rien à retravailler pour le moment 🎉
                        </p>
                        <p className="text-slate-600 dark:text-slate-300 mb-6">
                            Tes erreurs d'entraînement et d'examen apparaîtront ici pour que tu puisses les revoir quand tu veux.
                        </p>
                        <Link to="/training">
                            <Button>Aller m'entraîner</Button>
                        </Link>
                    </div>
                ) : (
                    <Accordion type="multiple" defaultValue={categories.map((c) => c.category)} className="space-y-3">
                        {categories.map((cat) => (
                            <AccordionItem
                                key={cat.category}
                                value={cat.category}
                                className="border border-slate-200 dark:border-slate-700 rounded-xl bg-white/50 dark:bg-slate-800/50 px-4"
                            >
                                <AccordionTrigger className="hover:no-underline">
                                    <span className="flex items-center gap-2 text-slate-900 dark:text-white font-semibold">
                                        {cat.category}
                                        <Badge variant="outline">{cat.questions.length}</Badge>
                                    </span>
                                </AccordionTrigger>
                                <AccordionContent>
                                    <div className="grid grid-cols-1 gap-4 pb-2">
                                        {cat.questions.map((item) => (
                                            <MistakeCard
                                                key={item.question.id}
                                                item={item}
                                                onMastered={handleMastered}
                                            />
                                        ))}
                                    </div>
                                </AccordionContent>
                            </AccordionItem>
                        ))}
                    </Accordion>
                )}
            </main>
        </div>
    );
}
