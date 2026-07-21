import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { BarChart3, TrendingUp, AlertCircle, CheckCircle, BookOpen, ArrowLeft } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Link } from 'react-router-dom';

// Use CRA proxy (relative paths)

export default function Stats() {
    const [activity, setActivity] = useState([]);
    const [summary, setSummary] = useState(null);
    const [failedQuestions, setFailedQuestions] = useState([]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [sumRes, detailRes] = await Promise.all([
                    axios.get(`/api/stats/summary`),
                    axios.get(`/api/stats/details`)
                ]);
                setSummary(sumRes.data);
                setActivity(detailRes.data?.exams || []);
                
                // Extract failed questions from all exams
                const failed = [];
                const questionsSeen = new Set();
                
                (detailRes.data?.exams || []).forEach(exam => {
                    (exam.questions || []).forEach(q => {
                        if (!q.is_correct && !questionsSeen.has(q.question_id)) {
                            failed.push({
                                ...q,
                                exam_id: exam.id,
                                exam_date: exam.completed_at
                            });
                            questionsSeen.add(q.question_id);
                        }
                    });
                });
                
                setFailedQuestions(failed);
            } catch (e) {
                console.error(e);
            }
        };
        fetchData();
    }, []);

    // Calculate pass rate from last 5 exams
    const passRate = summary?.last_exams 
        ? Math.round((summary.last_exams.filter(e => e?.score >= 83).length / (summary.last_exams.length || 1)) * 100) || 0
        : 0;

    return (
        <div className="min-h-screen pb-10">
            {/* En-tête cohérent + retour accueil */}
            <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 sticky top-0 z-30 p-4">
                <div className="max-w-5xl mx-auto flex items-center gap-3">
                    <Link to="/">
                        <Button variant="ghost" size="icon" aria-label="Retour à l'accueil">
                            <ArrowLeft className="h-5 w-5" />
                        </Button>
                    </Link>
                    <h1 className="text-xl font-heading font-bold text-slate-900 dark:text-white">Vos Statistiques</h1>
                </div>
            </header>

            <div className="max-w-5xl mx-auto p-6 space-y-8">

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-slate-600 dark:text-slate-300">Taux de réussite (récent)</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold text-slate-900 dark:text-white">{passRate}%</div>
                    </CardContent>
                </Card>
                <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-slate-600 dark:text-slate-300">Erreurs Totales</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold text-slate-900 dark:text-white">{summary?.total_errors || 0}</div>
                    </CardContent>
                </Card>
                <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-slate-600 dark:text-slate-300">Meilleure Catégorie</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-lg font-bold text-sky-600 dark:text-sky-400 truncate">{summary?.best_category || '—'}</div>
                    </CardContent>
                </Card>
                <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-slate-600 dark:text-slate-300">À Travailler</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-lg font-bold text-red-600 dark:text-red-400 truncate">{summary?.worst_category || '—'}</div>
                    </CardContent>
                </Card>
            </div>

            {/* Tabs for History and Failed Questions */}
            <Tabs defaultValue="history" className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="history" className="flex items-center gap-2">
                        <TrendingUp className="h-4 w-4" />
                        Historique
                    </TabsTrigger>
                    <TabsTrigger value="to-work-on" className="flex items-center gap-2">
                        <BookOpen className="h-4 w-4" />
                        À Travailler ({failedQuestions.length})
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="history" className="mt-6">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                        {/* History List */}
                        <div className="lg:col-span-2 space-y-4">
                            <h2 className="text-xl font-bold flex items-center text-slate-900 dark:text-white">
                                <TrendingUp className="mr-2 h-5 w-5 text-slate-500 dark:text-slate-400" /> Historique Complet
                            </h2>
                            <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
                                {activity.length > 0 ? (
                                    activity.map((item, idx) => (
                                        <a href={`/exam/${item.id}`} key={item.id} className={`block p-4 hover:bg-slate-50 dark:hover:bg-slate-750 transition-colors ${idx !== activity.length - 1 ? 'border-b border-slate-200 dark:border-slate-700' : ''}`}>
                                            <div className="flex justify-between items-center">
                                            <div className="flex items-center gap-3">
                                                <div className={`p-2 rounded-full ${(item.passed || (item.correct_answers >= Math.ceil((item.total_questions||30)*0.83))) ? 'bg-sky-100 dark:bg-sky-950/30 text-sky-600 dark:text-sky-400' : 'bg-red-100 dark:bg-red-950/30 text-red-600 dark:text-red-400'}`}>
                                                    {(item.passed || (item.correct_answers >= Math.ceil((item.total_questions||30)*0.83))) ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                                                </div>
                                                <div>
                                                    <div className="font-medium text-slate-900 dark:text-white">Examen Blanc</div>
                                                    <div className="text-xs text-slate-600 dark:text-slate-400">{item.completed_at ? new Date(item.completed_at).toLocaleDateString() : '—'} • {item.completed_at ? new Date(item.completed_at).toLocaleTimeString() : ''}</div>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <div className={`font-bold text-lg ${(item.passed || (item.correct_answers >= Math.ceil((item.total_questions||30)*0.83))) ? 'text-sky-600 dark:text-sky-400' : 'text-red-600 dark:text-red-400'}`}>
                                                    {item.correct_answers}/{item.total_questions || 30}
                                                </div>
                                            </div>
                                            </div>
                                        </a>
                                    ))
                                ) : (
                                    <div className="p-8 text-center text-slate-600 dark:text-slate-400">Aucune donnée disponible.</div>
                                )}
                            </div>
                        </div>

                        {/* Simple Visual (Placeholder for Chart) */}
                        <div className="space-y-4">
                            <h2 className="text-xl font-bold flex items-center text-slate-900 dark:text-white">
                                <BarChart3 className="mr-2 h-5 w-5 text-slate-500 dark:text-slate-400" /> Progression
                            </h2>
                            <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                                <CardContent className="p-6 flex flex-col items-center justify-center min-h-[300px] text-center">
                                    <div className="w-full space-y-2">
                                        {summary?.last_exams?.map((exam, i) => (
                                            <div key={i} className="space-y-1">
                                                <div className="flex justify-between text-xs text-slate-600 dark:text-slate-400">
                                                    <span>{exam.completed_at ? new Date(exam.completed_at).toLocaleDateString() : '—'}</span>
                                                    <span>{exam.score ?? '—'}/100</span>
                                                </div>
                                                <div className="h-2 w-full bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                                                    <div 
                                                        className={`h-full rounded-full ${(exam.score ?? 0) >= 83 ? 'bg-sky-500' : 'bg-red-500'}`} 
                                                        style={{ width: `${(exam.score ?? 0)}%` }}
                                                    ></div>
                                                </div>
                                            </div>
                                        ))}
                                        {(!summary?.last_exams || summary.last_exams.length === 0) && (
                                            <p className="text-slate-600 dark:text-slate-400">Pas assez de données pour afficher le graphique.</p>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    </div>
                </TabsContent>

                <TabsContent value="to-work-on" className="mt-6">
                    <div className="space-y-4">
                        <div className="flex justify-between items-center">
                            <h2 className="text-xl font-bold flex items-center text-slate-900 dark:text-white">
                                <BookOpen className="mr-2 h-5 w-5 text-slate-500 dark:text-slate-400" /> Questions à Travailler
                            </h2>
                            {failedQuestions.length > 0 && (
                                <Link to="/training">
                                    <button className="text-sm text-sky-600 dark:text-sky-400 hover:underline font-medium">
                                        Réviser maintenant
                                    </button>
                                </Link>
                            )}
                        </div>
                        
                        {failedQuestions.length > 0 ? (
                            <div className="grid grid-cols-1 gap-4">
                                {failedQuestions.map((q, idx) => (
                                    <Card key={idx} className="bg-white dark:bg-slate-800 border-red-200 dark:border-red-900/30">
                                        <CardContent className="p-4">
                                            <div className="flex items-start gap-3">
                                                <div className="p-2 rounded-full bg-red-100 dark:bg-red-950/30 text-red-600 dark:text-red-400 shrink-0">
                                                    <AlertCircle className="h-4 w-4" />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-start justify-between gap-2 mb-2">
                                                        <h3 className="font-medium text-slate-900 dark:text-white">{q.text}</h3>
                                                        <span className="text-xs px-2 py-1 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 shrink-0">
                                                            {q.category}
                                                        </span>
                                                    </div>
                                                    <div className="text-sm text-slate-600 dark:text-slate-400">
                                                        Échoué le {q.exam_date ? new Date(q.exam_date).toLocaleDateString() : '—'}
                                                    </div>
                                                </div>
                                            </div>
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        ) : (
                            <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                                <CardContent className="p-12 text-center">
                                    <CheckCircle className="h-12 w-12 text-sky-500 mx-auto mb-4" />
                                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
                                        Excellent travail !
                                    </h3>
                                    <p className="text-slate-600 dark:text-slate-400">
                                        Vous n'avez aucune question à retravailler pour le moment.
                                    </p>
                                </CardContent>
                            </Card>
                        )}
                    </div>
                </TabsContent>
            </Tabs>
            </div>
        </div>
    );
}
