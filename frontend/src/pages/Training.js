import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { CheckCircle, XCircle, Info, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function Training() {
    const [category, setCategory] = useState('all');
    const [questions, setQuestions] = useState([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [loading, setLoading] = useState(false);
    const [feedback, setFeedback] = useState(null); // { is_correct, explanation, correct_option_id }
    const [selectedOption, setSelectedOption] = useState(null);

    const fetchQuestions = async () => {
        setLoading(true);
        try {
            const url = category === 'all' ? `${BACKEND_URL}/api/questions` : `${BACKEND_URL}/api/questions?category=${category}`;
            const res = await axios.get(url);
            // Shuffle client side for variety
            const shuffled = res.data.sort(() => 0.5 - Math.random());
            setQuestions(shuffled);
            setCurrentIndex(0);
            setFeedback(null);
            setSelectedOption(null);
        } catch (e) {
            toast.error("Erreur lors du chargement des questions");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchQuestions();
    }, [category]);

    const handleAnswer = async (optionId) => {
        if (feedback) return; // Already answered
        setSelectedOption(optionId);

        try {
            const q = questions[currentIndex];
            const res = await axios.post(`${BACKEND_URL}/api/training/check`, {
                question_id: q.id,
                selected_option_id: optionId
            });
            setFeedback(res.data);
        } catch (e) {
            toast.error("Erreur de vérification");
        }
    };

    const nextQuestion = () => {
        if (currentIndex < questions.length - 1) {
            setCurrentIndex(prev => prev + 1);
            setFeedback(null);
            setSelectedOption(null);
        } else {
            // Restart or fetch more
            toast.info("Série terminée ! On recommence.");
            fetchQuestions();
        }
    };

    if (loading && questions.length === 0) return <div className="p-8 text-center">Chargement...</div>;

    if (questions.length === 0) return (
        <div className="p-8 text-center">
            <p className="mb-4">Aucune question disponible dans cette catégorie.</p>
            <Button onClick={() => setCategory('all')}>Voir toutes les questions</Button>
        </div>
    );

    const currentQ = questions[currentIndex];

    return (
        <div className="max-w-3xl mx-auto p-4 min-h-screen flex flex-col">
            {/* Top Bar */}
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-heading font-bold">Entraînement</h1>
                <div className="w-48">
                    <Select value={category} onValueChange={setCategory}>
                        <SelectTrigger>
                            <SelectValue placeholder="Catégorie" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">Toutes catégories</SelectItem>
                            <SelectItem value="Priorités">Priorités</SelectItem>
                            <SelectItem value="Croisements">Croisements</SelectItem>
                            <SelectItem value="Signalisations">Signalisations</SelectItem>
                            <SelectItem value="Mécanique">Mécanique</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {/* Question Card */}
            <div className="flex-1 flex flex-col justify-center">
                <Card className="border-0 shadow-lg overflow-hidden bg-white dark:bg-slate-900">
                    {currentQ.image_url && (
                        <div className="h-64 bg-black flex items-center justify-center">
                            <img src={currentQ.image_url} alt="Context" className="h-full object-contain" />
                        </div>
                    )}
                    
                    <CardContent className="p-6 md:p-8">
                        <h2 className="text-xl font-bold mb-8">{currentQ.text}</h2>

                        <div className="grid grid-cols-1 gap-3">
                            {currentQ.options.map(opt => {
                                let stateClass = "border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800";
                                let icon = null;

                                if (feedback) {
                                    if (opt.id === feedback.correct_option_id) {
                                        stateClass = "border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20 ring-1 ring-emerald-500";
                                        icon = <CheckCircle className="h-5 w-5 text-emerald-600 ml-auto" />;
                                    } else if (opt.id === selectedOption && opt.id !== feedback.correct_option_id) {
                                        stateClass = "border-red-500 bg-red-50 dark:bg-red-900/20 ring-1 ring-red-500";
                                        icon = <XCircle className="h-5 w-5 text-red-600 ml-auto" />;
                                    } else {
                                        stateClass = "opacity-50";
                                    }
                                } else if (selectedOption === opt.id) {
                                    stateClass = "border-primary bg-primary/5 ring-1 ring-primary";
                                }

                                return (
                                    <div 
                                        key={opt.id}
                                        onClick={() => handleAnswer(opt.id)}
                                        className={`p-4 rounded-xl border-2 cursor-pointer transition-all flex items-center ${stateClass}`}
                                    >
                                        <span className="font-medium">{opt.text}</span>
                                        {icon}
                                    </div>
                                );
                            })}
                        </div>

                        {/* Feedback Section */}
                        {feedback && (
                            <div className={`mt-6 p-4 rounded-xl border animate-in slide-in-from-bottom-2 ${feedback.is_correct ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-amber-50 border-amber-200 text-amber-800'}`}>
                                <div className="flex items-start gap-3">
                                    <Info className="h-5 w-5 mt-0.5 flex-shrink-0" />
                                    <div>
                                        <div className="font-bold mb-1">{feedback.is_correct ? 'Correct !' : 'Incorrect'}</div>
                                        <p className="text-sm opacity-90">{feedback.explanation}</p>
                                    </div>
                                </div>
                                <Button onClick={nextQuestion} className="mt-4 w-full bg-slate-900 text-white hover:bg-slate-800">
                                    Question Suivante <ArrowRight className="ml-2 h-4 w-4" />
                                </Button>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
