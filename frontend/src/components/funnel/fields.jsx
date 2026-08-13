import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

/**
 * Champs et boutons du tunnel : une seule définition, partagée par la
 * connexion, la création de compte, le choix de la formule et le paiement.
 * C'est ce qui garantit des inputs, des arrondis et des états de focus
 * identiques d'un écran à l'autre.
 */

export const inputClass =
  'w-full rounded-xl border border-white/25 bg-white/15 px-3.5 py-3 text-sm text-white placeholder:text-white/50 ' +
  'transition-colors focus:border-yellow-300/60 focus:bg-white/20 focus:outline-none focus:ring-2 focus:ring-yellow-300/30 ' +
  'disabled:opacity-70';

export const primaryButtonClass =
  'flex w-full items-center justify-center gap-2 rounded-xl bg-yellow-400 px-4 py-3 text-sm font-bold text-slate-900 ' +
  'transition-colors hover:bg-yellow-300 focus:outline-none focus:ring-2 focus:ring-yellow-200 focus:ring-offset-2 ' +
  'focus:ring-offset-blue-600 disabled:cursor-not-allowed disabled:opacity-70';

export const secondaryButtonClass =
  'flex w-full items-center justify-center gap-2 rounded-xl border border-white/30 bg-white/10 px-4 py-3 text-sm ' +
  'font-semibold text-white transition-colors hover:bg-white/20 focus:outline-none focus:ring-2 focus:ring-white/40 ' +
  'disabled:cursor-not-allowed disabled:opacity-70';

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-white/85">{label}</span>
      {children}
      {hint && <span className="mt-1.5 block text-xs text-white/70">{hint}</span>}
    </label>
  );
}

export function TextField({ label, hint, className = '', ...props }) {
  return (
    <Field label={label} hint={hint}>
      <input className={`${inputClass} ${className}`} {...props} />
    </Field>
  );
}

export function PasswordField({ label, hint, ...props }) {
  const [visible, setVisible] = useState(false);
  return (
    <Field label={label} hint={hint}>
      <div className="relative">
        <input type={visible ? 'text' : 'password'} className={`${inputClass} pr-11`} {...props} />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-white/70 transition-colors hover:text-white"
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
    <p role="alert" className="rounded-xl border border-red-300/40 bg-red-500/15 px-3.5 py-2.5 text-sm text-red-50">
      {children}
    </p>
  );
}

export function Notice({ children, tone = 'info' }) {
  const tones = {
    info: 'border-white/25 bg-white/10 text-white/85',
    success: 'border-emerald-300/40 bg-emerald-400/15 text-emerald-50',
    warning: 'border-yellow-300/40 bg-yellow-300/15 text-yellow-50',
  };
  return (
    <div className={`rounded-xl border px-3.5 py-2.5 text-sm ${tones[tone] || tones.info}`}>{children}</div>
  );
}
