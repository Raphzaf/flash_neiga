import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from './ui/accordion';
import { GraduationCap, TrendingUp, CheckCircle2, RotateCcw, BookOpen, Loader2, RefreshCw } from 'lucide-react';

/**
 * « Le bilan de ton prof » affiché à la fin d'une série (examen / entraînement).
 * Charge POST /api/ai-coach/series-report et affiche :
 *  - un bandeau d'encouragement chiffré (pourcentages calculés en SQL),
 *  - les notions maîtrisées / à retravailler (avec lien vers les cours),
 *  - un mini-cours dépliable par erreur.
 */
export default function SeriesReport({ sessionId }) {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);

    const load = useCallback(async () => {
        if (!sessionId) return;
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post('/api/ai-coach/series-report', { session_id: sessionId });
            setData(res.data);
        } catch (e) {
            setError(e.response?.data?.detail || "Le prof est momentanément indisponible, réessaie dans un instant.");
        } finally {
            setLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        load();
    }, [load]);

    const enc = data?.encouragement;
    const report = data?.report;

    const encouragementText = () => {
        if (!enc) return null;
        if (enc.has_history) {
            const up = enc.current_pct >= enc.previous_pct;
            return `${up ? 'Tu progresses !' : 'Garde le rythme !'} La semaine dernière tu étais à ${enc.previous_pct}%, aujourd'hui ${enc.current_pct}% de réussite ${up ? '🎉' : '💪'}`;
        }
        if (enc.current_pct != null) {
            return `Première semaine à ${enc.current_pct}% — continue, tes stats de progression arrivent ! 💪`;
        }
        return "Première série enregistrée — continue, tes stats de progression arrivent ! 💪";
    };

    return (
        <div className="text-left bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-5 md:p-6 space-y-5">
            <div className="flex items-center gap-2">
                <GraduationCap className="h-6 w-6 text-sky-600 dark:text-sky-400" />
                <h3 className="text-xl font-bold text-slate-900 dark:text-white">🎓 Le bilan de ton prof</h3>
            </div>

            {loading ? (
                <div className="py-8 flex flex-col items-center gap-3 text-slate-600 dark:text-slate-300">
                    <Loader2 className="h-7 w-7 animate-spin text-sky-500" />
                    <p>Ton prof analyse ta série…</p>
                </div>
            ) : error ? (
                <div className="py-6 text-center space-y-3">
                    <p className="text-slate-600 dark:text-slate-300">{error}</p>
                    <Button variant="outline" onClick={load}>
                        <RefreshCw className="mr-2 h-4 w-4" /> Réessayer
                    </Button>
                </div>
            ) : report ? (
                <>
                    {/* Encouragement chiffré */}
                    {enc && (
                        <div className="flex items-start gap-3 p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800">
                            <TrendingUp className="h-5 w-5 text-emerald-600 dark:text-emerald-400 mt-0.5 flex-shrink-0" />
                            <p className="font-medium text-emerald-900 dark:text-emerald-100">{encouragementText()}</p>
                        </div>
                    )}

                    {/* Message du prof */}
                    {report.message_prof && (
                        <p className="text-slate-700 dark:text-slate-300 italic">« {report.message_prof} »</p>
                    )}

                    {/* Notions maîtrisées */}
                    {report.notions_maitrisees?.length > 0 && (
                        <section>
                            <h4 className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white mb-2">
                                <CheckCircle2 className="h-4 w-4 text-emerald-500" /> Notions que tu maîtrises
                            </h4>
                            <div className="flex flex-wrap gap-2">
                                {report.notions_maitrisees.map((n, i) => (
                                    <Badge key={i} className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200 hover:bg-emerald-100">
                                        {n}
                                    </Badge>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* Notions à retravailler */}
                    {report.notions_a_retravailler?.length > 0 && (
                        <section>
                            <h4 className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white mb-2">
                                <RotateCcw className="h-4 w-4 text-amber-500" /> À retravailler
                            </h4>
                            <div className="space-y-2">
                                {report.notions_a_retravailler.map((n, i) => (
                                    <div key={i} className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800">
                                        <div className="flex items-center justify-between gap-2 mb-1">
                                            <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200 hover:bg-amber-100">
                                                {n.notion}
                                            </Badge>
                                            {n.cours_recommande && (
                                                <Link to="/courses" className="text-xs inline-flex items-center gap-1 text-sky-600 dark:text-sky-400 hover:underline">
                                                    <BookOpen className="h-3 w-3" /> {n.cours_recommande}
                                                </Link>
                                            )}
                                        </div>
                                        <p className="text-sm text-amber-900/90 dark:text-amber-100/90">{n.conseil}</p>
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* Mini-cours par erreur */}
                    {report.mini_cours?.length > 0 && (
                        <section>
                            <h4 className="font-semibold text-slate-900 dark:text-white mb-2">
                                Le cours rapide sur tes erreurs
                            </h4>
                            <Accordion type="single" collapsible className="space-y-2">
                                {report.mini_cours.map((mc, i) => (
                                    <AccordionItem
                                        key={i}
                                        value={`mc-${i}`}
                                        className="border border-slate-200 dark:border-slate-700 rounded-xl px-4"
                                    >
                                        <AccordionTrigger className="hover:no-underline text-left text-sm font-medium text-slate-900 dark:text-white">
                                            {mc.question_resume}
                                        </AccordionTrigger>
                                        <AccordionContent>
                                            <p className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-line">
                                                {mc.explication_claire}
                                            </p>
                                        </AccordionContent>
                                    </AccordionItem>
                                ))}
                            </Accordion>
                        </section>
                    )}
                </>
            ) : null}
        </div>
    );
}
