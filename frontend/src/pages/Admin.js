import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from '../api/axiosConfig';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Skeleton } from '../components/ui/skeleton';
import { Search, RefreshCw, Trash2, Save, Users } from 'lucide-react';

export default function Admin() {
    const [qText, setQText] = useState('');
    const [qCategory, setQCategory] = useState('Priorités');
    const [qImage, setQImage] = useState('');
    const [qExplanation, setQExplanation] = useState('');
    const [options, setOptions] = useState([
        { text: '', is_correct: true },
        { text: '', is_correct: false },
        { text: '', is_correct: false },
        { text: '', is_correct: false }
    ]);

    const [sName, setSName] = useState('');
    const [sCategory, setSCategory] = useState('Danger');
    const [sDesc, setSDesc] = useState('');
    const [sImage, setSImage] = useState('');

    // Database management state
    const [stats, setStats] = useState({
        total_questions: 0,
        by_category: {},
        database_type: ''
    });
    const [isLoadingStats, setIsLoadingStats] = useState(false);
    const [isGeneratingSynthesis, setIsGeneratingSynthesis] = useState(false);

    // Manage questions state
    const [manageLoading, setManageLoading] = useState(false);
    const [manageOnlyMissing, setManageOnlyMissing] = useState(true);
    const [manageQuestions, setManageQuestions] = useState([]);
    const [manageSearch, setManageSearch] = useState('');
    const [manageOffset, setManageOffset] = useState(0);
    const [manageHasMore, setManageHasMore] = useState(false);

    // Manage signs state
    const [manageSigns, setManageSigns] = useState([]);
    const [manageSignsSearch, setManageSignsSearch] = useState('');
    const [manageSignsLoading, setManageSignsLoading] = useState(false);
    const [manageSignsOnlyMissing, setManageSignsOnlyMissing] = useState(true);
    const [manageSignsOffset, setManageSignsOffset] = useState(0);
    const [manageSignsHasMore, setManageSignsHasMore] = useState(false);

    // Manage courses state
    const [courses, setCourses] = useState([]);
    const [coursesLoading, setCoursesLoading] = useState(false);
    const [editingCourse, setEditingCourse] = useState(null);
    const [courseForm, setCourseForm] = useState({
        title: '',
        description: '',
        content: '',
        order: 0,
        video_url: '',
        pdf_url: '',
        image_url: '',
        category: ''
    });

    // Fetch stats on component mount
    useEffect(() => {
        fetchStats();
        fetchManageQuestions({ reset: true });
        fetchManageSigns({ reset: true });
        fetchCourses();
    }, []);

    const fetchStats = async () => {
        setIsLoadingStats(true);
        try {
            const response = await axios.get('/api/admin/questions/stats');
            setStats(response.data);
        } catch (error) {
            console.error('Error fetching stats:', error);
            toast.error('Error fetching statistics');
        } finally {
            setIsLoadingStats(false);
        }
    };

    const fetchManageQuestions = async ({ reset = false } = {}) => {
        if (reset) {
            setManageLoading(true);
            setManageOffset(0);
        } else {
            setManageLoading(true);
        }
        try {
            const limit = 50;
            const params = { missingOnly: manageOnlyMissing, limit, offset: reset ? 0 : manageOffset };
            const resp = await axios.get('/api/admin/questions', { params });
            const items = resp.data || [];
            setManageQuestions(prev => reset ? items : [...prev, ...items]);
            setManageHasMore(items.length === limit);
            if (!reset) setManageOffset(prev => prev + items.length);
        } catch (error) {
            console.error('Error fetching questions:', error);
            toast.error("Erreur lors du chargement des questions");
        } finally {
            setManageLoading(false);
        }
    };

    const saveExplanation = async (id, explanation) => {
        try {
            await axios.patch(`/api/admin/questions/${id}/explanation`, { explanation });
            toast.success('Explication enregistrée');
            // Update local state
            setManageQuestions(prev => prev.map(q => q.id === id ? { ...q, explanation, has_explanation: !!(explanation && explanation.trim()) } : q));
        } catch (error) {
            toast.error("Erreur lors de l'enregistrement");
        }
    };

    const deleteQuestion = async (id) => {
        if (!window.confirm('Supprimer cette question ?')) return;
        try {
            await axios.delete(`/api/admin/questions/${id}`);
            toast.success('Question supprimée');
            setManageQuestions(prev => prev.filter(q => q.id !== id));
            fetchStats();
        } catch (error) {
            toast.error('Erreur lors de la suppression');
        }
    };

    // Manage signs functions
    const fetchManageSigns = async ({ reset = false } = {}) => {
        if (reset) {
            setManageSignsLoading(true);
            setManageSignsOffset(0);
        } else {
            setManageSignsLoading(true);
        }
        try {
            const limit = 50;
            const params = { missingOnly: manageSignsOnlyMissing, limit, offset: reset ? 0 : manageSignsOffset };
            const resp = await axios.get('/api/admin/signs', { params });
            const items = resp.data || [];
            setManageSigns(prev => reset ? items : [...prev, ...items]);
            setManageSignsHasMore(items.length === limit);
            if (!reset) setManageSignsOffset(prev => prev + items.length);
        } catch (error) {
            console.error('Error fetching signs:', error);
            toast.error("Erreur lors du chargement des panneaux");
        } finally {
            setManageSignsLoading(false);
        }
    };

    const saveSignExplanation = async (id, explanation) => {
        try {
            await axios.patch(`/api/admin/signs/${id}/explanation`, { explanation });
            toast.success('Explication enregistrée');
            // Update local state
            setManageSigns(prev => prev.map(s => s.id === id ? { ...s, explanation, has_explanation: !!(explanation && explanation.trim()) } : s));
        } catch (error) {
            toast.error("Erreur lors de l'enregistrement");
        }
    };

    const deleteSign = async (id) => {
        if (!window.confirm('Supprimer ce panneau ?')) return;
        try {
            await axios.delete(`/api/admin/signs/${id}`);
            toast.success('Panneau supprimé');
            setManageSigns(prev => prev.filter(s => s.id !== id));
        } catch (error) {
            toast.error('Erreur lors de la suppression');
        }
    };

    const filteredManageQuestions = manageQuestions.filter(q => {
        if (!manageSearch.trim()) return true;
        const s = manageSearch.trim().toLowerCase();
        return q.text.toLowerCase().includes(s) || (q.explanation || '').toLowerCase().includes(s);
    });

    const filteredManageSigns = manageSigns.filter(s => {
        if (!manageSignsSearch.trim()) return true;
        const search = manageSignsSearch.trim().toLowerCase();
        return s.name.toLowerCase().includes(search) || 
               s.description.toLowerCase().includes(search) ||
               (s.explanation || '').toLowerCase().includes(search);
    });

    const handleImportQuestions = async () => {
        if (!window.confirm('Import questions from data_v3.json?')) return;
        
        try {
            const response = await axios.post('/api/admin/import-questions', {
                source: 'data_v3',
                force: false
            });
            toast.success(response.data.message);
            fetchStats();
        } catch (error) {
            toast.error('Error importing questions: ' + (error.response?.data?.message || error.message));
        }
    };

    const handleGenerateTrapSynthesis = async () => {
        setIsGeneratingSynthesis(true);
        try {
            await axios.post('/api/admin/trap-questions/synthesis');
            toast.success('Synthèse des questions pièges générée ✅');
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erreur lors de la génération de la synthèse');
        } finally {
            setIsGeneratingSynthesis(false);
        }
    };

    const handleClearDatabase = async () => {
        if (!window.confirm('⚠️  Are you sure you want to delete ALL questions? This cannot be undone!')) return;
        
        try {
            const response = await axios.delete('/api/admin/questions/clear', {
                params: { confirm: true }
            });
            toast.success(response.data.message);
            fetchStats();
        } catch (error) {
            toast.error('Error clearing database: ' + (error.response?.data?.detail || error.message));
        }
    };

    const handleOptionChange = (index, field, value) => {
        const newOptions = [...options];
        newOptions[index][field] = value;
        if (field === 'is_correct' && value === true) {
            // Ensure only one correct
            newOptions.forEach((o, i) => {
                if (i !== index) o.is_correct = false;
            });
        }
        setOptions(newOptions);
    };

    const submitQuestion = async (e) => {
        e.preventDefault();
        try {
            await axios.post('/api/questions', {
                text: qText,
                category: qCategory,
                image_url: qImage || null,
                explanation: qExplanation,
                options: options.map(o => ({
                    text: o.text,
                    is_correct: o.is_correct
                }))
            });
            toast.success("Question ajoutée !");
            setQText('');
            setQExplanation('');
            setQImage('');
        } catch (e) {
            toast.error("Erreur lors de l'ajout");
        }
    };

    const submitSign = async (e) => {
        e.preventDefault();
        try {
            await axios.post('/api/signs', {
                name: sName,
                category: sCategory,
                description: sDesc,
                image_url: sImage
            });
            toast.success("Panneau ajouté !");
            setSName('');
            setSDesc('');
            setSImage('');
        } catch (e) {
            toast.error("Erreur lors de l'ajout");
        }
    };

    // Course management functions
    const fetchCourses = async () => {
        setCoursesLoading(true);
        try {
            const res = await axios.get('/api/courses');
            setCourses(res.data);
        } catch (error) {
            toast.error("Erreur lors du chargement des cours");
        } finally {
            setCoursesLoading(false);
        }
    };

    const handleCourseFormChange = (field, value) => {
        setCourseForm(prev => ({ ...prev, [field]: value }));
    };

    const saveCourse = async (e) => {
        e.preventDefault();
        try {
            if (editingCourse) {
                await axios.patch(`/api/courses/${editingCourse.id}`, courseForm);
                toast.success("Cours mis à jour !");
            } else {
                await axios.post('/api/courses', courseForm);
                toast.success("Cours créé !");
            }
            setCourseForm({
                title: '',
                description: '',
                content: '',
                order: 0,
                video_url: '',
                pdf_url: '',
                image_url: '',
                category: ''
            });
            setEditingCourse(null);
            fetchCourses();
        } catch (error) {
            toast.error("Erreur lors de la sauvegarde du cours");
        }
    };

    const editCourse = (course) => {
        setEditingCourse(course);
        setCourseForm({
            title: course.title || '',
            description: course.description || '',
            content: course.content || '',
            order: course.order || 0,
            video_url: course.video_url || '',
            pdf_url: course.pdf_url || '',
            image_url: course.image_url || '',
            category: course.category || ''
        });
    };

    const deleteCourse = async (courseId) => {
        if (!window.confirm('Êtes-vous sûr de vouloir supprimer ce cours ?')) return;
        try {
            await axios.delete(`/api/courses/${courseId}`);
            toast.success("Cours supprimé !");
            fetchCourses();
        } catch (error) {
            toast.error("Erreur lors de la suppression du cours");
        }
    };

    const cancelEdit = () => {
        setEditingCourse(null);
        setCourseForm({
            title: '',
            description: '',
            content: '',
            order: 0,
            video_url: '',
            pdf_url: '',
            image_url: '',
            category: ''
        });
    };

    return (
        <div className="max-w-4xl mx-auto p-6 min-h-screen">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-8">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Administration (CMS)</h1>
                <Link to="/admin/crm">
                    <Button variant="default" className="gap-2">
                        <Users className="h-4 w-4" /> Ouvrir le CRM (comptes & abonnements)
                    </Button>
                </Link>
            </div>

            <Tabs defaultValue="question">
                <TabsList className="grid w-full grid-cols-6 mb-8">
                    <TabsTrigger value="question">
                        <span className="flex items-center gap-2">Ajouter Question</span>
                    </TabsTrigger>
                    <TabsTrigger value="database">
                        <span className="flex items-center gap-2">Base de données <Badge variant="secondary">{stats.total_questions}</Badge></span>
                    </TabsTrigger>
                    <TabsTrigger value="manage">
                        <span className="flex items-center gap-2">Gérer Questions <Badge variant="outline">{filteredManageQuestions.length}</Badge></span>
                    </TabsTrigger>
                    <TabsTrigger value="manageSigns">
                        <span className="flex items-center gap-2">Gérer Panneaux <Badge variant="outline">{filteredManageSigns.length}</Badge></span>
                    </TabsTrigger>
                    <TabsTrigger value="manageCourses">
                        <span className="flex items-center gap-2">Gérer Cours</span>
                    </TabsTrigger>
                    <TabsTrigger value="sign">
                        <span className="flex items-center gap-2">Ajouter Panneau</span>
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="database">
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                        <CardHeader><CardTitle className="text-slate-900 dark:text-white">📊 Gestion de la base de données</CardTitle></CardHeader>
                        <CardContent className="space-y-6">
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {isLoadingStats ? (
                                    <>
                                        <Skeleton className="h-24 w-full rounded-xl" />
                                        <Skeleton className="h-24 w-full rounded-xl" />
                                        <Skeleton className="h-24 w-full rounded-xl" />
                                    </>
                                ) : (
                                    <>
                                        <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 bg-slate-50 dark:bg-slate-800">
                                            <div className="text-sm text-slate-600 dark:text-slate-300">Total questions</div>
                                            <div className="text-2xl font-bold text-slate-900 dark:text-white">{stats.total_questions}</div>
                                        </div>
                                        <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 bg-slate-50 dark:bg-slate-800">
                                            <div className="text-sm text-slate-600 dark:text-slate-300">Base de données</div>
                                            <div className="text-lg font-semibold text-slate-900 dark:text-white">{stats.database_type}</div>
                                        </div>
                                        <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 bg-slate-50 dark:bg-slate-800">
                                            <div className="text-sm text-slate-600 dark:text-slate-300 mb-2">Catégories</div>
                                            <div className="flex flex-wrap gap-2">
                                                {Object.entries(stats.by_category || {}).map(([category, count]) => (
                                                    <Badge key={category} variant="secondary">{category}: {count}</Badge>
                                                ))}
                                            </div>
                                        </div>
                                    </>
                                )}
                            </div>
                            
                            <div className="space-y-3">
                                <Button 
                                    onClick={handleImportQuestions} 
                                    className="w-full"
                                    variant="default"
                                >
                                    📥 Importer les questions depuis data_v3.json
                                </Button>
                                <Button 
                                    onClick={fetchStats} 
                                    className="w-full"
                                    variant="outline"
                                >
                                    🔄 Actualiser les statistiques
                                </Button>
                                <Button
                                    onClick={handleGenerateTrapSynthesis}
                                    className="w-full"
                                    variant="secondary"
                                    disabled={isGeneratingSynthesis}
                                >
                                    {isGeneratingSynthesis ? '⏳ Génération…' : '🧠 Générer la synthèse des questions pièges (IA)'}
                                </Button>
                                <Button
                                    onClick={handleClearDatabase}
                                    className="w-full"
                                    variant="destructive"
                                >
                                    🗑️ Effacer toutes les questions
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="manage">
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                        <CardHeader><CardTitle className="text-slate-900 dark:text-white">🛠️ Gérer les questions</CardTitle></CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
                                <div className="relative flex-1">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 dark:text-slate-400" />
                                    <Input
                                        value={manageSearch}
                                        onChange={(e) => setManageSearch(e.target.value)}
                                        placeholder="Rechercher une question ou une explication"
                                        className="pl-9 bg-white dark:bg-slate-700 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white"
                                    />
                                </div>
                                <div className="flex items-center gap-2">
                                    <Switch checked={manageOnlyMissing} onCheckedChange={(v) => { setManageOnlyMissing(v); fetchManageQuestions({ reset: true }); }} />
                                    <span className="text-sm text-slate-900 dark:text-white">Seulement sans explication</span>
                                </div>
                                <Button variant="outline" onClick={() => fetchManageQuestions({ reset: true })}>
                                    <RefreshCw className="h-4 w-4 mr-2" /> Actualiser
                                </Button>
                            </div>

                            {manageLoading && manageQuestions.length === 0 ? (
                                <div className="grid gap-3">
                                    <Skeleton className="h-24 w-full rounded-xl" />
                                    <Skeleton className="h-24 w-full rounded-xl" />
                                    <Skeleton className="h-24 w-full rounded-xl" />
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {filteredManageQuestions.length === 0 ? (
                                        <p className="text-sm text-slate-600 dark:text-slate-400">Aucune question à afficher.</p>
                                    ) : (
                                        filteredManageQuestions.map((q) => (
                                            <div key={q.id} className="border border-slate-200 dark:border-slate-700 rounded-lg p-4 space-y-3 bg-slate-50 dark:bg-slate-800">
                                                <div className="flex items-start justify-between gap-4">
                                                    <div>
                                                        <p className="font-medium text-slate-900 dark:text-white">{q.text}</p>
                                                        <div className="flex items-center gap-2 mt-1">
                                                            <Badge variant="outline" className="border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">{q.category}</Badge>
                                                            {q.has_explanation ? (
                                                                <Badge variant="secondary" className="bg-emerald-100 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300">Explication OK</Badge>
                                                            ) : (
                                                                <Badge variant="destructive" className="bg-red-100 dark:bg-red-950/30 text-red-700 dark:text-red-300">Explication manquante</Badge>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <Button variant="destructive" onClick={() => deleteQuestion(q.id)}>
                                                        <Trash2 className="h-4 w-4 mr-2" /> Supprimer
                                                    </Button>
                                                </div>
                                                <div>
                                                    <label className="text-sm font-medium text-slate-900 dark:text-white">Explication</label>
                                                    <Textarea
                                                        value={q.explanation || ''}
                                                        onChange={(e) => setManageQuestions(prev => prev.map(item => item.id === q.id ? { ...item, explanation: e.target.value } : item))}
                                                        placeholder="Ajoutez une explication claire et concise"
                                                        className="bg-white dark:bg-slate-700 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white"
                                                    />
                                                </div>
                                                <div className="flex justify-end">
                                                    <Button onClick={() => saveExplanation(q.id, q.explanation || '')}>
                                                        <Save className="h-4 w-4 mr-2" /> Enregistrer l'explication
                                                    </Button>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                    {manageHasMore && (
                                        <div className="flex justify-center">
                                            <Button variant="outline" onClick={() => fetchManageQuestions()}>Charger plus</Button>
                                        </div>
                                    )}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="manageSigns">
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                        <CardHeader><CardTitle className="text-slate-900 dark:text-white">🛠️ Gérer les panneaux</CardTitle></CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
                                <div className="relative flex-1">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 dark:text-slate-400" />
                                    <Input
                                        value={manageSignsSearch}
                                        onChange={(e) => setManageSignsSearch(e.target.value)}
                                        placeholder="Rechercher un panneau ou une explication"
                                        className="pl-9 bg-white dark:bg-slate-700 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white"
                                    />
                                </div>
                                <div className="flex items-center gap-2">
                                    <Switch checked={manageSignsOnlyMissing} onCheckedChange={(v) => { setManageSignsOnlyMissing(v); fetchManageSigns({ reset: true }); }} />
                                    <span className="text-sm text-slate-900 dark:text-white">Seulement sans explication</span>
                                </div>
                                <Button variant="outline" onClick={() => fetchManageSigns({ reset: true })}>
                                    <RefreshCw className="h-4 w-4 mr-2" /> Actualiser
                                </Button>
                            </div>

                            {manageSignsLoading && manageSigns.length === 0 ? (
                                <div className="grid gap-3">
                                    <Skeleton className="h-24 w-full rounded-xl" />
                                    <Skeleton className="h-24 w-full rounded-xl" />
                                    <Skeleton className="h-24 w-full rounded-xl" />
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {filteredManageSigns.length === 0 ? (
                                        <p className="text-sm text-slate-600 dark:text-slate-400">Aucun panneau à afficher.</p>
                                    ) : (
                                        filteredManageSigns.map((s) => (
                                            <div key={s.id} className="border border-slate-200 dark:border-slate-700 rounded-lg p-4 space-y-3 bg-slate-50 dark:bg-slate-800">
                                                <div className="flex items-start justify-between gap-4">
                                                    <div className="flex-1">
                                                        <div className="flex items-center gap-3 mb-2">
                                                            {s.image_url && (
                                                                <img src={s.image_url} alt={s.name} className="w-16 h-16 object-contain border border-slate-300 dark:border-slate-600 rounded" />
                                                            )}
                                                            <div>
                                                                <p className="font-medium text-slate-900 dark:text-white">{s.name}</p>
                                                                <p className="text-sm text-slate-600 dark:text-slate-400">{s.description}</p>
                                                            </div>
                                                        </div>
                                                        <div className="flex items-center gap-2 mt-1">
                                                            <Badge variant="outline" className="border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">{s.category}</Badge>
                                                            <Badge variant="outline" className="border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">#{s.number}</Badge>
                                                            {s.has_explanation ? (
                                                                <Badge variant="secondary" className="bg-emerald-100 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300">Explication OK</Badge>
                                                            ) : (
                                                                <Badge variant="destructive" className="bg-red-100 dark:bg-red-950/30 text-red-700 dark:text-red-300">Explication manquante</Badge>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <Button variant="destructive" onClick={() => deleteSign(s.id)}>
                                                        <Trash2 className="h-4 w-4 mr-2" /> Supprimer
                                                    </Button>
                                                </div>
                                                <div>
                                                    <label className="text-sm font-medium text-slate-900 dark:text-white">Explication</label>
                                                    <Textarea
                                                        value={s.explanation || ''}
                                                        onChange={(e) => setManageSigns(prev => prev.map(item => item.id === s.id ? { ...item, explanation: e.target.value } : item))}
                                                        placeholder="Ajoutez une explication claire et concise"
                                                        className="bg-white dark:bg-slate-700 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white"
                                                    />
                                                </div>
                                                <div className="flex justify-end">
                                                    <Button onClick={() => saveSignExplanation(s.id, s.explanation || '')}>
                                                        <Save className="h-4 w-4 mr-2" /> Enregistrer l'explication
                                                    </Button>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                    {manageSignsHasMore && (
                                        <div className="flex justify-center">
                                            <Button variant="outline" onClick={() => fetchManageSigns()}>Charger plus</Button>
                                        </div>
                                    )}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="question">
                    <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                        <CardHeader><CardTitle className="text-slate-900 dark:text-white">Nouvelle Question</CardTitle></CardHeader>
                        <CardContent>
                            <form onSubmit={submitQuestion} className="space-y-4">
                                <div>
                                    <label className="text-sm font-medium text-slate-900 dark:text-white">Énoncé</label>
                                    <Textarea value={qText} onChange={e => setQText(e.target.value)} required className="bg-white dark:bg-slate-700 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white" />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-sm font-medium text-slate-900 dark:text-white">Catégorie</label>
                                        <Select value={qCategory} onValueChange={setQCategory}>
                                            <SelectTrigger><SelectValue /></SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="Priorités">Priorités</SelectItem>
                                                <SelectItem value="Croisements">Croisements</SelectItem>
                                                <SelectItem value="Signalisations">Signalisations</SelectItem>
                                                <SelectItem value="Mécanique">Mécanique</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div>
                                        <label className="text-sm font-medium text-slate-900 dark:text-white">Image URL (Optionnel)</label>
                                        <Input value={qImage} onChange={e => setQImage(e.target.value)} placeholder="https://..." className="bg-white dark:bg-slate-700 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white" />
                                    </div>
                                </div>

                                <div className="space-y-3 border border-slate-200 dark:border-slate-700 p-4 rounded-lg bg-slate-50 dark:bg-slate-800">
                                    <label className="text-sm font-medium text-slate-900 dark:text-white">Réponses (Cochez la bonne)</label>
                                    {options.map((opt, idx) => (
                                        <div key={idx} className="flex items-center gap-3">
                                            <input 
                                                type="radio" 
                                                name="correct" 
                                                checked={opt.is_correct} 
                                                onChange={() => handleOptionChange(idx, 'is_correct', true)}
                                                className="w-4 h-4"
                                            />
                                            <Input 
                                                value={opt.text} 
                                                onChange={e => handleOptionChange(idx, 'text', e.target.value)} 
                                                placeholder={`Réponse ${idx + 1}`} 
                                                required 
                                            />
                                        </div>
                                    ))}
                                </div>

                                <div>
                                    <label className="text-sm font-medium text-slate-900 dark:text-white">Explication</label>
                                    <Textarea value={qExplanation} onChange={e => setQExplanation(e.target.value)} required className="bg-white dark:bg-slate-700 border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white" />
                                </div>

                                <Button type="submit" className="w-full">Enregistrer la question</Button>
                            </form>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="manageCourses">
                    <Card>
                        <CardHeader>
                            <CardTitle>Gérer les Cours</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            {/* Course Form */}
                            <form onSubmit={saveCourse} className="space-y-4 p-4 border rounded-lg bg-slate-50 dark:bg-slate-800">
                                <h3 className="font-bold text-lg">{editingCourse ? 'Modifier le cours' : 'Nouveau cours'}</h3>
                                
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-sm font-medium">Titre *</label>
                                        <Input 
                                            value={courseForm.title} 
                                            onChange={e => handleCourseFormChange('title', e.target.value)} 
                                            required 
                                        />
                                    </div>
                                    <div>
                                        <label className="text-sm font-medium">Ordre</label>
                                        <Input 
                                            type="number"
                                            value={courseForm.order} 
                                            onChange={e => handleCourseFormChange('order', parseInt(e.target.value) || 0)} 
                                        />
                                    </div>
                                </div>

                                <div>
                                    <label className="text-sm font-medium">Description</label>
                                    <Textarea 
                                        value={courseForm.description} 
                                        onChange={e => handleCourseFormChange('description', e.target.value)}
                                        rows={2}
                                    />
                                </div>

                                <div>
                                    <label className="text-sm font-medium">Contenu (HTML)</label>
                                    <Textarea 
                                        value={courseForm.content} 
                                        onChange={e => handleCourseFormChange('content', e.target.value)}
                                        rows={4}
                                        placeholder="<p>Contenu du cours en HTML...</p>"
                                    />
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-sm font-medium">URL Vidéo</label>
                                        <Input 
                                            value={courseForm.video_url} 
                                            onChange={e => handleCourseFormChange('video_url', e.target.value)}
                                            placeholder="https://youtube.com/embed/..."
                                        />
                                    </div>
                                    <div>
                                        <label className="text-sm font-medium">URL PDF</label>
                                        <Input 
                                            value={courseForm.pdf_url} 
                                            onChange={e => handleCourseFormChange('pdf_url', e.target.value)}
                                            placeholder="https://..."
                                        />
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-sm font-medium">URL Image</label>
                                        <Input 
                                            value={courseForm.image_url} 
                                            onChange={e => handleCourseFormChange('image_url', e.target.value)}
                                            placeholder="https://..."
                                        />
                                    </div>
                                    <div>
                                        <label className="text-sm font-medium">Catégorie</label>
                                        <Input 
                                            value={courseForm.category} 
                                            onChange={e => handleCourseFormChange('category', e.target.value)}
                                            placeholder="Priorités, Signalisation..."
                                        />
                                    </div>
                                </div>

                                <div className="flex gap-2">
                                    <Button type="submit" className="flex-1">
                                        <Save className="mr-2 h-4 w-4" />
                                        {editingCourse ? 'Mettre à jour' : 'Créer le cours'}
                                    </Button>
                                    {editingCourse && (
                                        <Button type="button" variant="outline" onClick={cancelEdit}>
                                            Annuler
                                        </Button>
                                    )}
                                </div>
                            </form>

                            {/* Courses List */}
                            <div className="space-y-3">
                                <h3 className="font-bold text-lg">Cours existants ({courses.length})</h3>
                                {coursesLoading ? (
                                    <div>Chargement...</div>
                                ) : courses.length === 0 ? (
                                    <div className="text-center p-8 text-slate-600 dark:text-slate-400">Aucun cours disponible</div>
                                ) : (
                                    courses.map(course => (
                                        <div 
                                            key={course.id} 
                                            className="p-4 border rounded-lg bg-white dark:bg-slate-800 flex justify-between items-start"
                                        >
                                            <div className="flex-1">
                                                <div className="font-bold">{course.title}</div>
                                                <div className="text-sm text-slate-600 dark:text-slate-400">
                                                    Ordre: {course.order} | Catégorie: {course.category || '—'}
                                                </div>
                                                {course.description && (
                                                    <div className="text-sm mt-1">{course.description}</div>
                                                )}
                                            </div>
                                            <div className="flex gap-2">
                                                <Button 
                                                    size="sm" 
                                                    variant="outline" 
                                                    onClick={() => editCourse(course)}
                                                >
                                                    Modifier
                                                </Button>
                                                <Button 
                                                    size="sm" 
                                                    variant="destructive" 
                                                    onClick={() => deleteCourse(course.id)}
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="sign">
                    <Card>
                        <CardHeader><CardTitle>Nouveau Panneau</CardTitle></CardHeader>
                        <CardContent>
                            <form onSubmit={submitSign} className="space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-sm font-medium">Nom du panneau</label>
                                        <Input value={sName} onChange={e => setSName(e.target.value)} required />
                                    </div>
                                    <div>
                                        <label className="text-sm font-medium">Catégorie</label>
                                        <Input value={sCategory} onChange={e => setSCategory(e.target.value)} placeholder="ex: Danger, Interdiction" required />
                                    </div>
                                </div>
                                <div>
                                    <label className="text-sm font-medium">Image URL</label>
                                    <Input value={sImage} onChange={e => setSImage(e.target.value)} placeholder="https://..." required />
                                </div>
                                <div>
                                    <label className="text-sm font-medium">Description</label>
                                    <Textarea value={sDesc} onChange={e => setSDesc(e.target.value)} required />
                                </div>
                                <Button type="submit" className="w-full">Enregistrer le panneau</Button>
                            </form>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}
