import React, { useState } from "react";
import axios from "axios";
import { HYP_CONFIG } from '../config/hypConfig';
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import {
  Zap, FileCheck, LineChart, BookOpen, HelpCircle, History,
  Crown, Check, Star, ShieldCheck, MonitorSmartphone, GraduationCap,
  ArrowRight, Loader2, BadgeCheck, X, Eye, EyeOff, UserPlus, LogIn,
} from "lucide-react";

// Renvoie le statut HTTP en cas d'échec pour que l'appelant puisse réagir
// (401 = session perdue : on redemande le compte plutôt que d'afficher une
// erreur sèche).
async function startHypCheckout(planId, promoCode = null) {
  try {
    const res = await axios.post('/api/payments/hyp/create-payment', {
      plan_id: planId, promo_code: promoCode || null,
    });
    // Code offrant 100 % : aucun paiement, l'accès est déjà activé côté serveur.
    // L'identifiant de transaction suit, sinon la page de confirmation n'a rien
    // à afficher.
    if (res.data?.free) {
      window.location.href = `/payment/success?free=1&transaction_id=${res.data.transaction_id}`;
      return { ok: true };
    }
    const paymentUrl = res.data?.payment_url;
    if (paymentUrl) {
      window.location.href = paymentUrl;
      return { ok: true };
    }
    toast.error("URL de paiement indisponible. Réessaie dans un instant.");
    return { ok: false };
  } catch (e) {
    const status = e?.response?.status;
    if (status !== 401) {
      toast.error(`Erreur de paiement : ${e?.response?.data?.detail || 'erreur inconnue'}`);
    }
    return { ok: false, status };
  }
}

/**
 * Compte obligatoire AVANT le paiement.
 *
 * Un abonnement n'existe que rattaché à un compte : si l'élève paie sans en
 * avoir un, l'argent est encaissé mais aucun accès ne peut être ouvert, et on
 * lui demande ensuite de se connecter à un compte qu'il n'a jamais créé. Le
 * mot de passe est donc choisi ici, avant la redirection vers la banque, puis
 * le paiement reprend tout seul.
 */
