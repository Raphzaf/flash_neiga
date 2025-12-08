import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Progress } from '../components/ui/progress';
import { toast } from 'sonner';
import { Clock, ArrowLeft, ArrowRight, CheckCircle, XCircle } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function Exam() {
    const [examSession, setExamSession] = useState(null);
    const [currentQIndex, setCurrentQIndex] = useState(0);
    const [timeLeft, setTimeLeft] = useState(40 * 60); // 40 minutes in seconds
    const [loading, setLoading] = useState(true);
    const [isFinished, setIsFinished] = useState(false);
    const [result, setResult] = useState(null);
    const navigate = useNavigate();

    // Start Exam
    useEffect(() => {
        const startExam = async () => {
            try {
                const res = await axios.post(`${BACKEND_URL}/api/exam/start`);
                setExamSession(res.data);
                setLoading(false);
            } catch (e) {
                console.error(e);
                toast.error("Impossible de démarrer l'examen. Veuillez réessayer.");
                navigate('/');
            }
        };
        startExam();
    }, [navigate]);

    // Timer
    useEffect(() => {
        if (!loading && !isFinished && timeLeft > 0) {
            const timer = setInterval(() => setTimeLeft(prev => prev - 1), 1000);
            return () => clearInterval(timer);
        } else if (timeLeft === 0 && !isFinished) {
            finishExam();
        }
    }, [loading, isFinished, timeLeft]);

    const formatTime = (seconds) => {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}:${s < 10 ? '0' : ''}${s}`;
    };

    const handleAnswer = async (optionId) => {
        if (!examSession) return;

        // Handle both id and _id for robustness
        const sessionId = examSession.id || examSession._id;
        if (!sessionId) {
            toast.error("Erreur de session: ID manquant");
            return;
        }

        const question = examSession.questions[currentQIndex];
        
        try {
            // Update local state immediately
            const updatedAnswers = [...examSession.answers.filter(a => a.question_id !== question.question_id)];
            updatedAnswers.push({
                question_id: question.question_id,
                selected_option_id: optionId
            });
            
            setExamSession(prev => ({
                ...prev,
                answers: updatedAnswers
            }));

            // Send to backend
            await axios.post(`${BACKEND_URL}/api/exam/${sessionId}/answer`, {
                question_id: question.question_id,
                selected_option_id: optionId
            });

            // Auto advance
            setTimeout(() => {
                if (currentQIndex < examSession.questions.length - 1) {
                    setCurrentQIndex(prev => prev + 1);
                }
            }, 300);

        } catch (e) {
            console.error(e);
            toast.error("Erreur lors de l'enregistrement de la réponse");
        }
    };

    const finishExam = async () => {
        if (!examSession) return;
        const sessionId = examSession.id || examSession._id;
        
        try {
            const res = await axios.post(`${BACKEND_URL}/api/exam/${sessionId}/finish`);
            setResult(res.data);
            setIsFinished(true);
        } catch (e) {
            console.error(e);
            toast.error("Erreur lors de la finalisation");
        }
    };

    if (loading) return <div className="flex h-screen items-center justify-center">Préparation de l'examen...</div>;

    // RESULT SCREEN
    if (isFinished && result) {
        return (
            <div className="min-h-screen bg-slate-50 dark:bg-slate-950 p-4 flex items-center justify-center">
                <Card className="w-full max-w-2xl p-6 md:p-8 text-center space-y-6">
                    <div className="flex justify-center">
                        {result.passed ? (
                            <div className="h-24 w-24 bg-emerald-100 rounded-full flex items-center justify-center text-emerald-600">
                                <CheckCircle className="h-12 w-12" />
                            </div>
                        ) : (
                            <div className="h-24 w-24 bg-red-100 rounded-full flex items-center justify-center text-red-600">
                                <XCircle className="h-12 w-12" />
                            </div>
                        )}
                    </div>
                    
                    <div>
                        <h2 className="text-3xl font-bold mb-2">{result.passed ? "Félicitations !" : "Désolé, c'est raté."}</h2>
                        <p className="text-muted-foreground">Vous avez fait {result.total_questions - result.correct_answers} erreurs.</p>
                    </div>

                    <div className="text-5xl font-black text-primary my-8">
                        {result.correct_answers}/{result.total_questions}
                    </div>

                    <div className="grid grid-cols-2 gap-4 text-left bg-slate-100 dark:bg-slate-900 p-4 rounded-xl">
                        <div>
                            <div className="text-sm text-muted-foreground">Score</div>
                            <div className="font-bold">{result.score_percentage.toFixed(1)}%</div>
                        </div>
                        <div>
                            <div className="text-sm text-muted-foreground">Résultat</div>
                            <div className={`font-bold ${result.passed ? 'text-emerald-600' : 'text-red-600'}`}>
                                {result.passed ? 'Admis' : 'Ajourné'}
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-4 justify-center pt-4">
                        <Button variant="outline" onClick={() => navigate('/')}>Retour au menu</Button>
                        <Button onClick={() => window.location.reload()}>Nouvel Examen</Button>
                        {examSession?.id && (
                            <Button variant="secondary" onClick={() => navigate(`/exam/${examSession.id}`)}>Voir les détails</Button>
                        )}
                    </div>
                </Card>
            </div>
        );
    }

    // EXAM RUNNER
    const currentQuestion = examSession.questions[currentQIndex];
    const currentAnswer = examSession.answers.find(a => a.question_id === currentQuestion.question_id);

    return (
        <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-950">
            {/* Header */}
            <div className="bg-white dark:bg-slate-900 p-4 border-b shadow-sm flex justify-between items-center sticky top-0 z-20">
                <div className="font-bold text-lg">Question {currentQIndex + 1}/{examSession.questions.length}</div>
                <div className={`font-mono font-medium px-3 py-1 rounded-full ${timeLeft < 300 ? 'bg-red-100 text-red-600' : 'bg-slate-100 text-slate-700'} flex items-center`}>
                    <Clock className="w-4 h-4 mr-2" />
                    {formatTime(timeLeft)}
                </div>
                <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-600 hover:bg-red-50" onClick={finishExam}>
                    Terminer
                </Button>
            </div>

            {/* Progress Bar */}
            <Progress value={((currentQIndex + 1) / examSession.questions.length) * 100} className="h-1 rounded-none" />

            {/* Content */}
            <main className="flex-1 max-w-3xl w-full mx-auto p-4 md:p-8 flex flex-col justify-center">
                
                {currentQuestion.image_url && (
                    <div className="mb-6 rounded-xl overflow-hidden border shadow-sm max-h-[300px] w-full flex justify-center bg-black">
                        <img src={currentQuestion.image_url} alt="Question Context" className="h-full object-contain" />
                    </div>
                )}

                <h2 className="text-xl md:text-2xl font-bold mb-8 leading-relaxed text-slate-800 dark:text-slate-100">
                    {currentQuestion.text}
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {currentQuestion.options.map((option) => {
                        const isSelected = currentAnswer?.selected_option_id === option.id;
                        return (
                            <div 
                                key={option.id}
                                onClick={() => handleAnswer(option.id)}
                                className={`
                                    p-6 rounded-2xl border-2 cursor-pointer transition-all duration-200 flex items-center
                                    ${isSelected 
                                        ? 'border-primary bg-primary/5 ring-2 ring-primary/20' 
                                        : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-indigo-300 hover:bg-slate-50'}
                                `}
                                data-testid={`option-${option.id}`}
                            >
                                <div className={`w-8 h-8 rounded-full border-2 mr-4 flex items-center justify-center flex-shrink-0 ${isSelected ? 'border-primary bg-primary text-white' : 'border-slate-300'}`}>
                                    {isSelected && <div className="w-3 h-3 bg-white rounded-full"></div>}
                                </div>
                                <span className="font-medium">{option.text}</span>
                            </div>
                        );
                    })}
                </div>

            </main>

            {/* Footer Nav */}
            <div className="p-4 border-t bg-white dark:bg-slate-900 flex justify-between items-center max-w-3xl w-full mx-auto">
                <Button 
                    variant="outline" 
                    onClick={() => setCurrentQIndex(prev => Math.max(0, prev - 1))}
                    disabled={currentQIndex === 0}
                >
                    <ArrowLeft className="mr-2 h-4 w-4" /> Précédent
                </Button>

                <div className="flex gap-1">
                   {examSession.questions.map((_, idx) => (
                       <div 
                            key={idx} 
                            className={`w-2 h-2 rounded-full ${idx === currentQIndex ? 'bg-primary' : idx < currentQIndex ? 'bg-slate-300' : 'bg-slate-100'}`}
                       />
                   ))}
                </div>

                <Button 
                    onClick={() => setCurrentQIndex(prev => Math.min(examSession.questions.length - 1, prev + 1))}
                    disabled={currentQIndex === examSession.questions.length - 1}
                >
                    Suivant <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
            </div>
        </div>
    );
}
