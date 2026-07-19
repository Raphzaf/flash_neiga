import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../components/ui/accordion';
import { CheckCircle, XCircle, ArrowLeft, AlertTriangle, Users } from 'lucide-react';
import { toast } from 'sonner';
import AiLesson from '../components/AiLesson';

// Une question piège, jouable directement (vérification côté client).
function TrapCard({ item, rank }) {
    const q = item.question;
    const [selected, setSelected] = useState(null);
    const [answered, setAnswered] = useState(false);

    const correctId = (q.options || []).find((o) => o.is_correct)?.id;

    const handleAnswer = (optId) => {
        if (answered) return;
        setSelected(optId);
        setAnswered(true);
    };

    const isWrong = answered && selected !== correctId;

    return (
        <Card className="border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
            <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-start gap-3">
                        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-700 text-sm font-bold text-slate-700 dark:text-slate-200">
                            {rank}
                        </span>
                        <h3 className="text-base font-semibold text-slate-900 dark:text-white">{q.text}</h3>
                    </div>
                    <Badge variant="destructive" className="shrink-0 gap-1">
                        <Users className="h-3 w-3" /> {item.stats.percent_trapped}%
                    </Badge>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-4 ml-10">
                    {item.stats.distinct_users} élève(s) se trompent sur cette question · {item.stats.total_wrong} erreurs au total
                </p>

                {q.image_url && (
                    <div className="mb-4 h-44 bg-black flex items-center justify-center rounded-lg overflow-hidden">
                        <img src={q.image_url} alt="Contexte" className="h-full object-contain" />
                    </div>
                )}

                <div className="grid grid-cols-1 gap-2">
                    {(q.options || []).map((opt) => {
                        let cls = 'border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white hover:border-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/30';
                        let icon = null;
                        if (answered) {
                            if (opt.id === correctId) {
                                cls = 'border-sky-500 bg-sky-100 dark:bg-sky-950/30 text-sky-900 dark:text-sky-100 ring-1 ring-sky-500';
                                icon = <CheckCircle className="h-5 w-5 text-sky-600 dark:text-sky-400 ml-auto" />;
                            } else if (opt.id === selected) {
                                cls = 'border-red-500 bg-red-100 dark:bg-red-950/30 text-red-900 dark:text-red-100 ring-1 ring-red-500';
                                icon = <XCircle className="h-5 w-5 text-red-600 dark:text-red-400 ml-auto" />;
                            } else {
                                cls = 'opacity-50';
                            }
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

                {answered && q.explanation && (
                    <div className="mt-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-700/50 text-sm text-slate-700 dark:text-slate-200">
                        {q.explanation}
                    </div>
                )}

                {isWrong && (
                    <div className="mt-3">
                        <AiLesson questionId={q.id} selectedOptionId={selected} className="w-full justify-center" />
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

export default function TrapQuestions() {
    const [loading, setLoading] = useState(true);
    const [questions, setQuestions] = useState([]);
    const [synthesis, setSynthesis] = useState(null);

    useEffect(() => {
        const load = async () => {
            setLoading(true);
            try {
                const res = await axios.get('/api/trap-questions?limit=30');
                setQuestions(res.data.questions || []);
                setSynthesis(res.data.synthesis || null);
            } catch (e) {
                toast.error('Impossible de charger les questions pièges');
            } finally {
                setLoading(false);
            }
        };
        load();
    }, []);

    return (
        <div className="min-h-screen pb-20">
            <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 sticky top-0 z-30 p-4">
                <div className="max-w-4xl mx-auto flex items-center gap-3">
                    <Link to="/">
                        <Button variant="ghost" size="icon"><ArrowLeft className="h-5 w-5" /></Button>
                    </Link>
                    <h1 className="text-xl font-heading font-bold text-slate-900 dark:text-white">
                        ⚠️ Les questions pièges les plus fréquentes au code
                    </h1>
                </div>
            </header>

            <main className="max-w-4xl mx-auto p-4 mt-4 space-y-6">
                {loading ? (
                    <div className="text-center p-12 text-slate-600 dark:text-slate-300">Chargement…</div>
                ) : (
                    <>
                        {/* Synthèse pédagogique du prof */}
                        {synthesis && (
                            <div className="rounded-2xl border border-sky-200 dark:border-sky-800 bg-sky-50 dark:bg-sky-950/30 p-5">
                                <h2 className="font-bold text-sky-900 dark:text-sky-100 mb-2">La synthèse de ton prof</h2>
                                <p className="text-sm text-sky-900/90 dark:text-sky-100/90 mb-3">{synthesis.intro}</p>
                                {synthesis.themes?.length > 0 && (
                                    <Accordion type="multiple" className="space-y-2">
                                        {synthesis.themes.map((t, i) => (
                                            <AccordionItem
                                                key={i}
                                                value={`theme-${i}`}
                                                className="border border-sky-200 dark:border-sky-800 rounded-xl px-4 bg-white/60 dark:bg-slate-800/40"
                                            >
                                                <AccordionTrigger className="hover:no-underline text-left text-sm font-semibold text-slate-900 dark:text-white">
                                                    {t.titre}
                                                </AccordionTrigger>
                                                <AccordionContent className="space-y-2">
                                                    <p className="text-sm text-slate-700 dark:text-slate-300"><strong>Pourquoi :</strong> {t.pourquoi}</p>
                                                    <p className="text-sm text-slate-700 dark:text-slate-300"><strong>Le conseil :</strong> {t.conseil}</p>
                                                </AccordionContent>
                                            </AccordionItem>
                                        ))}
                                    </Accordion>
                                )}
                            </div>
                        )}

                        {questions.length === 0 ? (
                            <div className="text-center p-12 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-2xl">
                                <AlertTriangle className="h-10 w-10 mx-auto mb-4 text-amber-500" />
                                <p className="text-slate-600 dark:text-slate-300">
                                    Pas encore assez de données. Les questions qui piègent le plus les élèves apparaîtront ici.
                                </p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 gap-4">
                                {questions.map((item, idx) => (
                                    <TrapCard key={item.question.id} item={item} rank={idx + 1} />
                                ))}
                            </div>
                        )}
                    </>
                )}
            </main>
        </div>
    );
}
