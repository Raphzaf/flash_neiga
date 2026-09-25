import React from 'react';
import { Link } from 'react-router-dom';
import { Sparkles } from 'lucide-react';

/**
 * Invitation à passer au Premium, affichée à la place du chat pour un élève
 * Standard. Le chat « prof 24h/24 » est ce qui distingue le Premium : le
 * montrer (sans le donner) fait comprendre ce que la formule apporte.
 */
export default function PremiumUpsell({ compact = false }) {
    return (
        <div className={`flex flex-col items-center text-center gap-3 ${compact ? 'p-4' : 'p-6'}`}>
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-amber-100 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300">
                <Sparkles className="h-5 w-5" />
            </div>
            <div className="font-semibold text-slate-900 dark:text-white">Ton prof 24h/24, c'est le Premium</div>
            <p className="text-sm text-slate-600 dark:text-slate-300">
                Pose toutes tes questions, sans limite : ton prof te répond en mini leçons illustrées,
                avec des mises en situation réelles.
            </p>
            <Link
                to="/subscribe"
                className="inline-flex items-center justify-center rounded-xl bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-400"
            >
                Passer au Premium
            </Link>
        </div>
    );
}
