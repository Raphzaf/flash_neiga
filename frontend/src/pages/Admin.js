import React, { useState, useEffect } from 'react';
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
import { Search, RefreshCw, Trash2, Save } from 'lucide-react';

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

    // Manage questions state
    const [manageLoading, setManageLoading] = useState(false);
    const [manageOnlyMissing, setManageOnlyMissing] = useState(true);
    const [manageQuestions, setManageQuestions] = useState([]);
    const [manageSearch, setManageSearch] = useState('');
    const [manageOffset, setManageOffset] = useState(0);
    const [manageHasMore, setManageHasMore] = useState(false);

    // Fetch stats on component mount
    useEffect(() => {
        fetchStats();
        fetchManageQuestions({ reset: true });
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

    const filteredManageQuestions = manageQuestions.filter(q => {
        if (!manageSearch.trim()) return true;
        const s = manageSearch.trim().toLowerCase();
        return q.text.toLowerCase().includes(s) || (q.explanation || '').toLowerCase().includes(s);
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

    return (
        <div className="max-w-4xl mx-auto p-6 min-h-screen">
            <h1 className="text-3xl font-bold mb-8">Administration (CMS)</h1>

            <Tabs defaultValue="question">
                <TabsList className="grid w-full grid-cols-4 mb-8">
                    <TabsTrigger value="question">
                        <span className="flex items-center gap-2">Ajouter Question</span>
                    </TabsTrigger>
                    <TabsTrigger value="database">
                        <span className="flex items-center gap-2">Base de données <Badge variant="secondary">{stats.total_questions}</Badge></span>
                    </TabsTrigger>
                    <TabsTrigger value="manage">
                        <span className="flex items-center gap-2">Gérer Questions <Badge variant="outline">{filteredManageQuestions.length}</Badge></span>
                    </TabsTrigger>
                    <TabsTrigger value="sign">
                        <span className="flex items-center gap-2">Ajouter Panneau</span>
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="database">
                    <Card>
                        <CardHeader><CardTitle>📊 Gestion de la base de données</CardTitle></CardHeader>
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
                                        <div className="rounded-xl border p-4 bg-slate-50 dark:bg-slate-900">
                                            <div className="text-sm text-muted-foreground">Total questions</div>
                                            <div className="text-2xl font-bold">{stats.total_questions}</div>
                                        </div>
                                        <div className="rounded-xl border p-4 bg-slate-50 dark:bg-slate-900">
                                            <div className="text-sm text-muted-foreground">Base de données</div>
                                            <div className="text-lg font-semibold">{stats.database_type}</div>
                                        </div>
                                        <div className="rounded-xl border p-4 bg-slate-50 dark:bg-slate-900">
                                            <div className="text-sm text-muted-foreground mb-2">Catégories</div>
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
                    <Card>
                        <CardHeader><CardTitle>🛠️ Gérer les questions</CardTitle></CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
                                <div className="relative flex-1">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                                    <Input
                                        value={manageSearch}
                                        onChange={(e) => setManageSearch(e.target.value)}
                                        placeholder="Rechercher une question ou une explication"
                                        className="pl-9"
                                    />
                                </div>
                                <div className="flex items-center gap-2">
                                    <Switch checked={manageOnlyMissing} onCheckedChange={(v) => { setManageOnlyMissing(v); fetchManageQuestions({ reset: true }); }} />
                                    <span className="text-sm">Seulement sans explication</span>
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
                                        <p className="text-sm text-muted-foreground">Aucune question à afficher.</p>
                                    ) : (
                                        filteredManageQuestions.map((q) => (
                                            <div key={q.id} className="border rounded-lg p-4 space-y-3 bg-slate-50 dark:bg-slate-900">
                                                <div className="flex items-start justify-between gap-4">
                                                    <div>
                                                        <p className="font-medium">{q.text}</p>
                                                        <div className="flex items-center gap-2 mt-1">
                                                            <Badge variant="outline">{q.category}</Badge>
                                                            {q.has_explanation ? (
                                                                <Badge variant="secondary">Explication OK</Badge>
                                                            ) : (
                                                                <Badge variant="destructive">Explication manquante</Badge>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <Button variant="destructive" onClick={() => deleteQuestion(q.id)}>
                                                        <Trash2 className="h-4 w-4 mr-2" /> Supprimer
                                                    </Button>
                                                </div>
                                                <div>
                                                    <label className="text-sm font-medium">Explication</label>
                                                    <Textarea
                                                        value={q.explanation || ''}
                                                        onChange={(e) => setManageQuestions(prev => prev.map(item => item.id === q.id ? { ...item, explanation: e.target.value } : item))}
                                                        placeholder="Ajoutez une explication claire et concise"
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

                <TabsContent value="question">
                    <Card>
                        <CardHeader><CardTitle>Nouvelle Question</CardTitle></CardHeader>
                        <CardContent>
                            <form onSubmit={submitQuestion} className="space-y-4">
                                <div>
                                    <label className="text-sm font-medium">Énoncé</label>
                                    <Textarea value={qText} onChange={e => setQText(e.target.value)} required />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-sm font-medium">Catégorie</label>
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
                                        <label className="text-sm font-medium">Image URL (Optionnel)</label>
                                        <Input value={qImage} onChange={e => setQImage(e.target.value)} placeholder="https://..." />
                                    </div>
                                </div>

                                <div className="space-y-3 border p-4 rounded-lg bg-slate-50 dark:bg-slate-900">
                                    <label className="text-sm font-medium">Réponses (Cochez la bonne)</label>
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
                                    <label className="text-sm font-medium">Explication</label>
                                    <Textarea value={qExplanation} onChange={e => setQExplanation(e.target.value)} required />
                                </div>

                                <Button type="submit" className="w-full">Enregistrer la question</Button>
                            </form>
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
