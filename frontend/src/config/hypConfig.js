// frontend/src/config/hypConfig.js
// HYP Payment Platform Configuration

export const HYP_CONFIG = {
  backendUrl: process.env.REACT_APP_BACKEND_URL || '/api',
  plans: {
    STANDARD: {
      DAYS_14: 'standard_14d',
      DAYS_30: 'standard_30d',
    },
    PREMIUM: {
      DAYS_14: 'premium_14d',
      DAYS_30: 'premium_30d',
    },
    CODE: {
      DAYS_14: 'code_14d',
      DAYS_30: 'code_30d',
      EXTENSION: 'code_ext',
    },
    VIDEO: {
      MONTH_1: 'video_1m',
      MONTH_2: 'video_2m',
      MONTH_3: 'video_3m',
      EXTENSION: 'video_ext',
    }
  }
};

export const PLAN_DETAILS = {
  standard_14d: { name: 'Formule Standard', price: 79, currency: 'ILS', duration: '14 jours' },
  standard_30d: { name: 'Formule Standard', price: 129, currency: 'ILS', duration: '30 jours' },
  premium_14d: { name: 'Formule Premium', price: 109, currency: 'ILS', duration: '14 jours' },
  premium_30d: { name: 'Formule Premium', price: 159, currency: 'ILS', duration: '30 jours' },
  code_14d: {
    name: 'Code 14 jours',
    price: 99,
    currency: 'ILS',
    duration: '14 jours',
    features: [
      'Accès à la Web App',
      'Livre de code en ligne (E-book)',
      'Questions officielles du code israélien',
      'Examens blancs',
      'Coaching / cours privés de code'
    ]
  },
  code_30d: {
    name: 'Code 30 jours',
    price: 159,
    currency: 'ILS',
    originalPrice: 198,
    duration: '30 jours',
    discount: '-20%',
    features: [
      'Accès à la Web App',
      'Livre de code en ligne (E-book)',
      'Questions officielles du code israélien',
      'Examens blancs',
      'Coaching / cours privés de code'
    ]
  },
  code_ext: {
    name: 'Extension Code',
    price: 59,
    currency: 'ILS',
    duration: '1 semaine',
    features: [
      'Prolongation d\'une semaine',
      'Tous les avantages du plan Code'
    ]
  },
  video_1m: {
    name: 'Vidéos 1 mois',
    price: 199,
    currency: 'ILS',
    duration: '1 mois',
    features: [
      '28 objectifs pédagogiques',
      'Parcours examens complets',
      'Situations réelles de conduite',
      'Accès illimité pendant 30 jours'
    ]
  },
  video_2m: {
    name: 'Vidéos 2 mois',
    price: 339,
    currency: 'ILS',
    originalPrice: 398,
    duration: '2 mois',
    discount: '-15%',
    features: [
      '28 objectifs pédagogiques',
      'Parcours examens complets',
      'Situations réelles de conduite',
      'Accès illimité pendant 60 jours'
    ]
  },
  video_3m: {
    name: 'Vidéos 3 mois',
    price: 419,
    currency: 'ILS',
    originalPrice: 597,
    duration: '3 mois',
    discount: '-30%',
    features: [
      '28 objectifs pédagogiques',
      'Parcours examens complets',
      'Situations réelles de conduite',
      'Accès illimité pendant 90 jours',
      '💎 Meilleure valeur!'
    ]
  },
  video_ext: {
    name: 'Extension Vidéos',
    price: 59,
    currency: 'ILS',
    duration: '1 semaine',
    features: [
      'Prolongation d\'une semaine',
      'Tous les avantages du plan Vidéos'
    ]
  }
};

// Helper function to format price
export const formatPrice = (price, currency = 'ILS') => {
  return `${price}${currency === 'ILS' ? '₪' : currency}`;
};

// Helper function to get plan details
export const getPlanDetails = (planId) => {
  return PLAN_DETAILS[planId] || null;
};
