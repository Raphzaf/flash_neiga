import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Play, BookOpen, AlertTriangle, BarChart3, History, LogOut, User } from 'lucide-react';
import axios from 'axios';

export default function Dashboard() {
    const { user, logout } = useAuth();
    const [stats, setStats] = useState(null);
    const [recent, setRecent] = useState([]);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const [sumRes, detailsRes] = await Promise.all([
                    axios.get(`/api/stats/summary`),
                    axios.get(`/api/stats/details`)
                ]);
                setStats(sumRes.data);
                setRecent((detailsRes.data?.exams || []).slice(0, 6));
            } catch (e) {
                console.error("Failed to fetch stats");
            }
        };
        fetchStats();
    }, []);

    return (
        <div className="min-h-screen pb-20 md:pb-0">
            {/* Header */}
            <header className="bg-white dark:bg-slate-900 border-b sticky top-0 z-30 p-4">
                <div className="max-w-5xl mx-auto flex justify-between items-center">
                    <h1 className="text-2xl font-heading font-bold text-primary">Flash Neiga</h1>
                    <div className="flex items-center gap-4">
                        <span className="hidden md:inline-block font-medium text-sm">{user?.full_name}</span>
                        <Button variant="ghost" size="icon" onClick={logout} data-testid="logout-btn">
                            <LogOut className="h-5 w-5" />
                        </Button>
                    </div>
                </div>
            </header>

            <main className="max-w-5xl mx-auto p-4 space-y-8 mt-6">
                
                {/* Welcome Section */}
                <div className="relative rounded-2xl overflow-hidden bg-indigo-900 text-white p-8 md:p-12 shadow-xl">
                    <div className="absolute inset-0 bg-gradient-to-r from-indigo-600 to-purple-600 opacity-90"></div>
                    <div className="relative z-10">
                        <h2 className="text-3xl md:text-4xl font-bold mb-2">Prêt à prendre la route ?</h2>
                        <p className="text-indigo-100 mb-6 max-w-xl">Entraînez-vous, suivez vos progrès et obtenez votre code de la route avec Flash Neiga.</p>
                        <div className="flex flex-col sm:flex-row gap-3">
                            <Link to="/exam">
                                <Button size="lg" className="bg-white text-indigo-600 hover:bg-indigo-50 font-bold rounded-full px-8 shadow-lg transition-transform hover:scale-105" data-testid="start-exam-hero-btn">
                                    <Play className="mr-2 h-5 w-5" /> Lancer un Examen
                                </Button>
                            </Link>
                        </div>
                    </div>
                </div>

                {/* Removed pricing quick link and register CTA for base dashboard */}

                {/* Main Actions Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
                    <Link to="/training" className="group">
                        <Card className="h-full hover:border-primary/50 transition-all hover:shadow-md cursor-pointer" data-testid="training-card">
                            <CardHeader>
                                <CardTitle className="flex items-center text-lg">
                                    <div className="p-2 rounded-lg bg-emerald-100 text-emerald-600 mr-3 group-hover:scale-110 transition-transform">
                                        <BookOpen className="h-6 w-6" />
                                    </div>
                                    Entraînement
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <p className="text-sm text-muted-foreground">Révisez par thèmes sans limite de temps. Feedback immédiat.</p>
                            </CardContent>
                        </Card>
                    </Link>

                    <Link to="/signs" className="group">
                        <Card className="h-full hover:border-primary/50 transition-all hover:shadow-md cursor-pointer" data-testid="signs-card">
                            <CardHeader>
                                <CardTitle className="flex items-center text-lg">
                                    <div className="p-2 rounded-lg bg-amber-100 text-amber-600 mr-3 group-hover:scale-110 transition-transform">
                                        <AlertTriangle className="h-6 w-6" />
                                    </div>
                                    Panneaux
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <p className="text-sm text-muted-foreground">Consultez la bibliothèque complète des panneaux de signalisation.</p>
                            </CardContent>
                        </Card>
                    </Link>

                    <Link to="/stats" className="group">
                        <Card className="h-full hover:border-primary/50 transition-all hover:shadow-md cursor-pointer" data-testid="stats-card">
                            <CardHeader>
                                <CardTitle className="flex items-center text-lg">
                                    <div className="p-2 rounded-lg bg-purple-100 text-purple-600 mr-3 group-hover:scale-110 transition-transform">
                                        <BarChart3 className="h-6 w-6" />
                                    </div>
                                    Statistiques
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="flex justify-between items-center">
                                    <div className="text-sm text-muted-foreground">Erreurs totales</div>
                                    <div className="font-bold text-xl">{stats?.total_errors ?? 0}</div>
                                </div>
                                <div className="flex justify-between items-center">
                                    <div className="text-sm text-muted-foreground">Meilleure catégorie</div>
                                    <div className="font-medium truncate max-w-[140px]">{stats?.best_category ?? '—'}</div>
                                </div>
                                <div className="flex justify-between items-center">
                                    <div className="text-sm text-muted-foreground">Pire catégorie</div>
                                    <div className="font-medium truncate max-w-[140px]">{stats?.worst_category ?? '—'}</div>
                                </div>
                                <div className="flex justify-between items-center">
                                    <div className="text-sm text-muted-foreground">Derniers examens</div>
                                    <div className="font-medium">{stats?.last_exams?.length ?? 0}/5</div>
                                </div>
                                <div className="text-xs text-primary/80">Cliquez pour voir les statistiques détaillées</div>
                            </CardContent>
                        </Card>
                    </Link>
                </div>

                {/* Recent Activity */}
                <section>
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-xl font-heading font-bold flex items-center">
                            <History className="mr-2 h-5 w-5 text-muted-foreground" /> Activité Récente
                        </h3>
                        <Link to="/stats" className="text-sm text-primary font-medium hover:underline">Voir tout</Link>
                    </div>
                    
                    <div className="space-y-3">
                        {recent.length > 0 ? (
                            recent.map((exam) => (
                                <Link to={`/exam/${exam.id}`} key={exam.id} className="block">
                                    <div className="bg-white dark:bg-slate-900 border rounded-xl p-4 flex justify-between items-center hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                                        <div>
                                            <div className="font-bold">Examen Blanc</div>
                                            <div className="text-xs text-muted-foreground">{exam.completed_at ? new Date(exam.completed_at).toLocaleDateString() : '—'} à {exam.completed_at ? new Date(exam.completed_at).toLocaleTimeString() : ''}</div>
                                        </div>
                                        <div className={`text-lg font-bold ${(exam.passed || (exam.correct_answers >= Math.ceil((exam.total_questions||30)*0.83))) ? 'text-emerald-600' : 'text-red-500'}`}>
                                            {exam.correct_answers}/{exam.total_questions || 30}
                                        </div>
                                    </div>
                                </Link>
                            ))
                        ) : (
                            <div className="text-center p-8 border-2 border-dashed rounded-xl text-muted-foreground">
                                Pas encore d'activité. Lancez votre premier examen !
                            </div>
                        )}
                    </div>
                </section>
                
                {/* Admin Link (Temporary for MVP to access admin easily) */}
                <div className="mt-12 text-center">
                    <Link to="/admin">
                        <Button variant="outline" size="sm" className="text-xs text-muted-foreground">Accès Admin (Démo)</Button>
                    </Link>
                </div>

            </main>
        </div>
    );
}
