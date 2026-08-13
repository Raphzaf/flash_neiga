import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import FunnelShell from '../components/funnel/FunnelShell';
import { FormError, Notice, inputClass, primaryButtonClass } from '../components/funnel/fields';
import { formatDate, formatPrice, forgetPlan, rememberPlan, readRememberedPlan } from '../lib/funnel';
import { ArrowLeft, CreditCard, Loader2, Lock, ShieldCheck, Tag } from 'lucide-react';

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
      const status = err?.response?.status;
      if (status === 401) {
        // Session perdue pendant le parcours : on repasse par la connexion, la
        // formule est conservée.
        navigate(`/login?reason=session`, { replace: true });
        return;
      }
      setError(err?.response?.data?.detail || "Le paiement n'a pas pu être lancé. Réessaie dans un instant.");
      setPaying(false);
    }
  };

  if (loading || notFound) {
    return (
      <FunnelShell step={3} width="md" title="Paiement">
        <div className="flex items-center justify-center gap-3 py-10 text-white/80">
          <Loader2 className="h-5 w-5 animate-spin" /> Préparation de ta commande…
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
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white/70">Ton abonnement</h2>
          <div className="rounded-2xl border border-white/20 bg-white/[0.08] p-4">
            <div className="flex items-baseline justify-between gap-4">
              <div>
                <div className="text-base font-bold text-white">Formule {plan.label}</div>
                <div className="text-sm text-white/70">{plan.period} d'accès complet</div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-extrabold text-white">{formatPrice(plan.amount, plan.currency)}</div>
              </div>
            </div>

            <dl className="mt-4 space-y-2 border-t border-white/15 pt-4 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="shrink-0 text-white/70">Compte</dt>
                {/* Les adresses longues doivent rester dans la carte en mobile. */}
                <dd className="break-all text-right font-medium text-white">{user?.email || '—'}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-white/70">Accès</dt>
                <dd className="font-medium text-white">
                  dès le paiement, jusqu'au {formatDate(endDate)}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-white/70">Facturation</dt>
                <dd className="font-medium text-white">paiement unique, sans reconduction</dd>
              </div>
            </dl>
          </div>

          <Link
            to={`/subscribe?plan=${encodeURIComponent(plan.plan_id)}`}
            className="mt-2 inline-flex items-center gap-1.5 text-xs text-white/70 underline underline-offset-4 hover:text-white"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Changer de formule
          </Link>
        </section>

        {/* ===== Code promo ===== */}
        <section>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white/70">Code promo</h2>
          <div className="flex gap-2">
            <input
              className={inputClass}
              placeholder="Saisis ton code (facultatif)"
              value={promoInput}
              onChange={(e) => setPromoInput(e.target.value.toUpperCase())}
              aria-label="Code promo"
            />
            <button
              type="button"
              onClick={applyPromo}
              disabled={promoChecking || !promoInput.trim()}
              className="shrink-0 rounded-xl border border-white/30 bg-white/10 px-4 text-sm font-semibold text-white transition-colors hover:bg-white/20 disabled:opacity-50"
            >
              {promoChecking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Tag className="h-4 w-4" />}
            </button>
          </div>
          {promoMessage && (
            <p className={`mt-2 text-sm ${promoMessage.ok ? 'text-emerald-200' : 'text-red-200'}`}>
              {promoMessage.text}
            </p>
          )}
        </section>

        {/* ===== Total et paiement ===== */}
        <section className="rounded-2xl border border-white/20 bg-white/[0.08] p-4">
          {promo && (
            <div className="mb-2 flex justify-between text-sm text-white/70">
              <span>Remise {promo.code}</span>
              <span>− {formatPrice(promo.discount_amount, plan.currency)}</span>
            </div>
          )}
          <div className="flex items-baseline justify-between">
            <span className="text-sm font-semibold uppercase tracking-wider text-white/80">Total</span>
            <span className="text-3xl font-extrabold text-white">{formatPrice(total, plan.currency)}</span>
          </div>

          <FormError>{error}</FormError>

          <button type="button" onClick={pay} disabled={paying} className={`${primaryButtonClass} mt-4`}>
            {paying
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Ouverture du paiement…</>
              : <><CreditCard className="h-4 w-4" /> Payer {formatPrice(total, plan.currency)}</>}
          </button>

          <p className="mt-3 flex items-center justify-center gap-1.5 text-xs text-white/70">
            <Lock className="h-3.5 w-3.5" /> Tu vas être redirigé vers la page sécurisée de notre
            prestataire de paiement.
          </p>
        </section>

        <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-white/70">
          <span className="flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5" /> Paiement sécurisé</span>
          <span>Aucune donnée bancaire n'est stockée sur nos serveurs</span>
          <Link to="/politique-remboursement" className="underline hover:text-white">Politique de remboursement</Link>
        </div>
      </div>
    </FunnelShell>
  );
}
