import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Search } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function Signs() {
    const [signs, setSigns] = useState([]);
    const [search, setSearch] = useState('');
    const [selectedSign, setSelectedSign] = useState(null);

    useEffect(() => {
        const fetchSigns = async () => {
            try {
                const res = await axios.get(`${BACKEND_URL}/api/signs`);
                setSigns(res.data);
            } catch (e) {
                console.error(e);
            }
        };
        fetchSigns();
    }, []);

    const filteredSigns = signs.filter(s => 
        s.name.toLowerCase().includes(search.toLowerCase()) || 
        s.category.toLowerCase().includes(search.toLowerCase())
    );

    return (
        <div className="max-w-6xl mx-auto p-6 min-h-screen">
            <div className="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
                <h1 className="text-3xl font-heading font-bold">Panneaux de Signalisation</h1>
                <div className="relative w-full md:w-64">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input 
                        placeholder="Rechercher un panneau..." 
                        className="pl-9 rounded-full"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6">
                {filteredSigns.map(sign => (
                    <Card 
                        key={sign.id} 
                        className="cursor-pointer hover:scale-105 transition-transform hover:shadow-lg border-0 bg-white dark:bg-slate-900"
                        onClick={() => setSelectedSign(sign)}
                    >
                        <CardContent className="p-4 flex flex-col items-center text-center h-full justify-between">
                            <div className="w-full aspect-square relative mb-3 flex items-center justify-center">
                                <img src={sign.image_url} alt={sign.name} className="max-w-full max-h-full object-contain drop-shadow-md" />
                            </div>
                            <div className="font-medium text-sm leading-tight">{sign.name}</div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {filteredSigns.length === 0 && (
                <div className="text-center py-12 text-muted-foreground">Aucun panneau trouvé.</div>
            )}

            <Dialog open={!!selectedSign} onOpenChange={() => setSelectedSign(null)}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>{selectedSign?.name}</DialogTitle>
                        <DialogDescription className="text-primary font-medium">{selectedSign?.category}</DialogDescription>
                    </DialogHeader>
                    <div className="flex flex-col items-center gap-6 py-4">
                        <div className="w-48 h-48 flex items-center justify-center">
                            <img src={selectedSign?.image_url} alt={selectedSign?.name} className="max-w-full max-h-full drop-shadow-xl" />
                        </div>
                        <p className="text-center text-slate-600 dark:text-slate-300 leading-relaxed">
                            {selectedSign?.description}
                        </p>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
