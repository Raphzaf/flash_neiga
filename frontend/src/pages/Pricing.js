import React, { useState } from "react";
import axios from "axios";
import { HYP_CONFIG } from '../config/hypConfig';
import { useAuth } from "../context/AuthContext";
import {
  Zap, FileCheck, LineChart, BookOpen, HelpCircle, History,
  Crown, Check, Star, ShieldCheck, MonitorSmartphone, GraduationCap,
  ArrowRight, Loader2, BadgeCheck,
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
  { icon: FileCheck, label: "Questions officielles du Code de la route en Israël" },
  { icon: HelpCircle, label: "« Pourquoi ai-je fait cette erreur ? » Ta mini leçon de code explicative pour corriger ton erreur." },
  { icon: History, label: "Historique de TOUTES tes erreurs pour les revoir et les retravailler !" },
  { icon: LineChart, label: "Suis ta progression depuis le début !" },
  { icon: BookOpen, label: "Cours de code et Flashcards pour mémoriser l'essentiel." },
];

const PROF_TOPICS = [
  "Les règles de priorité",
  "Les intersections",
  "Les limitations de vitesse",
  "Les différentes familles de panneaux de signalisation",
  "Les dépassements",
  "Les erreurs les plus fréquentes aux examens",
];

// Mise en forme reprise à l'identique du document de la direction :
// jaune #ffff00, rouge #ff0000, gras et italique appliqués mot pour mot.
// Seule exception : sur la carte Premium (fond blanc), le jaune pur serait
// invisible — il y est donc assombri en doré, même teinte, lisible.
const YELLOW = "text-[#ffff00] italic";
const YELLOW_ON_WHITE = "text-[#b59500] italic";
const RED = "text-[#ff0000] italic";
const RED_BOLD = "text-[#ff0000] italic font-bold";

const STANDARD_FEATURES = [
  { text: "Questions officielles du Code de la route en Israël" },
  {
    text: <><span className={RED_BOLD}>Plateforme E-Learning</span> avec</>,
    sub: ["Cours de Code", "Explications illustrées", "Interface claire et intuitive", "Préparation à l'Examen Théorique"],
  },
  { text: "Correction automatique et immédiate de ton erreur" },
  { text: "Suivi personnalisé de ta progression !" },
  {
    text: (
      <>
        <span className="italic">« Pourquoi ai-je fait cette erreur ? »</span> Ta mini leçon explicative
        de ton erreur !
      </>
    ),
  },
  { text: "Historique de toutes tes erreurs pour les retravailler !" },
];

const PREMIUM_FEATURES = [
  { text: <span className="italic">Toutes les offres de la formule Standard sont incluses.</span> },
  {
    text: (
      <>
        <span className={YELLOW_ON_WHITE}>FLASH</span> <span className="italic">Premium</span> : pose tes
        questions <span className={RED}>illimitées 24/24 7/7</span> et ton professeur de code te répond
        directement et clairement sous forme de mini leçon de code de façon précise, avec des illustrations
        et des mises en situations réelles, ce qui te garantira une progression rapide et une forte
        probabilité de réussite à ton examen théorique !
      </>
    ),
  },
];

