import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import FunnelShell from '../components/funnel/FunnelShell';
import { FormError, Notice } from '../components/funnel/fields';
import { Button } from '../components/ui/button';
import { formatDate, formatPrice, pricePerDay, rememberPlan, readRememberedPlan } from '../lib/funnel';
import { Check, Loader2 } from 'lucide-react';

/**
 * Choix de la formule (étape 2).
 *
 * Le catalogue et les prix viennent du serveur : la formule affichée ici est
 * exactement celle qui sera facturée. Le choix est mémorisé et repris tel quel
 * par la page de paiement, y compris après un rechargement ou un retour arrière.
 */
export default function Subscribe() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, subscription } = useAuth();

  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  const loadPlans = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await axios.get('/api/payments/hyp/plans', { params: { visible_only: true } });
      setPlans(data.items || []);
    } catch {
      setError("Impossible de charger les formules pour le moment. Réessaie dans un instant.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadPlans(); }, [loadPlans]);

  // Reprise du choix : URL d'abord (partage / retour arrière), puis mémoire
  // locale, puis la formule la plus complète.
  useEffect(() => {
    if (!plans.length || selected) return;
    const candidates = [searchParams.get('plan'), readRememberedPlan()];
    const known = candidates.find((id) => plans.some((p) => p.plan_id === id));
    setSelected(known || plans[plans.length - 1]?.plan_id);
  }, [plans, selected, searchParams]);

  const groups = useMemo(() => {
    const byLabel = new Map();
    plans.forEach((plan) => {
      if (!byLabel.has(plan.label)) byLabel.set(plan.label, []);
      byLabel.get(plan.label).push(plan);
    });
    return Array.from(byLabel, ([label, items]) => ({ label, items }));
  }, [plans]);

  const selectedPlan = plans.find((p) => p.plan_id === selected) || null;

  const choose = (planId) => {
    setSelected(planId);
    rememberPlan(planId);
    // L'URL porte le choix : un rechargement ou un partage de lien le conserve.
    setSearchParams({ plan: planId }, { replace: true });
  };

  const goToCheckout = () => {
    if (!selectedPlan) return;
    rememberPlan(selectedPlan.plan_id);
    navigate(`/checkout?plan=${encodeURIComponent(selectedPlan.plan_id)}`);
  };

  const active = subscription?.subscription && !subscription.subscription.expired;

  return (
    <FunnelShell
      step={2}
      width="lg"
      title="Choisis ta formule"
      subtitle={
        user
          ? `Elle sera activée sur le compte ${user.email}.`
          : 'Toutes les formules donnent accès à la plateforme complète.'
      }
      footer={
        <Link to="/pricing" className="underline underline-offset-4 hover:text-foreground">
          Voir le détail des formules
        </Link>
      }
    >
      {active && (
        <div className="mb-5">
          <Notice tone="success">
            Ton abonnement <strong>{subscription.subscription.plan_name}</strong> est actif jusqu'au{' '}
            {formatDate(subscription.subscription.end_date)}.{' '}
            <Link to="/" className="underline underline-offset-4">Accéder à la plateforme</Link> — ou choisis
            ci-dessous une nouvelle formule pour prendre la suite.
          </Notice>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Chargement des formules…
        </div>
      ) : error ? (
        <div className="space-y-3">
          <FormError>{error}</FormError>
          <Button variant="outline" className="w-full" onClick={loadPlans}>Réessayer</Button>
        </div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            {groups.map(({ label, items }) => {
              const groupSelected = items.some((p) => p.plan_id === selected);
              return (
                <section
                  key={label}
                  className={`rounded-lg border p-4 transition-colors ${
                    groupSelected
                      ? 'border-primary/60 bg-primary/[0.04]'
                      : 'border-slate-200 dark:border-slate-700'
                  }`}
                >
                  <h2 className="font-heading text-base font-bold text-slate-900 dark:text-white">
                    Formule {label}
                  </h2>

                  <div role="radiogroup" aria-label={`Durée — formule ${label}`} className="mt-3 grid grid-cols-3 gap-2">
                    {items.map((plan) => {
                      const isSelected = plan.plan_id === selected;
                      return (
                        <button
                          key={plan.plan_id}
                          type="button"
                          role="radio"
                          aria-checked={isSelected}
                          onClick={() => choose(plan.plan_id)}
                          className={`rounded-md border px-2 py-2 text-center transition-colors ${
                            isSelected
                              ? 'border-primary bg-primary text-primary-foreground'
                              : 'border-slate-200 hover:border-slate-300 dark:border-slate-700 dark:hover:border-slate-600'
                          }`}
                        >
                          <span className={`block text-[11px] font-medium ${isSelected ? 'opacity-90' : 'text-muted-foreground'}`}>
                            {plan.period}
                          </span>
                          <span className="block text-base font-bold">
                            {formatPrice(plan.amount, plan.currency)}
                          </span>
                        </button>
                      );
                    })}
                  </div>

                  <ul className="mt-4 space-y-2">
                    {(items[0]?.features || []).map((feature) => (
                      <li key={feature} className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
          </div>

          {selectedPlan && (
            <div className="mt-5 flex flex-col gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/40 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-xs text-muted-foreground">Ta sélection</div>
                <div className="font-semibold text-slate-900 dark:text-white">
                  Formule {selectedPlan.label} · {selectedPlan.period} ·{' '}
                  {formatPrice(selectedPlan.amount, selectedPlan.currency)}
                </div>
                {pricePerDay(selectedPlan.amount, selectedPlan.duration_days) && (
                  <div className="text-xs text-muted-foreground">
                    soit environ {pricePerDay(selectedPlan.amount, selectedPlan.duration_days)} ₪ par jour
                  </div>
                )}
              </div>
              <Button className="h-10 sm:w-auto sm:px-6" onClick={goToCheckout}>Continuer</Button>
            </div>
          )}
        </>
      )}
    </FunnelShell>
  );
}
