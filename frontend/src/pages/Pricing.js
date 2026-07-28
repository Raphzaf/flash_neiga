import React, { useState } from "react";
import axios from "axios";
import { HYP_CONFIG } from '../config/hypConfig';
import { useAuth } from "../context/AuthContext";
import {
  Zap, Crown, Target, Check, Star, ShieldCheck, Clock, Headphones, Bot, ArrowRight, Loader2,
} from "lucide-react";

async function startHypCheckout(planId, userEmail = null, userId = null) {
  try {
    const res = await axios.post('/api/payments/hyp/create-payment', {
      plan_id: planId, user_email: userEmail, user_id: userId,
    });
    const paymentUrl = res.data?.payment_url;
    if (paymentUrl) {
      window.location.href = paymentUrl;
    } else {
      alert('❌ Erreur : URL de paiement non disponible');
    }
  } catch (e) {
    const errorDetail = e?.response?.data?.detail || 'Erreur inconnue';
    alert(`❌ Erreur de paiement : ${errorDetail}`);
  }
}

const STANDARD_FEATURES = [
  { text: "Questions officielles du Code de la route israélien" },
  { text: "Correction automatique et immédiate" },
  { text: "« Pourquoi ai-je fait cette erreur ? » — une explication claire apparaît après chaque mauvaise réponse pour comprendre et progresser" },
  {
    text: "Plateforme E-learning complète",
    sub: [
      "Cours de Code de la route",
      "Fiches de révision",
      "Explications illustrées",
      "Préparation à l'examen théorique et aux leçons de conduite",
    ],
  },
  { text: "Historique de toutes vos erreurs pour les retravailler jusqu'à leur parfaite maîtrise" },
];

const PREMIUM_FEATURES = [
  { text: "Questions officielles du Code de la route israélien" },
  { text: "Correction automatique et immédiate" },
  { text: "Explication détaillée de chaque erreur" },
  {
    text: "Plateforme E-learning complète",
    sub: [
      "Cours de Code de la route",
      "Fiches de révision",
      "Explications illustrées",
      "Préparation théorique et aux leçons de conduite",
    ],
  },
  { text: "Suivi personnalisé de votre progression" },
  { text: "Historique de toutes vos erreurs pour les retravailler jusqu'à leur parfaite maîtrise" },
];

const COACH_BULLETS = [
  "Il t'explique chaque règle du Code de manière ultra simple",
  "Des explications adaptées à ton niveau",
  "Un coaching pour progresser plus vite",
  "Il te fait comprendre facilement tes erreurs",
];

