import React from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import FunnelShell from '../components/funnel/FunnelShell';
import { Notice, primaryButtonClass, secondaryButtonClass } from '../components/funnel/fields';
import { readRememberedPlan } from '../lib/funnel';
import { RefreshCw, XCircle } from 'lucide-react';

const REASONS = [
  'Fonds insuffisants ou plafond de carte atteint',
  'Informations de carte incorrectes ou carte expirée',
  'Paiement refusé par la banque',
  'Paiement interrompu ou annulé',
];

export default function PaymentFailure() {
  const [searchParams] = useSearchParams();

  const transactionId = searchParams.get('transaction_id') || searchParams.get('Order');
  const message = searchParams.get('error');
  // On rouvre le paiement sur la formule choisie : l'élève ne recommence pas
  // son parcours depuis le début.
  const plan = searchParams.get('plan') || readRememberedPlan();
  const retryTo = plan ? `/checkout?plan=${encodeURIComponent(plan)}` : '/subscribe';

  return (
    <FunnelShell
      step={3}
      title="Le paiement n'a pas abouti"
      subtitle="Aucun montant n'a été débité. Tu peux réessayer immédiatement."
    >
      <div className="space-y-5">
        <div className="flex justify-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-red-400/20">
            <XCircle className="h-8 w-8 text-red-300" />
          </span>
        </div>

        {message && <Notice tone="warning">{message}</Notice>}

        <div className="rounded-2xl border border-white/20 bg-white/[0.08] p-4">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-white/70">
            Causes les plus fréquentes
          </h2>
          <ul className="space-y-1.5 text-sm text-white/80">
            {REASONS.map((reason) => (
              <li key={reason} className="flex gap-2"><span aria-hidden="true">•</span><span>{reason}</span></li>
            ))}
          </ul>
        </div>

        <Link to={retryTo} className={primaryButtonClass}>
          <RefreshCw className="h-4 w-4" /> Réessayer le paiement
        </Link>
        <Link to="/subscribe" className={secondaryButtonClass}>Choisir une autre formule</Link>

        <p className="text-center text-xs text-white/70">
          Besoin d'aide ?{' '}
          <a href="mailto:support@flash-neiga.com" className="underline hover:text-white">support@flash-neiga.com</a>
          {transactionId && <> — référence <span className="font-mono">{transactionId.slice(0, 8)}</span></>}
        </p>
      </div>
    </FunnelShell>
  );
}