function AccountGate({ planLabel, onClose, onReady }) {
  const { register, login } = useAuth();
  const [mode, setMode] = useState('register');   // register | login
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const isRegister = mode === 'register';

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    if (isRegister && password.length < 6) {
      setError("Ton mot de passe doit contenir au moins 6 caractères.");
      return;
    }
    setSubmitting(true);
    try {
      if (isRegister) {
        await register(email.trim(), password, firstName.trim(), lastName.trim());
      } else {
        await login(email.trim(), password);
      }
      onReady();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(
        detail ||
        (isRegister
          ? "Impossible de créer le compte. Cet email est peut-être déjà utilisé."
          : "Email ou mot de passe incorrect.")
      );
    } finally {
      setSubmitting(false);
    }
  };

  const field = "w-full rounded-xl bg-white/10 border border-white/15 px-3 py-2.5 text-sm text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-yellow-400";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="w-full max-w-md rounded-3xl bg-[#0c1a2e] border border-white/15 p-6 shadow-2xl my-8">
        <div className="flex items-start justify-between gap-4 mb-1">
          <h3 className="text-xl font-extrabold text-white">
            {isRegister ? 'Crée ton compte pour continuer' : 'Connecte-toi pour continuer'}
          </h3>
          <button type="button" onClick={onClose} aria-label="Fermer" className="text-white/60 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="text-sm text-white/70 mb-5">
          Ton abonnement <strong className="text-yellow-300">{planLabel}</strong> sera rattaché à ce compte.
          {isRegister && " Choisis ton mot de passe maintenant : c'est avec lui que tu te connecteras juste après le paiement."}
        </p>

        <form onSubmit={submit} className="space-y-3">
          {isRegister && (
            <div className="grid grid-cols-2 gap-3">
              <input className={field} placeholder="Prénom" autoComplete="given-name" autoFocus
                value={firstName} onChange={(e) => setFirstName(e.target.value)} required />
              <input className={field} placeholder="Nom" autoComplete="family-name"
                value={lastName} onChange={(e) => setLastName(e.target.value)} required />
            </div>
          )}
          <input className={field} type="email" placeholder="Ton email" autoComplete="email" inputMode="email"
            autoFocus={!isRegister} value={email} onChange={(e) => setEmail(e.target.value)} required />
          <div className="relative">
            <input
              className={`${field} pr-11`}
              type={showPassword ? 'text' : 'password'}
              placeholder={isRegister ? 'Mot de passe (6 caractères minimum)' : 'Ton mot de passe'}
              autoComplete={isRegister ? 'new-password' : 'current-password'}
              minLength={isRegister ? 6 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button type="button" onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-white/60 hover:text-white">
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>

          {error && <p className="text-sm text-red-300">{error}</p>}

          <button type="submit" disabled={submitting}
            className="w-full rounded-xl bg-yellow-400 hover:bg-yellow-300 text-slate-900 font-bold py-3 transition-colors flex items-center justify-center gap-2 disabled:opacity-60">
            {submitting
              ? <Loader2 className="h-5 w-5 animate-spin" />
              : <>{isRegister ? <UserPlus className="h-4 w-4" /> : <LogIn className="h-4 w-4" />} Continuer vers le paiement</>}
          </button>
        </form>

        <button type="button"
          onClick={() => { setMode(isRegister ? 'login' : 'register'); setError(null); }}
          className="mt-4 w-full text-sm text-white/70 hover:text-white underline underline-offset-4">
          {isRegister ? "J'ai déjà un compte" : "Je n'ai pas encore de compte"}
        </button>
      </div>
    </div>
  );
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
  const { user, logout } = useAuth();
  const [loading, setLoading] = useState(null);
  const [standardSel, setStandardSel] = useState(HYP_CONFIG.plans.BASIC.DAYS_30);
  const [premiumSel, setPremiumSel] = useState(HYP_CONFIG.plans.PREMIUM.DAYS_30);
  const [promoInput, setPromoInput] = useState('');
  const [promoApplied, setPromoApplied] = useState(null);
  const [promoMessage, setPromoMessage] = useState(null);
  const [promoChecking, setPromoChecking] = useState(false);
  // Formule choisie en attendant que l'élève ait un compte.
  const [pendingPlan, setPendingPlan] = useState(null);

  const goToPayment = async (planId) => {
    setLoading(planId);
    try {
      const result = await startHypCheckout(planId, promoApplied?.code || null);
      // Session perdue ou expirée entre-temps : on redemande le compte plutôt
      // que de laisser l'élève devant un message d'erreur.
      if (!result.ok && result.status === 401) {
        toast.info('Reconnecte-toi pour finaliser ton abonnement.');
        setPendingPlan(planId);
      }
    } finally {
      setLoading(null);
    }
  };

  const checkout = async (planId) => {
    // Pas de compte, pas de paiement : sinon l'abonnement encaissé ne peut être
    // rattaché à personne. La formule est mémorisée et le paiement repart seul
    // dès que le compte est prêt.
    if (!user) {
      setPendingPlan(planId);
      return;
    }
    await goToPayment(planId);
  };

  const planLabel = (planId) =>
    [...standardOptions, ...premiumOptions].find((o) => o.planId === planId)?.label || 'Flash Neiga';

  // Vérifie le code auprès du serveur pour afficher le prix remisé.
  // Le montant réellement facturé est recalculé côté serveur au paiement.
  const applyPromo = async (planId) => {
    const code = promoInput.trim();
    if (!code) return;
    setPromoChecking(true);
    setPromoMessage(null);
    try {
      const { data } = await axios.post('/api/payments/hyp/validate-promo', {
        code, plan_id: planId, user_id: user?.id || null,
      });
      if (data.valid) {
        setPromoApplied(data);
        setPromoMessage({ ok: true, text: data.message });
      } else {
        setPromoApplied(null);
        setPromoMessage({ ok: false, text: data.message });
      }
    } catch (e) {
      setPromoApplied(null);
      setPromoMessage({ ok: false, text: e?.response?.data?.detail || 'Code invalide' });
    } finally {
      setPromoChecking(false);
    }
  };

  const standardOptions = [
    { planId: HYP_CONFIG.plans.BASIC.DAYS_14, price: 69, duration: '14 jours', label: 'Standard 14 jours' },
    { planId: HYP_CONFIG.plans.BASIC.DAYS_21, price: 89, duration: '21 jours', label: 'Standard 21 jours' },
    { planId: HYP_CONFIG.plans.BASIC.DAYS_30, price: 99, duration: '30 jours', label: 'Standard 30 jours' },
  ];
  const premiumOptions = [
    { planId: HYP_CONFIG.plans.PREMIUM.DAYS_14, price: 119, duration: '14 jours', label: 'Premium 14 jours' },
    { planId: HYP_CONFIG.plans.PREMIUM.DAYS_21, price: 139, duration: '21 jours', label: 'Premium 21 jours' },
    { planId: HYP_CONFIG.plans.PREMIUM.DAYS_30, price: 149, duration: '30 jours', label: 'Premium 30 jours' },
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
            {user ? (
              <div className="text-right text-sm">
                <div className="text-white/60 text-xs">Abonnement rattaché à</div>
                <div className="text-white font-semibold">{user.email}</div>
                <button type="button" onClick={logout} className="text-white/50 hover:text-white text-xs underline underline-offset-2">
                  Ce n'est pas moi
                </button>
              </div>
            ) : (
              <a href="/login" className="text-sm text-white/70 hover:text-white underline underline-offset-4">Se connecter</a>
            )}
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
          <h2 className="text-center text-2xl md:text-3xl font-extrabold mb-2">
            Choisis ta formule et avance à ton rythme
          </h2>
          <p className="text-center text-sm text-white/60 mb-6">
            {user
              ? <>Ton abonnement sera activé sur ton compte <strong className="text-white/80">{user.email}</strong> dès le paiement validé.</>
              : "Tu choisiras ton mot de passe juste avant le paiement : ton accès est activé immédiatement après."}
          </p>

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

          {/* Code promo */}
          <div className="mt-6 rounded-2xl bg-white/[0.06] border border-white/10 p-4">
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <label htmlFor="promo" className="text-sm text-white/85 font-semibold whitespace-nowrap">
                Tu as un code promo ?
              </label>
              <input
                id="promo"
                type="text"
                value={promoInput}
                onChange={(e) => setPromoInput(e.target.value.toUpperCase())}
                placeholder="Saisis ton code"
                className="flex-1 rounded-xl bg-white/10 border border-white/15 px-3 py-2 text-sm text-white placeholder-white/40 uppercase focus:outline-none focus:ring-2 focus:ring-yellow-400"
              />
              <button
                type="button"
                onClick={() => applyPromo(premiumSel)}
                disabled={promoChecking || !promoInput.trim()}
                className="rounded-xl bg-white/15 hover:bg-white/25 text-white font-semibold px-4 py-2 text-sm transition-colors disabled:opacity-50"
              >
                {promoChecking ? 'Vérification…' : 'Appliquer'}
              </button>
            </div>
            {promoMessage && (
              <p className={`mt-2 text-sm ${promoMessage.ok ? 'text-emerald-300' : 'text-red-300'}`}>
                {promoMessage.text}
                {promoApplied && !promoApplied.free && (
                  <> — tu paieras <strong>{promoApplied.final_amount} ₪</strong> au lieu de {promoApplied.original_amount} ₪.</>
                )}
              </p>
            )}
            <p className="mt-2 text-xs text-white/50">
              Le code est vérifié pour la formule Premium sélectionnée ; la remise est recalculée sur la
              formule que tu choisis au moment du paiement.
            </p>
          </div>

          <p className="mt-4 text-center text-sm text-white/70">
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

      {pendingPlan && (
        <AccountGate
          planLabel={planLabel(pendingPlan)}
          onClose={() => setPendingPlan(null)}
          onReady={() => {
            const planId = pendingPlan;
            setPendingPlan(null);
            goToPayment(planId);
          }}
        />
      )}
    </div>
  );
}

export default Pricing;
