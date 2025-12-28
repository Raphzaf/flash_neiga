// setup-paddle.js
// Setup Paddle products and prices (run once)
// Usage: set PADDLE_API_KEY, then: node setup-paddle.js
// NOTE: Do NOT hardcode secrets; use environment variables.

import { Paddle, Environment } from '@paddle/paddle-node-sdk';

const apiKey = process.env.PADDLE_API_KEY;
if (!apiKey) {
  console.error('❌ Missing PADDLE_API_KEY environment variable');
  process.exit(1);
}

const paddle = new Paddle(apiKey, {
  environment: Environment.production
});

async function setupPaddleProducts() {
  try {
    console.log('🚀 Création des produits et prix Paddle...\n');

    // ===== PRODUIT 1 : CODE SUBSCRIPTION =====
    const codeProduct = await paddle.products.create({
      name: 'Flash Neiga - Code Subscription',
      description: 'Accès à la Web App, E-book, Questions officielles, Examens blancs, Coaching',
      taxCategory: 'standard'
    });
    console.log('✅ Produit Code créé:', codeProduct.id);

    // Prices pour le CODE (ILS)
    const codePrice14days = await paddle.prices.create({
      productId: codeProduct.id,
      description: '14 jours',
      billingCycle: { interval: 'day', frequency: 14 },
      unitPrice: { amount: '11900', currencyCode: 'ILS' }
    });
    console.log('  ✓ Prix 14 jours/119₪ créé:', codePrice14days.id);

    const codePrice30days = await paddle.prices.create({
      productId: codeProduct.id,
      description: '30 jours (réduit de 238₪)',
      billingCycle: { interval: 'day', frequency: 30 },
      unitPrice: { amount: '18900', currencyCode: 'ILS' }
    });
    console.log('  ✓ Prix 30 jours/189₪ créé:', codePrice30days.id);

    // ===== PRODUIT 2 : VIDEOS PEDAGOGIQUES =====
    const videoProduct = await paddle.products.create({
      name: 'Flash Neiga - Vidéos Pédagogiques',
      description: '28 objectifs + parcours examens filmés + Conduite Commentée',
      taxCategory: 'standard'
    });
    console.log('\n✅ Produit Vidéos créé:', videoProduct.id);

    // Prices pour les VIDEOS (ILS)
    const videoPrice1month = await paddle.prices.create({
      productId: videoProduct.id,
      description: '1 mois',
      billingCycle: { interval: 'month', frequency: 1 },
      unitPrice: { amount: '19900', currencyCode: 'ILS' }
    });
    console.log('  ✓ Prix 1 mois/199₪ créé:', videoPrice1month.id);

    const videoPrice2months = await paddle.prices.create({
      productId: videoProduct.id,
      description: '2 mois (réduit de 398₪)',
      billingCycle: { interval: 'month', frequency: 2 },
      unitPrice: { amount: '34900', currencyCode: 'ILS' }
    });
    console.log('  ✓ Prix 2 mois/349₪ créé:', videoPrice2months.id);

    const videoPrice3months = await paddle.prices.create({
      productId: videoProduct.id,
      description: '3 mois (réduit de 597₪)',
      billingCycle: { interval: 'month', frequency: 3 },
      unitPrice: { amount: '48900', currencyCode: 'ILS' }
    });
    console.log('  ✓ Prix 3 mois/489₪ créé:', videoPrice3months.id);

    // Résumé
    console.log('\n\n 📋 RÉSUMÉ POUR TON CODE FRONTEND:\n');
    console.log('ABONNEMENTS AU CODE:');
    console.log(`  - 14 jours: pri_${codePrice14days.id}`);
    console.log(`  - 30 jours: pri_${codePrice30days.id}`);
    console.log('\nABONNEMENTS VIDÉOS:');
    console.log(`  - 1 mois: pri_${videoPrice1month.id}`);
    console.log(`  - 2 mois: pri_${videoPrice2months.id}`);
    console.log(`  - 3 mois: pri_${videoPrice3months.id}`);

    const fs = await import('fs');
    const priceIds = {
      code: { '14days': codePrice14days.id, '30days': codePrice30days.id },
      videos: { '1month': videoPrice1month.id, '2months': videoPrice2months.id, '3months': videoPrice3months.id }
    };
    fs.writeFileSync('./paddle_price_ids.json', JSON.stringify(priceIds, null, 2), 'utf-8');
    console.log('\n✅ IDs sauvegardés dans paddle_price_ids.json');

    console.log('\n✅ Configuration complétée !');
  } catch (error) {
    console.error('❌ Erreur:', error.message || error);
    process.exit(1);
  }
}

setupPaddleProducts();
