/**
 * Mémoire de parcours du tunnel d'abonnement.
 *
 * Sert uniquement de confort : reprendre là où l'élève s'était arrêté s'il
 * recharge la page, revient en arrière ou revient plus tard. La vérité reste
 * côté serveur — la formule réellement facturée est celle enregistrée sur la
 * transaction, et l'accès dépend de l'abonnement en base, jamais de ces
 * valeurs.
 */

const PLAN_KEY = 'flashneiga.selectedPlan';
const EMAIL_KEY = 'flashneiga.lastEmail';

const safeStorage = {
  get(key) {
    try {
      return window.localStorage.getItem(key);
    } catch {
      return null;   // navigation privée / stockage bloqué
    }
  },
  set(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch {
      /* non bloquant : le parcours fonctionne sans mémoire */
    }
  },
  remove(key) {
    try {
      window.localStorage.removeItem(key);
    } catch {
      /* idem */
    }
  },
};

export const rememberPlan = (planId) => planId && safeStorage.set(PLAN_KEY, planId);
export const readRememberedPlan = () => safeStorage.get(PLAN_KEY);
export const forgetPlan = () => safeStorage.remove(PLAN_KEY);

// L'email sert à pré-remplir la connexion : jamais le mot de passe.
export const rememberEmail = (email) => email && safeStorage.set(EMAIL_KEY, email);
export const readRememberedEmail = () => safeStorage.get(EMAIL_KEY);

export const formatPrice = (amount, currency = 'ILS') => {
  if (amount == null) return '—';
  const value = Number(amount).toLocaleString('fr-FR');
  return currency === 'ILS' ? `${value} ₪` : `${value} ${currency}`;
};

export const formatDate = (value) =>
  value
    ? new Date(value).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
    : '—';

/** Prix moyen par jour, utile pour comparer des durées différentes. */
export const pricePerDay = (amount, days) =>
  amount && days ? Math.round((Number(amount) / Number(days)) * 10) / 10 : null;
