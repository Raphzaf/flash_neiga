import React, { useState } from "react";
import axios from "axios";
import { HYP_CONFIG } from '../config/hypConfig';
import { useAuth } from "../context/AuthContext";
import {
  Zap, FileCheck, Layers, LineChart, BookOpen, Sparkles, History,
  Crown, Check, Star, ShieldCheck, MonitorSmartphone, GraduationCap, Car, Gift,
  ArrowRight, Loader2, MessageCircle, BadgeCheck,
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
    alert(`❌ Erreur de paiement : ${e?.response?.data?.detail || 'Erreur inconnue'}`);
  }
}

const HIGHLIGHTS = [
  { icon: FileCheck, label: "Questions officielles du Code de la route israélien" },
  { icon: Layers, label: "Des dizaines de séries de code" },
  { icon: LineChart, label: "Suivi intelligent et individualisé" },
  { icon: BookOpen, label: "Cours clairs et fiches de code" },
  { icon: Sparkles, label: "Flashcards pour réviser l'essentiel" },
  { icon: History, label: "Historique des questions" },
];

const PROF_TOPICS = [
  "Comprendre une règle de priorité.",
  "Interpréter un panneau de signalisation.",
  "Analyser une erreur commise pendant un exercice.",
  "Répondre à toutes tes questions sur le Code de la route israélien.",
];

const BASIC_FEATURES = [
  { text: "Questions officielles du Code de la route israélien" },
  { text: "Des dizaines de séries de code" },
  { text: "Historique des questions" },
  { text: "Fiches de révision et cours" },
  { text: "Suivi de progression" },
  { text: "Correction automatique et immédiate après chaque erreur commise" },
  {
    text: "Plateforme e-learning complète",
    sub: ["Cours de code de la route", "Fiches de révision", "Préparation à l'examen théorique et aux leçons de conduite"],
  },
  { text: "Interface claire et intuitive" },
];

const PREMIUM_FEATURES = [
  { text: "Tout le contenu de la formule Basic", strong: true },
  { text: "Coach IA pédagogique personnel — un prof de conduite disponible 24h/24", strong: true },
  {
    text: "Plateforme e-learning complète",
    sub: ["Cours de code de la route", "Fiches de révision", "Préparation à l'examen théorique et aux leçons de conduite"],
  },
  { text: "Suivi personnalisé de votre progression" },
  { text: "Historique de toutes tes erreurs pour les retravailler jusqu'à leur parfaite maîtrise" },
];

const TRUST = [
  { icon: BadgeCheck, title: "Contenu parfait en français", desc: "100 % conforme au Code de la route israélien" },
  { icon: ShieldCheck, title: "Plateforme sécurisée", desc: "Données protégées" },
  { icon: MonitorSmartphone, title: "Accessible partout", desc: "Ordinateur et smartphone, 24h/24" },
  { icon: GraduationCap, title: "Pédagogie française de référence", desc: "Méthode nouvelle, moderne et vivante" },
];

