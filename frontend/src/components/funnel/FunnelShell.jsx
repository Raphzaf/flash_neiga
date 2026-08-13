import React from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader } from '../ui/card';

/**
 * Ossature commune du tunnel : connexion, création de compte, choix de la
 * formule, paiement et confirmations.
 *
 * Elle réutilise le système de l'application (cartes, bordures, palette slate,
 * couleur primaire) et laisse le fond de page à l'ossature générale : ces
 * écrans doivent ressembler au reste du produit, pas à une parenthèse.
 */

const WIDTHS = {
  sm: 'max-w-md',
  md: 'max-w-xl',
  lg: 'max-w-3xl',
};

export const STEPS = ['Compte', 'Formule', 'Paiement'];

function Steps({ current }) {
  return (
    <ol className="mb-6 flex items-center justify-center gap-3" aria-label="Étapes de l'abonnement">
      {STEPS.map((label, index) => {
        const position = index + 1;
        const done = position < current;
        const active = position === current;
        return (
          <li key={label} className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span
                aria-current={active ? 'step' : undefined}
                className={[
                  'flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold',
                  done ? 'bg-primary/15 text-primary' : '',
                  active ? 'bg-primary text-primary-foreground' : '',
                  !done && !active ? 'bg-slate-200 text-slate-500 dark:bg-slate-700 dark:text-slate-400' : '',
                ].join(' ')}
              >
                {done ? '✓' : position}
              </span>
              <span className={`text-xs font-medium ${active ? 'text-slate-900 dark:text-white' : 'text-muted-foreground'}`}>
                {label}
              </span>
            </div>
            {position < STEPS.length && (
              <span className="h-px w-5 bg-slate-300 dark:bg-slate-700" aria-hidden="true" />
            )}
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
}) {
  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center px-4 py-10">
      <div className={`w-full ${WIDTHS[width] || WIDTHS.sm}`}>
        <Link
          to="/"
          className="mb-6 flex items-center justify-center gap-2.5"
          aria-label="Flash Neiga"
        >
          <img src="/brand-logo.svg" alt="" className="h-7 w-7" />
          <span className="font-heading text-lg font-bold tracking-tight text-slate-900 dark:text-white">
            Flash Neiga
          </span>
        </Link>

        {step && <Steps current={step} />}

        <Card className="border-slate-200 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          {(title || subtitle) && (
            <CardHeader className="space-y-1.5 pb-4 text-center">
              {title && (
                <h1 className="font-heading text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                  {title}
                </h1>
              )}
              {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
            </CardHeader>
          )}
          <CardContent className="pb-6">{children}</CardContent>
        </Card>

        {footer && <div className="mt-5 text-center text-sm text-muted-foreground">{footer}</div>}
      </div>
    </div>
  );
}
