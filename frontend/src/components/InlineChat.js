import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Button } from './ui/button';
import { MessageCircle, Send, Loader2, GraduationCap } from 'lucide-react';

/**
 * Discussion contextuelle avec le prof, intégrée dans une leçon ou un cours.
 * Réutilise POST /api/ai-coach/chat en passant `context` pour que le prof
 * réponde en tenant compte du sujet en cours (vrai suivi pédagogique).
 *
 * Props :
 *  - context (string)  : le sujet courant (leçon, cours…) injecté au prof
 *  - title (string)    : libellé du bouton d'ouverture
 *  - placeholder (string)
 */
export default function InlineChat({ context, title = '💬 Poser une question sur ce sujet', placeholder = 'Ta question au prof…' }) {
    const [openChat, setOpenChat] = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const scrollRef = useRef(null);

    useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [messages, loading, openChat]);

    const send = async () => {
        const text = input.trim();
        if (!text || loading) return;
        const next = [...messages, { role: 'user', content: text }];
        setMessages(next);
        setInput('');
        setLoading(true);
        try {
            const res = await axios.post('/api/ai-coach/chat', {
                messages: next.map((m) => ({ role: m.role, content: m.content })),
                context: context || undefined,
            });
            setMessages((prev) => [...prev, { role: 'assistant', content: res.data.reply }]);
        } catch (e) {
            const detail = e.response?.data?.detail || 'Le prof est momentanément indisponible, réessaie dans un instant.';
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

    if (!openChat) {
        return (
            <Button variant="outline" onClick={() => setOpenChat(true)} className="gap-2 w-full justify-center">
                <MessageCircle className="h-4 w-4" /> {title}
            </Button>
        );
    }

    return (
        <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 overflow-hidden">
            <div className="flex items-center gap-2 px-3 py-2 bg-sky-600 text-white text-sm font-semibold">
                <GraduationCap className="h-4 w-4" /> Discute avec ton prof
            </div>

            <div ref={scrollRef} className="max-h-64 overflow-y-auto p-3 space-y-2">
                {messages.length === 0 && (
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                        Pose une question sur ce sujet, le prof te répond en tenant compte de ce que tu vois ici.
                    </p>
                )}
                {messages.map((m, i) => (
                    <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-line ${
                            m.role === 'user'
                                ? 'bg-sky-600 text-white rounded-br-sm'
                                : m.error
                                    ? 'bg-red-100 dark:bg-red-950/40 text-red-800 dark:text-red-200 rounded-bl-sm'
                                    : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 border border-slate-200 dark:border-slate-700 rounded-bl-sm'
                        }`}>
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

            <div className="p-2 border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 flex items-end gap-2">
                <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={onKeyDown}
                    rows={1}
                    placeholder={placeholder}
                    className="flex-1 resize-none max-h-24 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
                <Button onClick={send} disabled={loading || !input.trim()} size="icon" className="shrink-0 rounded-lg">
                    <Send className="h-4 w-4" />
                </Button>
            </div>
        </div>
    );
}
