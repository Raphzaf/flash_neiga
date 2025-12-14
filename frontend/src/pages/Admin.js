import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';

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

    // Fetch stats on component mount
    useEffect(() => {
        fetchStats();
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

            <Tabs defaultValue="database">
                <TabsList className="grid w-full grid-cols-3 mb-8">
                    <TabsTrigger value="database">Base de données</TabsTrigger>
                    <TabsTrigger value="question">Ajouter Question</TabsTrigger>
                    <TabsTrigger value="sign">Ajouter Panneau</TabsTrigger>
                </TabsList>

                <TabsContent value="database">
                    <Card>
                        <CardHeader><CardTitle>📊 Gestion de la base de données</CardTitle></CardHeader>
                        <CardContent className="space-y-6">
                            <div className="border p-4 rounded-lg bg-slate-50 dark:bg-slate-900">
                                <h3 className="text-lg font-semibold mb-4">Statistiques des questions</h3>
                                {isLoadingStats ? (
                                    <p>Chargement...</p>
                                ) : (
                                    <>
                                        <div className="space-y-2">
                                            <p><strong>Total de questions:</strong> {stats.total_questions}</p>
                                            <p><strong>Base de données:</strong> {stats.database_type}</p>
                                        </div>
                                        
                                        {Object.keys(stats.by_category).length > 0 && (
                                            <div className="mt-4">
                                                <h4 className="font-medium mb-2">Par catégorie:</h4>
                                                <ul className="space-y-1 pl-4">
                                                    {Object.entries(stats.by_category).map(([category, count]) => (
                                                        <li key={category}>
                                                            <strong>{category}:</strong> {count} questions
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}
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
