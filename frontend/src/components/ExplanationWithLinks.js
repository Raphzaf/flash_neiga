import React from 'react';
import { ExternalLink } from 'lucide-react';

export function ExplanationWithLinks({ explanation, onCourseClick }) {
    if (!explanation) return null;

    // Parser le texte pour détecter les liens [texte](#course:id)
    const parseExplanation = (text) => {
        const courseRegex = /\[([^\]]+)\]\(#course:([a-zA-Z0-9-]+)\)/g;
        const parts = [];
        let lastIndex = 0;
        let match;

        while ((match = courseRegex.exec(text)) !== null) {
            // Texte avant le lien
            if (match.index > lastIndex) {
                parts.push({
                    type: 'text',
                    content: text.substring(lastIndex, match.index)
                });
            }

            // Lien vers cours
            parts.push({
                type: 'link',
                text: match[1],  // Texte du lien
                courseId: match[2]  // ID du cours
            });

            lastIndex = match.index + match[0].length;
        }

        // Texte après le dernier lien
        if (lastIndex < text.length) {
            parts.push({
                type: 'text',
                content: text.substring(lastIndex)
            });
        }

        return parts;
    };

    const parts = parseExplanation(explanation || '');

    // Si pas de liens détectés, retourner le texte brut
    if (parts.length === 0) {
        return <div className="text-sm text-slate-700 dark:text-slate-300">{explanation}</div>;
    }

    return (
        <div className="text-sm text-slate-700 dark:text-slate-300">
            {parts.map((part, index) => {
                if (part.type === 'text') {
                    return <span key={index}>{part.content}</span>;
                } else {
                    return (
                        <button
                            key={index}
                            onClick={() => onCourseClick(part.courseId)}
                            className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline font-medium inline-flex items-center gap-1"
                        >
                            {part.text}
                            <ExternalLink className="h-3 w-3" />
                        </button>
                    );
                }
            })}
        </div>
    );
}
