import React, { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import axios from 'axios';
import { Button } from './ui/button';
import { MessageCircle, Send, X, Loader2, GraduationCap } from 'lucide-react';

const WELCOME = {
    role: 'assistant',
    content: "Salut 👋 Je suis ton prof de code, dispo 24h/24. Pose-moi n'importe quelle question sur le code de la route israélien ou la conduite : priorités, panneaux, distances, alcoolémie… Je t'explique simplement !",
};

/**
 * Chatbot flottant « prof 24h/24 ». Bulle en bas à droite qui ouvre un panneau
 * de conversation. Backend sans état : on renvoie l'historique récent à chaque tour.
 * Masqué pendant un examen en cours (/exam) pour ne pas fausser l'épreuve.
 */
export default function ChatWidget() {
    const location = useLocation();
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState([WELCOME]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const scrollRef = useRef(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, open, loading]);

    // Pas de chatbot pendant un examen blanc en cours.
    if (location.pathname === '/exam') return null;

    const send = async () => {
        const text = input.trim();
        if (!text || loading) return;
        const next = [...messages, { role: 'user', content: text }];
        setMessages(next);
        setInput('');
        setLoading(true);
        try {
            // On envoie l'historique sans le message de bienvenue (purement UI).
            const payload = next.filter((m) => m !== WELCOME).map((m) => ({ role: m.role, content: m.content }));
            const res = await axios.post('/api/ai-coach/chat', { messages: payload });
            setMessages((prev) => [...prev, { role: 'assistant', content: res.data.reply }]);
        } catch (e) {
            const detail = e.response?.data?.detail || "Le prof est momentanément indisponible, réessaie dans un instant.";
            setMessages((prev) => [...prev, { role: 'assistant', content: detail, error: true }]);
        } finally {
            setLoading(false);
        }
    };

    const onKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            send();
        }
    };

    return (
        <>
            {/* Bulle flottante */}
            {!open && (
                <button
                    onClick={() => setOpen(true)}
                    aria-label="Ouvrir le chat avec le prof"
                    className="fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-full bg-sky-600 hover:bg-sky-500 text-white px-5 py-3 shadow-xl transition-transform hover:scale-105"
                >
                    <MessageCircle className="h-5 w-5" />
                    <span className="font-semibold hidden sm:inline">Demande à ton prof</span>
                </button>
            )}

            {/* Panneau de chat */}
            {open && (
                <div className="fixed bottom-5 right-5 z-50 flex flex-col w-[92vw] max-w-sm h-[70vh] max-h-[560px] rounded-2xl overflow-hidden shadow-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
                    {/* En-tête */}
                    <div className="flex items-center justify-between px-4 py-3 bg-sky-600 text-white">
                        <div className="flex items-center gap-2">
                            <GraduationCap className="h-5 w-5" />
                            <span className="font-semibold">Ton prof de code</span>
                        </div>
                        <button onClick={() => setOpen(false)} aria-label="Fermer" className="hover:opacity-80">
                            <X className="h-5 w-5" />
                        </button>
                    </div>

                    {/* Messages */}
                    <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3 bg-slate-50 dark:bg-slate-950">
                        {messages.map((m, i) => (
                            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div
                                    className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-line ${
                                        m.role === 'user'
                                            ? 'bg-sky-600 text-white rounded-br-sm'
                                            : m.error
                                                ? 'bg-red-100 dark:bg-red-950/40 text-red-800 dark:text-red-200 rounded-bl-sm'
                                                : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-700 rounded-bl-sm'
                                    }`}
                                >
                                    {m.content}
                                </div>
                            </div>
                        ))}
                        {loading && (
                            <div className="flex justify-start">
                                <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl rounded-bl-sm px-3 py-2 text-sm text-slate-500 dark:text-slate-400 flex items-center gap-2">
                                    <Loader2 className="h-4 w-4 animate-spin" /> Ton prof réfléchit…
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Saisie */}
                    <div className="p-3 border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 flex items-end gap-2">
                        <textarea
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={onKeyDown}
                            rows={1}
                            placeholder="Pose ta question…"
                            className="flex-1 resize-none max-h-28 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                        />
                        <Button onClick={send} disabled={loading || !input.trim()} size="icon" className="shrink-0 rounded-xl">
                            <Send className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            )}
        </>
    );
}