function FeatureItem({ item, accent }) {
  const color = accent === 'gold' ? 'text-yellow-600' : 'text-sky-600';
  return (
    <li className="flex flex-col gap-1">
      <div className="flex items-start gap-2">
        <Check className={`h-4 w-4 mt-0.5 shrink-0 ${color}`} />
        <span className={`text-sm ${item.strong ? 'font-semibold' : ''} text-slate-700 dark:text-slate-200`}>{item.text}</span>
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

function DurationOptions({ options, selected, onSelect, accent }) {
  const ring = accent === 'gold' ? 'ring-yellow-400 border-yellow-400' : 'ring-sky-400 border-sky-400';
  return (
    <div className="grid grid-cols-3 gap-2">
      {options.map((opt) => {
        const isSel = selected === opt.planId;
        return (
          <button
            key={opt.planId}
            type="button"
            onClick={() => onSelect(opt.planId)}
            className={`rounded-xl border-2 p-2.5 text-center transition-all ${
              isSel ? `bg-white dark:bg-slate-900 ${ring} ring-2 shadow` : 'border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-slate-900/60 hover:border-slate-300'
            }`}
            aria-pressed={isSel}
          >
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{opt.duration}</div>
            <div className="text-xl font-extrabold text-slate-900 dark:text-white">{opt.price} ₪</div>
          </button>
        );
      })}
    </div>
  );
}

function Pricing() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(null);
  const [basicSel, setBasicSel] = useState(HYP_CONFIG.plans.BASIC.DAYS_30);
  const [premiumSel, setPremiumSel] = useState(HYP_CONFIG.plans.PREMIUM.DAYS_30);

  const checkout = async (planId) => {
    setLoading(planId);
    try {
      await startHypCheckout(planId, user?.email || null, user?.id || null);
    } finally {
      setLoading(null);
    }
  };

  const basicOptions = [
    { planId: HYP_CONFIG.plans.BASIC.DAYS_14, price: 99, duration: '14 jours' },
    { planId: HYP_CONFIG.plans.BASIC.DAYS_21, price: 139, duration: '21 jours' },
    { planId: HYP_CONFIG.plans.BASIC.DAYS_30, price: 179, duration: '30 jours' },
  ];
  const premiumOptions = [
    { planId: HYP_CONFIG.plans.PREMIUM.DAYS_14, price: 139, duration: '14 jours' },
    { planId: HYP_CONFIG.plans.PREMIUM.DAYS_21, price: 189, duration: '21 jours' },
    { planId: HYP_CONFIG.plans.PREMIUM.DAYS_30, price: 229, duration: '30 jours' },
  ];

  return (
    <div className="min-h-screen bg-[#0c1a2e] text-white relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-sky-500/10 blur-3xl" />
        <div className="absolute top-1/3 -right-24 w-96 h-96 rounded-full bg-yellow-400/10 blur-3xl" />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-4 py-6 space-y-12">

        {/* Marque + hero */}
        <div>
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-yellow-400 flex items-center justify-center shadow-lg shadow-yellow-400/30">
                <Zap className="h-5 w-5 text-slate-900" />
              </div>
              <div className="leading-tight">
                <div className="text-lg font-extrabold">FlashNeiga</div>
                <div className="text-[11px] text-yellow-300 font-semibold uppercase tracking-wide">
                  LA plateforme de référence
                </div>
              </div>
            </div>
            <a href="/login" className="text-sm text-white/70 hover:text-white underline underline-offset-4">Se connecter</a>
          </div>

          <div className="max-w-2xl">
            <h1 className="text-3xl md:text-5xl font-extrabold leading-tight">
              Apprends plus <span className="text-yellow-400">vite</span>.<br />
              Comprends <span className="text-yellow-400">mieux</span>.<br />
              Réussis du premier coup.
            </h1>
            <p className="mt-4 text-sm md:text-base text-white/75">
              FlashNeiga est <strong>LA</strong> plateforme de référence dédiée aux francophones. Portée par une pédagogie
              française reconnue pour son excellence, nous accompagnons et formons les élèves en Israël, en France et
              partout dans le monde vers la réussite du Code de la route israélien.
            </p>
          </div>
        </div>

        {/* Bandeau des points forts */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {HIGHLIGHTS.map(({ icon: Icon, label }, i) => (
            <div key={i} className="flex items-center gap-3 rounded-2xl bg-white/[0.06] border border-white/10 p-3">
              <div className="h-10 w-10 rounded-xl bg-yellow-400/15 text-yellow-300 flex items-center justify-center shrink-0">
                <Icon className="h-5 w-5" />
              </div>
              <span className="text-xs md:text-sm text-white/85">{label}</span>
            </div>
          ))}
        </div>

        {/* Professeur de conduite particulier */}
        <div className="rounded-3xl bg-white/[0.06] border border-white/10 p-6 md:p-8">
          <div className="flex items-center gap-3 mb-4">
            <div className="h-12 w-12 rounded-2xl bg-yellow-400 text-slate-900 flex items-center justify-center shadow-lg shadow-yellow-400/30">
              <GraduationCap className="h-6 w-6" />
            </div>
            <h2 className="text-2xl font-extrabold">Ton professeur de conduite particulier</h2>
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <p className="text-white/80 mb-3">Ton professeur est là pour t'aider sur différentes notions comme :</p>
              <ul className="space-y-2">
                {PROF_TOPICS.map((t, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-white/90">
                    <Check className="h-4 w-4 mt-0.5 shrink-0 text-yellow-400" /> {t}
                  </li>
                ))}
              </ul>
            </div>
            <div className="rounded-2xl bg-gradient-to-br from-sky-500/20 to-yellow-400/10 border border-white/10 p-5 flex flex-col justify-center">
              <MessageCircle className="h-7 w-7 text-yellow-300 mb-2" />
              <p className="text-sm text-white/90">
                Pose tes questions à ton professeur de conduite <strong>sous forme de chat</strong> : questions
                <strong> illimitées</strong> et réponses sous forme de leçon de code claires et précises, pour un meilleur apprentissage.
              </p>
            </div>
          </div>
        </div>

        {/* Formules */}
        <div>
          <h2 className="text-center text-2xl md:text-3xl font-extrabold mb-6">
            Choisis ta formule et avance à ton rythme
          </h2>

          <div className="grid md:grid-cols-2 gap-6 items-start">

            {/* BASIC */}
            <div className="rounded-3xl bg-white dark:bg-slate-800 text-slate-900 dark:text-white p-6 shadow-xl border border-white/10">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-11 w-11 rounded-2xl bg-sky-100 text-sky-600 flex items-center justify-center">
                  <Zap className="h-6 w-6" />
                </div>
                <h3 className="text-xl font-extrabold">Formule Basic</h3>
              </div>
              <DurationOptions options={basicOptions} selected={basicSel} onSelect={setBasicSel} accent="sky" />
              <ul className="mt-5 space-y-3">
                {BASIC_FEATURES.map((f, i) => <FeatureItem key={i} item={f} accent="sky" />)}
              </ul>
              <button
                onClick={() => checkout(basicSel)}
                disabled={loading === basicSel}
                className="mt-6 w-full rounded-xl bg-sky-500 hover:bg-sky-600 text-white font-bold py-3 uppercase tracking-wide transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
              >
                {loading === basicSel ? <Loader2 className="h-5 w-5 animate-spin" /> : <>Je commence <ArrowRight className="h-4 w-4" /></>}
              </button>
            </div>

            {/* PREMIUM */}
            <div className="relative rounded-3xl bg-white dark:bg-slate-800 text-slate-900 dark:text-white p-6 shadow-2xl border-2 border-yellow-400">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-yellow-400 text-slate-900 text-xs font-bold px-4 py-1 flex items-center gap-1 shadow">
                <Star className="h-3.5 w-3.5 fill-slate-900" /> LA PLUS CHOISIE
              </div>
              <div className="flex items-center gap-3 mb-4 mt-2">
                <div className="h-11 w-11 rounded-2xl bg-yellow-100 text-yellow-600 flex items-center justify-center">
                  <Crown className="h-6 w-6" />
                </div>
                <h3 className="text-xl font-extrabold">Formule Premium</h3>
              </div>
              <DurationOptions options={premiumOptions} selected={premiumSel} onSelect={setPremiumSel} accent="gold" />
              <ul className="mt-5 space-y-3">
                {PREMIUM_FEATURES.map((f, i) => <FeatureItem key={i} item={f} accent="gold" />)}
              </ul>
              <button
                onClick={() => checkout(premiumSel)}
                disabled={loading === premiumSel}
                className="mt-6 w-full rounded-xl bg-yellow-400 hover:bg-yellow-300 text-slate-900 font-bold py-3 uppercase tracking-wide transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
              >
                {loading === premiumSel ? <Loader2 className="h-5 w-5 animate-spin" /> : <>Je passe en Premium <ArrowRight className="h-4 w-4" /></>}
              </button>
            </div>
          </div>

          {/* Offre spéciale */}
          <div className="mt-6 rounded-3xl bg-gradient-to-r from-yellow-400 to-amber-400 text-slate-900 p-5 md:p-6 flex flex-col md:flex-row items-center gap-4 shadow-lg shadow-yellow-400/20">
            <div className="h-14 w-14 rounded-2xl bg-slate-900/10 flex items-center justify-center shrink-0">
              <Gift className="h-7 w-7" />
            </div>
            <div className="flex-1 text-center md:text-left">
              <div className="text-xs font-bold uppercase tracking-wide">Offre spéciale — Premium 30 jours</div>
              <div className="text-lg font-extrabold flex items-center justify-center md:justify-start gap-2">
                <Car className="h-5 w-5" /> 1 séance de conduite offerte
              </div>
              <div className="text-sm">pour les 100 premiers utilisateurs de l'offre Premium 30 jours !</div>
            </div>
          </div>

          <p className="mt-4 text-center text-sm text-white/70">
            Le prix moyen par jour est entre <strong className="text-yellow-300">5 et 9 ₪</strong> selon la formule choisie.
          </p>
        </div>

        {/* Réassurance */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {TRUST.map(({ icon: Icon, title, desc }, i) => (
            <div key={i} className="rounded-2xl bg-white/[0.06] border border-white/10 p-4 text-center">
              <Icon className="h-7 w-7 text-yellow-400 mx-auto mb-2" />
              <div className="text-sm font-bold">{title}</div>
              <div className="text-xs text-white/70 mt-1">{desc}</div>
            </div>
          ))}
        </div>

        {/* CTA bas de page */}
        <div className="rounded-3xl bg-yellow-400 text-slate-900 p-6 text-center font-extrabold text-lg md:text-xl">
          Rejoins FlashNeiga dès aujourd'hui et prends la route de la réussite ! 🚗💨
        </div>
      </div>
    </div>
  );
}

export default Pricing;
