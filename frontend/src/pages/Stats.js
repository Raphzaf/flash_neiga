import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { BarChart3, TrendingUp, AlertCircle, CheckCircle } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function Stats() {
    const [activity, setActivity] = useState([]);
    const [summary, setSummary] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [sumRes, actRes] = await Promise.all([
                    axios.get(`${BACKEND_URL}/api/stats/summary`),
                    axios.get(`${BACKEND_URL}/api/stats/activity`)
                ]);
                setSummary(sumRes.data);
                setActivity(actRes.data);
            } catch (e) {
                console.error(e);
            }
        };
        fetchData();
    }, []);

    // Calculate pass rate from last 5 exams
    const passRate = summary?.recent_exams 
        ? Math.round((summary.recent_exams.filter(e => e.score >= 25).length / summary.recent_exams.length) * 100) || 0
        : 0;

    return (
        <div className="max-w-5xl mx-auto p-6 min-h-screen space-y-8">
            <h1 className="text-3xl font-heading font-bold">Vos Statistiques</h1>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Taux de réussite (récent)</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold">{passRate}%</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Erreurs Totales</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold">{summary?.total_errors || 0}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">Meilleure Catégorie</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-lg font-bold text-emerald-600 truncate">{summary?.best_category}</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">À Travailler</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-lg font-bold text-red-600 truncate">{summary?.worst_category}</div>
                    </CardContent>
                </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* History List */}
                <div className="lg:col-span-2 space-y-4">
                    <h2 className="text-xl font-bold flex items-center">
                        <TrendingUp className="mr-2 h-5 w-5" /> Historique Complet
                    </h2>
                    <div className="bg-white dark:bg-slate-900 rounded-xl border shadow-sm overflow-hidden">
                        {activity.length > 0 ? (
                            activity.map((item, idx) => (
                                <div key={item.id} className={`p-4 flex justify-between items-center ${idx !== activity.length - 1 ? 'border-b' : ''}`}>
                                    <div className="flex items-center gap-3">
                                        <div className={`p-2 rounded-full ${item.score >= 25 ? 'bg-emerald-100 text-emerald-600' : 'bg-red-100 text-red-600'}`}>
                                            {item.score >= 25 ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                                        </div>
                                        <div>
                                            <div className="font-medium">Examen Blanc</div>
                                            <div className="text-xs text-muted-foreground">{new Date(item.date).toLocaleDateString()} • {new Date(item.date).toLocaleTimeString()}</div>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        {item.status === 'completed' ? (
                                            <div className={`font-bold text-lg ${item.score >= 25 ? 'text-emerald-600' : 'text-red-600'}`}>
                                                {item.score}/30
                                            </div>
                                        ) : (
                                            <span className="text-xs px-2 py-1 bg-slate-100 rounded-full text-slate-600">Abandonné</span>
                                        )}
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="p-8 text-center text-muted-foreground">Aucune donnée disponible.</div>
                        )}
                    </div>
                </div>

                {/* Simple Visual (Placeholder for Chart) */}
                <div className="space-y-4">
                    <h2 className="text-xl font-bold flex items-center">
                        <BarChart3 className="mr-2 h-5 w-5" /> Progression
                    </h2>
                    <Card>
                        <CardContent className="p-6 flex flex-col items-center justify-center min-h-[300px] text-center">
                            <div className="w-full space-y-2">
                                {summary?.recent_exams?.map((exam, i) => (
                                    <div key={i} className="space-y-1">
                                        <div className="flex justify-between text-xs text-muted-foreground">
                                            <span>{new Date(exam.date).toLocaleDateString()}</span>
                                            <span>{exam.score}/30</span>
                                        </div>
                                        <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                                            <div 
                                                className={`h-full rounded-full ${exam.score >= 25 ? 'bg-emerald-500' : 'bg-red-500'}`} 
                                                style={{ width: `${(exam.score / 30) * 100}%` }}
                                            ></div>
                                        </div>
                                    </div>
                                ))}
                                {(!summary?.recent_exams || summary.recent_exams.length === 0) && (
                                    <p className="text-muted-foreground">Pas assez de données pour afficher le graphique.</p>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
