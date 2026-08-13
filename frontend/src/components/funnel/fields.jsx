import React, { useId, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { Input } from '../ui/input';
import { Label } from '../ui/label';

/**
 * Champs et encarts du tunnel. Ils enveloppent les composants d'interface déjà
 * utilisés partout dans l'application : un seul système de formulaires pour le
 * produit entier, plutôt qu'un style propre au parcours d'abonnement.
 */

export function Field({ label, hint, htmlFor, children }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function TextField({ label, hint, className = '', ...props }) {
  const id = useId();
  return (
    <Field label={label} hint={hint} htmlFor={id}>
      <Input id={id} className={`h-10 ${className}`} {...props} />
    </Field>
  );
}

export function PasswordField({ label, hint, ...props }) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  return (
    <Field label={label} hint={hint} htmlFor={id}>
      <div className="relative">
        <Input id={id} type={visible ? 'text' : 'password'} className="h-10 pr-10" {...props} />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
        >
          {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </Field>
  );
}

export function FormError({ children }) {
  if (!children) return null;
  return (
    <p
      role="alert"
      className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300"
    >
      {children}
    </p>
  );
}

export function Notice({ children, tone = 'info' }) {
  const tones = {
    info: 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-300',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300',
    warning: 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300',
  };
  return <div className={`rounded-md border px-3 py-2 text-sm ${tones[tone] || tones.info}`}>{children}</div>;
}
