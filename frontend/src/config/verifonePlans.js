// frontend/src/config/verifonePlans.js
// Define Verifone/2Checkout plan amounts in ILS (₪)

export const VERIFONE_PLANS = {
  CODE: {
    DAYS_14: { amount: 119, currency: 'ILS', name: 'Code 14 jours', productId: 52702666 },
    DAYS_30: { amount: 189, currency: 'ILS', name: 'Code 30 jours', productId: 52702671 },
    WEEK_EXTENSION: { amount: 49, currency: 'ILS', name: 'Code extension 7 jours' },
  },
  VIDEOS: {
    MONTH_1: { amount: 199, currency: 'ILS', name: 'Vidéos 1 mois', productId: 52702691 },
    MONTH_2: { amount: 349, currency: 'ILS', name: 'Vidéos 2 mois', productId: 52702701 },
    MONTH_3: { amount: 489, currency: 'ILS', name: 'Vidéos 3 mois', productId: 52702716 },
    WEEK_EXTENSION: { amount: 49, currency: 'ILS', name: 'Vidéos extension 7 jours' },
  },
};