function FeatureItem({ item }) {
  return (
    <li className="flex flex-col gap-1">
      <div className="flex items-start gap-2">
        <Check className="h-4 w-4 mt-0.5 shrink-0 text-emerald-500" />
        <span className="text-sm text-slate-700 dark:text-slate-200">{item.text}</span>
      </div>
      {item.sub && (
        <ul className="ml-6 mt-1 space-y-1">
          {item.sub.map((s, i) => (
            <li key={i} className="flex items-start gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span className="mt-0.5">•</span><span>{s}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

// Sélecteur de durée (14 / 30 jours) — deux options, une seule sélectionnée.
function PriceOptions({ options, selected, onSelect, accent }) {
  const ring = accent === 'gold' ? 'ring-yellow-400 border-yellow-400' : 'ring-sky-400 border-sky-400';
  return (
    <div className="grid grid-cols-2 gap-3">
      {options.map((opt) => {
        const isSel = selected === opt.planId;
        return (
          <button
            key={opt.planId}
            type="button"
            onClick={() => onSelect(opt.planId)}
            className={`rounded-xl border-2 p-3 text-center transition-all ${
              isSel
                ? `bg-white dark:bg-slate-900 ${ring} ring-2 shadow`
                : 'border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-slate-900/60 hover:border-slate-300'
            }`}
            aria-pressed={isSel}
          >
            <div className="text-2xl font-extrabold text-slate-900 dark:text-white">{opt.price} ₪</div>
            <div className="text-xs text-slate-500 dark:text-slate-400">/ {opt.duration}</div>
          </button>
        );
      })}
    </div>
  );
}

function Pricing() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(null);
  const [standardSel, setStandardSel] = useState(HYP_CONFIG.plans.STANDARD.DAYS_30);
  const [premiumSel, setPremiumSel] = useState(HYP_CONFIG.plans.PREMIUM.DAYS_30);

  const checkout = async (planId) => {
    setLoading(planId);
    try {
      await startHypCheckout(planId, user?.email || null, user?.id || null);
    } finally {
      setLoading(null);
    }
  };

  const standardOptions = [
    { planId: HYP_CONFIG.plans.STANDARD.DAYS_14, price: 79, duration: '14 jours' },
    { planId: HYP_CONFIG.plans.STANDARD.DAYS_30, price: 129, duration: '30 jours' },
  ];
  const premiumOptions = [
    { planId: HYP_CONFIG.plans.PREMIUM.DAYS_14, price: 109, duration: '14 jours' },
    { planId: HYP_CONFIG.plans.PREMIUM.DAYS_30, price: 159, duration: '30 jours' },
  ];

  return (
    <div className="min-h-screen bg-[#0c1a2e] text-white relative overflow-hidden">
      {/* Accents lumineux d'arrière-plan (cohérents avec le reste du site) */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-sky-500/10 blur-3xl" />
        <div className="absolute bottom-0 -right-24 w-96 h-96 rounded-full bg-yellow-400/10 blur-3xl" />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-4 py-6">
        {/* Barre de marque */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-yellow-400 flex items-center justify-center shadow-lg shadow-yellow-400/30">
              <Zap className="h-5 w-5 text-slate-900" />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-bold tracking-wide text-white/90">בריין טרטור</div>
              <div className="text-xs text-yellow-300 font-semibold">Flashneiga</div>
            </div>
          </div>
          <a href="#plans" className="rounded-full bg-yellow-400 text-slate-900 font-bold text-sm px-5 py-2 shadow-lg shadow-yellow-400/30 hover:bg-yellow-300 transition-colors">
            Commencer
          </a>
        </div>

        {/* Hero */}
        <div className="text-center max-w-2xl mx-auto mb-8">
          <h1 className="text-3xl md:text-4xl font-extrabold leading-tight">
            Choisissez la formule<br />
            <span className="text-yellow-400">qui vous correspond</span>
          </h1>
          <p className="mt-3 text-sm md:text-base text-white/70">
            Réussissez votre Code de la route israélien du 1er coup grâce à une méthode moderne, interactive et efficace.
          </p>
        </div>

        {/* Bandeau 95% */}
        <div className="mb-10 rounded-2xl bg-gradient-to-r from-yellow-400 to-amber-400 text-slate-900 p-4 flex items-start gap-3 shadow-lg shadow-yellow-400/20 max-w-3xl mx-auto">
          <div className="h-9 w-9 rounded-full bg-slate-900/10 flex items-center justify-center shrink-0">
            <Target className="h-5 w-5 text-slate-900" />
          </div>
          <p className="text-sm font-medium">
            Plus de <strong>95 %</strong> de nos élèves réussissent grâce à une méthode basée sur la compréhension, et non sur le simple apprentissage par cœur.
          </p>
        </div>

        {/* Cartes */}
        <div id="plans" className="grid md:grid-cols-2 gap-6 items-start">

          {/* Formule Standard */}
          <div className="rounded-3xl bg-white dark:bg-slate-800 text-slate-900 dark:text-white p-6 shadow-xl border border-white/10">
            <div className="flex items-center gap-3 mb-4">
              <div className="h-11 w-11 rounded-2xl bg-sky-100 text-sky-600 flex items-center justify-center">
                <Zap className="h-6 w-6" />
              </div>
              <h2 className="text-xl font-extrabold">Formule Standard</h2>
            </div>

            <PriceOptions options={standardOptions} selected={standardSel} onSelect={setStandardSel} accent="sky" />

            <div className="mt-5">
              <div className="text-sm font-bold text-slate-900 dark:text-white mb-2">Inclus :</div>
              <ul className="space-y-3">
                {STANDARD_FEATURES.map((f, i) => <FeatureItem key={i} item={f} />)}
              </ul>
            </div>

            <button
              onClick={() => checkout(standardSel)}
              disabled={loading === standardSel}
              className="mt-6 w-full rounded-xl bg-sky-500 hover:bg-sky-600 text-white font-bold py-3 uppercase tracking-wide transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {loading === standardSel ? <Loader2 className="h-5 w-5 animate-spin" /> : <>Commencer <ArrowRight className="h-4 w-4" /></>}
            </button>
          </div>

          {/* Formule Premium */}
          <div className="relative rounded-3xl bg-white dark:bg-slate-800 text-slate-900 dark:text-white p-6 shadow-2xl border-2 border-yellow-400">
            {/* Ruban */}
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-yellow-400 text-slate-900 text-xs font-bold px-4 py-1 flex items-center gap-1 shadow">
              <Star className="h-3.5 w-3.5 fill-slate-900" /> LA FORMULE LA PLUS CHOISIE
            </div>

            <div className="flex items-center gap-3 mb-4 mt-2">
              <div className="h-11 w-11 rounded-2xl bg-yellow-100 text-yellow-600 flex items-center justify-center">
                <Crown className="h-6 w-6" />
              </div>
              <h2 className="text-xl font-extrabold">Formule Premium</h2>
            </div>

            <PriceOptions options={premiumOptions} selected={premiumSel} onSelect={setPremiumSel} accent="gold" />

            <div className="mt-5">
              <div className="text-sm font-bold text-slate-900 dark:text-white mb-2">Tout le contenu de la Formule Standard</div>
              <ul className="space-y-3">
                {PREMIUM_FEATURES.map((f, i) => <FeatureItem key={i} item={f} />)}
              </ul>
            </div>

            {/* Bonus Coach IA */}
            <div className="mt-5 rounded-2xl bg-[#0c1a2e] text-white p-4">
              <div className="inline-flex items-center gap-1 rounded-full bg-yellow-400 text-slate-900 text-[11px] font-bold px-2.5 py-0.5 mb-2">
                <Bot className="h-3.5 w-3.5" /> BONUS COACH IA
              </div>
              <div className="font-bold text-lg">Votre Coach IA personnel</div>
              <p className="text-sm text-white/80 mt-1">
                Un véritable prof pédagogique disponible <strong>24h/24 et 7j/7</strong>. Pose-lui toutes tes questions à toute heure, il te répond instantanément.
              </p>
              <ul className="mt-3 space-y-1.5">
                {COACH_BULLETS.map((b, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-white/90">
                    <Check className="h-4 w-4 mt-0.5 shrink-0 text-yellow-400" /> {b}
                  </li>
                ))}
              </ul>
            </div>

            <button
              onClick={() => checkout(premiumSel)}
              disabled={loading === premiumSel}
              className="mt-6 w-full rounded-xl bg-yellow-400 hover:bg-yellow-300 text-slate-900 font-bold py-3 uppercase tracking-wide transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {loading === premiumSel ? <Loader2 className="h-5 w-5 animate-spin" /> : <>Choisir Premium <ArrowRight className="h-4 w-4" /></>}
            </button>
          </div>
        </div>

        {/* Réassurance */}
        <div className="mt-10 grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
          <div className="flex flex-col items-center gap-1 text-white/80">
            <ShieldCheck className="h-6 w-6 text-yellow-400" />
            <span className="text-sm font-medium">Paiement 100 % sécurisé</span>
          </div>
          <div className="flex flex-col items-center gap-1 text-white/80">
            <Clock className="h-6 w-6 text-yellow-400" />
            <span className="text-sm font-medium">Accès immédiat après paiement</span>
          </div>
          <div className="flex flex-col items-center gap-1 text-white/80">
            <Headphones className="h-6 w-6 text-yellow-400" />
            <span className="text-sm font-medium">Support réactif garanti</span>
          </div>
        </div>

        <div className="mt-8 text-center">
          <a href="/login" className="text-sm text-white/60 hover:text-white underline underline-offset-4">
            J'ai déjà un compte — me connecter
          </a>
        </div>
      </div>
    </div>
  );
}

export default Pricing;
