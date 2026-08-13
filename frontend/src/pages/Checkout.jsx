import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import FunnelShell from '../components/funnel/FunnelShell';
import { FormError, Notice } from '../components/funnel/fields';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { formatDate, formatPrice, forgetPlan, rememberPlan, readRememberedPlan } from '../lib/funnel';
import { ArrowLeft, Loader2, Lock } from 'lucide-react';

/**
 * Paiement (étape 3).
 *
 * Récapitulatif court puis paiement : l'élève voit ce qu'il prend, ce qu'il
 * paie et jusqu'à quand, avant d'être redirigé vers la page sécurisée de HYP.
 * Le montant affiché est recalculé côté serveur au moment du paiement — ici,
 * rien n'est décidé par le navigateur.
 */
export default function Checkout() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user, subscription } = useAuth();

  const planId = searchParams.get('plan') || readRememberedPlan();

  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState(null);
  const [paying, setPaying] = useState(false);

  const [promoInput, setPromoInput] = useState('');
  const [promo, setPromo] = useState(null);
  const [promoMessage, setPromoMessage] = useState(null);
  const [promoChecking, setPromoChecking] = useState(false);

  const loadPlan = useCallback(async () => {
    if (!planId) {
      setNotFound(true);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const { data } = await axios.get('/api/payments/hyp/plans', { params: { visible_only: true } });
      const found = (data.items || []).find((p) => p.plan_id === planId);
      if (!found) {
        setNotFound(true);
      } else {
        setPlan(found);
        rememberPlan(found.plan_id);
      }
    } catch {
      setError("Impossible de charger ta formule. Vérifie ta connexion et réessaie.");
    } finally {
      setLoading(false);
    }
  }, [planId]);

  useEffect(() => { loadPlan(); }, [loadPlan]);

  // Formule inconnue ou absente : on renvoie au choix plutôt que d'afficher une
  // page de paiement vide.
  useEffect(() => {
    if (notFound) navigate('/subscribe', { replace: true });
  }, [notFound, navigate]);

  const applyPromo = async () => {
    const code = promoInput.trim();
    if (!code || !plan) return;
    setPromoChecking(true);
    setPromoMessage(null);
    try {
      const { data } = await axios.post('/api/payments/hyp/validate-promo', {
        code, plan_id: plan.plan_id, user_id: user?.id || null,
      });
      if (data.valid) {
        setPromo(data);
        setPromoMessage({ ok: true, text: data.message });
      } else {
        setPromo(null);
        setPromoMessage({ ok: false, text: data.message });
      }
    } catch (err) {
      setPromo(null);
      setPromoMessage({ ok: false, text: err?.response?.data?.detail || 'Code invalide.' });
    } finally {
      setPromoChecking(false);
    }
  };

  const pay = async () => {
    if (!plan) return;
    setPaying(true);
    setError(null);
    try {
      const { data } = await axios.post('/api/payments/hyp/create-payment', {
        plan_id: plan.plan_id,
        promo_code: promo?.code || null,
      });

      // Remise de 100 % : aucun paiement à effectuer, l'accès est déjà ouvert.
      if (data.free) {
        forgetPlan();
        window.location.href = `/payment/success?transaction_id=${data.transaction_id}`;
        return;
      }
      if (data.payment_url) {
        window.location.href = data.payment_url;
        return;
      }
      setError("Le paiement n'a pas pu être ouvert. Réessaie dans un instant.");
      setPaying(false);
    } catch (err) {
      if (err?.response?.status === 401) {
        // Session perdue pendant le parcours : on repasse par la connexion, la
        // formule est conservée.
        navigate('/login?reason=session', { replace: true });
        return;
      }
      setError(err?.response?.data?.detail || "Le paiement n'a pas pu être lancé. Réessaie dans un instant.");
      setPaying(false);
    }
  };

  if (loading || notFound) {
    return (
      <FunnelShell step={3} width="md" title="Paiement">
        <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Préparation de ta commande…
        </div>
      </FunnelShell>
    );
  }

  const total = promo ? promo.final_amount : plan.amount;
  const endDate = new Date(Date.now() + (plan.duration_days || 30) * 86400000);
  const activeSub = subscription?.subscription && !subscription.subscription.expired
    ? subscription.subscription
    : null;

  return (
    <FunnelShell
      step={3}
      width="md"
      title="Finalise ton abonnement"
      subtitle="Dernière étape avant d'accéder à la plateforme."
    >
      <div className="space-y-6">
        {activeSub && (
          <Notice tone="warning">
            Tu as déjà un abonnement actif jusqu'au {formatDate(activeSub.end_date)}. Ce paiement ouvrira
            un nouvel abonnement à partir d'aujourd'hui.
          </Notice>
        )}

        {/* ===== Récapitulatif ===== */}
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Ton abonnement
          </h2>
          <div className="rounded-lg border border-slate-200 dark:border-slate-700">
            <div className="flex items-baseline justify-between gap-4 p-4">
              <div>
                <div className="font-semibold text-slate-900 dark:text-white">Formule {plan.label}</div>
                <div className="text-sm text-muted-foreground">{plan.period} d'accès complet</div>
              </div>
              <div className="font-heading text-xl font-bold text-slate-900 dark:text-white">
                {formatPrice(plan.amount, plan.currency)}
              </div>
            </div>

            <dl className="space-y-2 border-t border-slate-200 p-4 text-sm dark:border-slate-700">
              <div className="flex justify-between gap-4">
                <dt className="shrink-0 text-muted-foreground">Compte</dt>
                {/* Les adresses longues doivent rester dans la carte en mobile. */}
                <dd className="break-all text-right text-slate-900 dark:text-slate-200">{user?.email || '—'}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="shrink-0 text-muted-foreground">Accès</dt>
                <dd className="text-right text-slate-900 dark:text-slate-200">
                  dès le paiement, jusqu'au {formatDate(endDate)}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="shrink-0 text-muted-foreground">Facturation</dt>
                <dd className="text-right text-slate-900 dark:text-slate-200">
                  paiement unique, sans reconduction
                </dd>
              </div>
            </dl>
          </div>

          <Link
            to={`/subscribe?plan=${encodeURIComponent(plan.plan_id)}`}
            className="mt-2 inline-flex items-center gap-1.5 text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Changer de formule
          </Link>
        </section>

        {/* ===== Code promo ===== */}
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Code promo
          </h2>
          <div className="flex gap-2">
            <Input
              className="h-10"
              placeholder="Saisis ton code (facultatif)"
              value={promoInput}
              onChange={(e) => setPromoInput(e.target.value.toUpperCase())}
              aria-label="Code promo"
            />
            <Button
              type="button"
              variant="outline"
              className="h-10 shrink-0"
              onClick={applyPromo}
              disabled={promoChecking || !promoInput.trim()}
            >
              {promoChecking ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Appliquer'}
            </Button>
          </div>
          {promoMessage && (
            <p className={`mt-2 text-sm ${promoMessage.ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
              {promoMessage.text}
            </p>
          )}
        </section>

        {/* ===== Total et paiement ===== */}
        <section className="rounded-lg border border-slate-200 p-4 dark:border-slate-700">
          {promo && (
            <div className="mb-2 flex justify-between text-sm text-muted-foreground">
              <span>Remise {promo.code}</span>
              <span>− {formatPrice(promo.discount_amount, plan.currency)}</span>
            </div>
          )}
          <div className="flex items-baseline justify-between">
            <span className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Total</span>
            <span className="font-heading text-2xl font-bold text-slate-900 dark:text-white">
              {formatPrice(total, plan.currency)}
            </span>
          </div>

          <div className="mt-4 space-y-3">
            <FormError>{error}</FormError>
            <Button className="h-11 w-full" onClick={pay} disabled={paying}>
              {paying
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Ouverture du paiement…</>
                : `Payer ${formatPrice(total, plan.currency)}`}
            </Button>
            <p className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
              <Lock className="h-3.5 w-3.5" /> Tu vas être redirigé vers la page sécurisée de notre
              prestataire de paiement.
            </p>
          </div>
        </section>

        <p className="text-center text-xs text-muted-foreground">
          Aucune donnée bancaire n'est stockée sur nos serveurs.{' '}
          <Link to="/politique-remboursement" className="underline hover:text-foreground">
            Politique de remboursement
          </Link>
        </p>
      </div>
    </FunnelShell>
  );
}