const TRUST = [
  { icon: BadgeCheck, title: "Contenu parfait en français", desc: "100 % conforme au Code de la route israélien" },
  { icon: ShieldCheck, title: "Plateforme sécurisée", desc: <span className="italic">Paiement sécurisé et données protégées</span> },
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
  const [standardSel, setStandardSel] = useState(HYP_CONFIG.plans.BASIC.DAYS_30);
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
    { planId: HYP_CONFIG.plans.BASIC.DAYS_14, price: 69, duration: '14 jours' },
    { planId: HYP_CONFIG.plans.BASIC.DAYS_21, price: 89, duration: '21 jours' },
    { planId: HYP_CONFIG.plans.BASIC.DAYS_30, price: 99, duration: '30 jours' },
  ];
  const premiumOptions = [
    { planId: HYP_CONFIG.plans.PREMIUM.DAYS_14, price: 119, duration: '14 jours' },
    { planId: HYP_CONFIG.plans.PREMIUM.DAYS_21, price: 139, duration: '21 jours' },
    { planId: HYP_CONFIG.plans.PREMIUM.DAYS_30, price: 149, duration: '30 jours' },
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
                <div className="text-lg font-extrabold">FLASHNEIGA</div>
                <div className="text-[11px] text-yellow-300 font-semibold uppercase tracking-wide">
                  LA plateforme de référence
                </div>
              </div>
            </div>
            <a href="/login" className="text-sm text-white/70 hover:text-white underline underline-offset-4">Se connecter</a>
          </div>

          <div className="max-w-2xl">
            <p className={`text-sm md:text-base font-semibold mb-4 ${YELLOW}`}>
              La Plateforme de Référence des francophones pour réussir rapidement le Code de la route
              en Israël.
            </p>
            <h1 className="text-3xl md:text-5xl font-extrabold leading-tight">
              Apprends <span className={YELLOW}>mieux</span>.<br />
              Comprends tes <span className={YELLOW}>erreurs</span>.<br />
              <span className={RED}>Réussis ton code du premier coup !</span>
            </h1>
            <p className="mt-4 text-sm md:text-base text-white/75">
              <span className={RED_BOLD}>FLASHNEIGA</span> est heureux de vous faire découvrir
              sa <strong>Formation Théorique au Code de la route en
              Israël</strong>. Nous accompagnons et formons nos élèves francophones à l'apprentissage continu des
              différentes règles du Code de la route en Israël (signalisation, panneaux, règles de priorité...) grâce à
              notre pédagogie et notre méthode d'enseignement à la française jusqu'à l'obtention du code en un minimum
              de temps.
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

        {/* Professeur particulier */}
        <div className="rounded-3xl bg-white/[0.06] border border-white/10 p-6 md:p-8">
          <div className="flex items-center gap-3 mb-4">
            <div className="h-12 w-12 rounded-2xl bg-yellow-400 text-slate-900 flex items-center justify-center shadow-lg shadow-yellow-400/30">
              <GraduationCap className="h-6 w-6" />
            </div>
            <h2 className="text-2xl font-extrabold">
              Ton professeur particulier <em className={RED}>24/24 7/7</em>
            </h2>
          </div>
          <p className="text-white/80 mb-4">
            t'accompagne pour te faire progresser rapidement sur toutes les notions importantes pour réussir ton
            Examen Théorique du Code comme notamment :
          </p>
          <ul className="grid sm:grid-cols-2 gap-x-6 gap-y-2">
            {PROF_TOPICS.map((t, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-white/90">
                <Check className="h-4 w-4 mt-0.5 shrink-0 text-yellow-400" /> {t}
              </li>
            ))}
          </ul>
        </div>

        {/* Formules */}
        <div>
          <h2 className="text-center text-2xl md:text-3xl font-extrabold mb-6">
            Choisis ta formule et avance à ton rythme
          </h2>

          <div className="grid md:grid-cols-2 gap-6 items-start">

            {/* STANDARD */}
            <div className="rounded-3xl bg-white dark:bg-slate-800 text-slate-900 dark:text-white p-6 shadow-xl border border-white/10">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-11 w-11 rounded-2xl bg-sky-100 text-sky-600 flex items-center justify-center">
                  <Zap className="h-6 w-6" />
                </div>
                <h3 className={`text-xl font-extrabold ${RED}`}>Formule Standard</h3>
              </div>
              <DurationOptions options={standardOptions} selected={standardSel} onSelect={setStandardSel} accent="sky" />
              <ul className="mt-5 space-y-3">
                {STANDARD_FEATURES.map((f, i) => <FeatureItem key={i} item={f} accent="sky" />)}
              </ul>
              <button
                onClick={() => checkout(standardSel)}
                disabled={loading === standardSel}
                className="mt-6 w-full rounded-xl bg-sky-500 hover:bg-sky-600 text-white font-bold py-3 uppercase tracking-wide transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
              >
                {loading === standardSel ? <Loader2 className="h-5 w-5 animate-spin" /> : <>Je commence <ArrowRight className="h-4 w-4" /></>}
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
                <h3 className={`text-xl font-extrabold ${RED}`}>Formule Premium</h3>
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

          <p className="mt-6 text-center text-sm text-white/70">
            Le prix moyen par jour est entre <strong className="text-yellow-300">3 et 9 ₪</strong> selon la formule choisie.
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
        <div className="rounded-3xl bg-yellow-400 text-slate-900 p-6 text-center font-extrabold text-lg md:text-xl flex flex-wrap items-center justify-center gap-2">
          <span>
            Rejoins <span className={RED}>FLASHNEIGA</span> et obtiens ton code à la vitesse de l'éclair
          </span>
          <Zap className="h-6 w-6 fill-slate-900" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}

export default Pricing;
