import React from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import FunnelShell from '../components/funnel/FunnelShell';
import { Notice } from '../components/funnel/fields';
import { Button } from '../components/ui/button';
import { readRememberedPlan } from '../lib/funnel';
import { XCircle } from 'lucide-react';

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
          <XCircle className="h-10 w-10 text-red-600 dark:text-red-400" />
        </div>

        {message && <Notice tone="warning">{message}</Notice>}

        <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-700">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Causes les plus fréquentes
          </h2>
          <ul className="space-y-1.5 text-sm text-slate-600 dark:text-slate-300">
            {REASONS.map((reason) => (
              <li key={reason} className="flex gap-2"><span aria-hidden="true">•</span><span>{reason}</span></li>
            ))}
          </ul>
        </div>

        <div className="space-y-3">
          <Button className="h-10 w-full" asChild>
            <Link to={retryTo}>Réessayer le paiement</Link>
          </Button>
          <Button variant="outline" className="h-10 w-full" asChild>
            <Link to="/subscribe">Choisir une autre formule</Link>
          </Button>
        </div>

        <p className="text-center text-xs text-muted-foreground">
          Besoin d'aide ?{' '}
          <a href="mailto:support@flash-neiga.com" className="underline hover:text-foreground">support@flash-neiga.com</a>
          {transactionId && <> — référence <span className="font-mono">{transactionId.slice(0, 8)}</span></>}
        </p>
      </div>
    </FunnelShell>
  );
}
