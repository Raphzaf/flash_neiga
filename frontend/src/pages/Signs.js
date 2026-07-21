import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Search, Triangle, Circle, Octagon, Square, ArrowLeft } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';

// Map sign categories to shapes (based on Israeli road signs)
const getSignShape = (category) => {
    if (category.toLowerCase().includes('avertissement') || category.toLowerCase().includes('warning')) {
        return { icon: Triangle, label: 'Triangle (Avertissement)', color: 'text-red-500' };
    } else if (category.toLowerCase().includes('interdiction') || category.toLowerCase().includes('prohibition')) {
        return { icon: Circle, label: 'Rond rouge (Interdiction)', color: 'text-red-600' };
    } else if (category.toLowerCase().includes('obligation') || category.toLowerCase().includes('mandatory')) {
        return { icon: Circle, label: 'Rond bleu (Obligation)', color: 'text-blue-600' };
    } else if (category.toLowerCase().includes('information')) {
        return { icon: Square, label: 'Carré bleu (Information)', color: 'text-blue-500' };
    } else if (category.toLowerCase().includes('stop')) {
        return { icon: Octagon, label: 'Octogone (Stop)', color: 'text-red-700' };
    }
    return { icon: Square, label: 'Autre', color: 'text-slate-500' };
};

export default function Signs() {
    const [signs, setSigns] = useState([]);
    const [search, setSearch] = useState('');
    const [selectedSign, setSelectedSign] = useState(null);
    const [selectedCategory, setSelectedCategory] = useState('all');

    useEffect(() => {
        const fetchSigns = async () => {
            try {
                const res = await axios.get('/api/signs');
                setSigns(res.data);
            } catch (e) {
                console.error(e);
            }
        };
        fetchSigns();
    }, []);

    const filteredSigns = signs.filter(s => 
        (s.name.toLowerCase().includes(search.toLowerCase()) || 
        s.category.toLowerCase().includes(search.toLowerCase())) &&
        (selectedCategory === 'all' || s.category === selectedCategory)
    );

    // Group signs by category
    const categories = [...new Set(signs.map(s => s.category))];
    const signsByCategory = {};
    filteredSigns.forEach(sign => {
        if (!signsByCategory[sign.category]) {
            signsByCategory[sign.category] = [];
        }
        signsByCategory[sign.category].push(sign);
    });

    return (
        <div className="min-h-screen pb-10">
            {/* En-tête cohérent + retour accueil */}
            <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 sticky top-0 z-30 p-4">
                <div className="max-w-6xl mx-auto flex items-center gap-3">
                    <Link to="/">
                        <Button variant="ghost" size="icon" aria-label="Retour à l'accueil">
                            <ArrowLeft className="h-5 w-5" />
                        </Button>
                    </Link>
                    <h1 className="text-xl font-heading font-bold text-slate-900 dark:text-white">Panneaux de Signalisation</h1>
                </div>
            </header>

            <div className="max-w-6xl mx-auto p-6">
            <div className="mb-8 flex justify-end">
                <div className="relative w-full md:w-72">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-600 dark:text-slate-400" />
                    <Input
                        placeholder="Rechercher un panneau..."
                        className="pl-9 rounded-full"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
            </div>

            {/* Category Tabs */}
            <Tabs value={selectedCategory} onValueChange={setSelectedCategory} className="mb-6">
                <TabsList className="flex flex-wrap h-auto gap-2">
                    <TabsTrigger value="all" className="rounded-full">
                        Tous
                    </TabsTrigger>
                    {categories.map(cat => {
                        const shape = getSignShape(cat);
                        const ShapeIcon = shape.icon;
                        return (
                            <TabsTrigger key={cat} value={cat} className="rounded-full flex items-center gap-2">
                                <ShapeIcon className={`h-4 w-4 ${shape.color}`} />
                                {cat}
                            </TabsTrigger>
                        );
                    })}
                </TabsList>
            </Tabs>

            {/* Display signs grouped by category */}
            {Object.keys(signsByCategory).length > 0 ? (
                Object.entries(signsByCategory).map(([category, categorySigns]) => {
                    const shape = getSignShape(category);
                    const ShapeIcon = shape.icon;
                    
                    return (
                        <div key={category} className="mb-12">
                            <div className="flex items-center gap-3 mb-4">
                                <ShapeIcon className={`h-6 w-6 ${shape.color}`} />
                                <h2 className="text-xl font-bold text-slate-900 dark:text-white">{category}</h2>
                                <span className="text-sm text-slate-500 dark:text-slate-400">({categorySigns.length})</span>
                            </div>
                            
                            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6">
                                {categorySigns.map(sign => (
                                    <Card 
                                        key={sign.id} 
                                        className="cursor-pointer hover:scale-105 transition-transform hover:shadow-lg border bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700"
                                        onClick={() => setSelectedSign(sign)}
                                    >
                                        <CardContent className="p-4 flex flex-col items-center text-center h-full justify-between">
                                            <div className="w-full aspect-square relative mb-3 flex items-center justify-center">
                                                <img src={sign.image_url} alt={sign.name} className="max-w-full max-h-full object-contain drop-shadow-md" />
                                            </div>
                                            <div className="font-medium text-sm leading-tight text-slate-900 dark:text-white mb-2">{sign.name}</div>
                                            {sign.description && (
                                                <div className="text-xs text-slate-600 dark:text-slate-400 line-clamp-2">
                                                    {sign.description}
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        </div>
                    );
                })
            ) : (
                <div className="text-center py-12 text-slate-600 dark:text-slate-400">Aucun panneau trouvé.</div>
            )}

            <Dialog open={!!selectedSign} onOpenChange={() => setSelectedSign(null)}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle className="text-slate-900 dark:text-white">{selectedSign?.name}</DialogTitle>
                        <DialogDescription className="text-sky-600 dark:text-sky-400 font-medium flex items-center gap-2">
                            {selectedSign && (() => {
                                const shape = getSignShape(selectedSign.category);
                                const ShapeIcon = shape.icon;
                                return (
                                    <>
                                        <ShapeIcon className={`h-4 w-4 ${shape.color}`} />
                                        {selectedSign.category}
                                    </>
                                );
                            })()}
                        </DialogDescription>
                    </DialogHeader>
                    <div className="flex flex-col items-center gap-6 py-4">
                        <div className="w-48 h-48 flex items-center justify-center">
                            <img src={selectedSign?.image_url} alt={selectedSign?.name} className="max-w-full max-h-full drop-shadow-xl" />
                        </div>
                        <div className="w-full">
                            <h3 className="font-semibold text-sm text-slate-700 dark:text-slate-300 mb-2">Explication :</h3>
                            <p className="text-center text-slate-700 dark:text-slate-200 leading-relaxed">
                                {selectedSign?.description || "Aucune explication disponible."}
                            </p>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
            </div>
        </div>
    );
}
