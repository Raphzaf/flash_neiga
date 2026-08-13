import React from 'react';
import { Link } from 'react-router-dom';

/**
 * Décor commun à tout le tunnel : connexion, création de compte, choix de la
 * formule, paiement et confirmation.
 *
 * Une seule source pour le fond, la carte, la typographie et les espacements :
 * l'élève doit avoir l'impression de rester au même endroit du début à la fin.
 * Le décor est volontairement calme (deux halos fixes, aucune animation
 * permanente) pour que l'attention aille au contenu et à l'action.
 */

const WIDTHS = {
  sm: 'max-w-md',
  md: 'max-w-xl',
  lg: 'max-w-4xl',
};

export const STEPS = ['Compte', 'Formule', 'Paiement'];

function Steps({ current }) {
  return (
    <ol className="flex items-center justify-center gap-2 mb-8" aria-label="Étapes de l'abonnement">
      {STEPS.map((label, index) => {
        const position = index + 1;
        const done = position < current;
        const active = position === current;
        return (
          <li key={label} className="flex items-center gap-2">
            <div className="flex items-center gap-2">
              <span
                aria-current={active ? 'step' : undefined}
                className={[
                  'h-6 w-6 rounded-full text-[11px] font-bold flex items-center justify-center transition-colors',
                  done ? 'bg-yellow-400/25 text-yellow-200' : '',
                  active ? 'bg-yellow-400 text-slate-900' : '',
                  !done && !active ? 'bg-white/10 text-white/50' : '',
                ].join(' ')}
              >
                {done ? '✓' : position}
              </span>
              <span className={`text-xs font-semibold tracking-wide ${active ? 'text-white' : 'text-white/50'}`}>
                {label}
              </span>
            </div>
            {position < STEPS.length && <span className="h-px w-6 bg-white/15" aria-hidden="true" />}
          </li>
        );
      })}
    </ol>
  );
}

export default function FunnelShell({
  step = null,
  title,
  subtitle,
  width = 'sm',
  children,
  footer = null,
  showLegal = true,
}) {
  // <section> et non <main> : l'ossature de l'application fournit déjà le
  // <main> de la page, et deux <main> imbriqués perturbent les lecteurs d'écran.
  return (
    <section className="min-h-screen bg-gradient-to-br from-cyan-400 via-blue-500 to-blue-600 px-4 py-10 sm:py-14">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-24 -left-24 h-96 w-96 rounded-full bg-white/15 blur-3xl" />
        <div className="absolute -bottom-32 -right-24 h-96 w-96 rounded-full bg-yellow-300/20 blur-3xl" />
      </div>

      <div className={`relative z-10 mx-auto w-full ${WIDTHS[width] || WIDTHS.sm}`}>
        <Link to="/" className="mb-8 flex items-center justify-center gap-3" aria-label="Flash Neiga">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white shadow-lg shadow-blue-900/20">
            <img src="/brand-logo.svg" alt="" className="h-6 w-6" />
          </span>
          <span className="text-lg font-extrabold tracking-tight text-white">FLASH NEIGA</span>
        </Link>

        {step && <Steps current={step} />}

        <div className="animate-fade-in-up rounded-3xl border border-white/25 bg-white/[0.14] p-6 shadow-[0_12px_40px_rgba(2,20,50,0.28)] backdrop-blur-2xl sm:p-8">
          {(title || subtitle) && (
            <header className="mb-6 text-center">
              {title && <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">{title}</h1>}
              {subtitle && <p className="mt-2 text-sm text-white/80">{subtitle}</p>}
            </header>
          )}
          {children}
        </div>

        {footer && <div className="mt-6 text-center text-sm text-white/80">{footer}</div>}

        {showLegal && (
          <nav className="mt-8 flex flex-wrap justify-center gap-x-6 gap-y-2 text-[11px] uppercase tracking-[0.18em] text-white/70">
            <Link to="/conditions-generales" className="hover:text-white transition-colors">CGU</Link>
            <Link to="/politique-confidentialite" className="hover:text-white transition-colors">Confidentialité</Link>
            <Link to="/politique-remboursement" className="hover:text-white transition-colors">Remboursement</Link>
          </nav>
        )}
      </div>
    </section>
  );
}
