"frontend/src/pages/Pricing.js"

import React from "react";
import axios from "axios";
import { PADDLE_PRICES } from '../config/paddlePrices';
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";

async function startPaddleCheckout(priceId) {
  try {
    if (!priceId || String(priceId).startsWith('pri_FILL_ME')) {
      alert('Configurez les IDs Paddle (voir setup-paddle.js ou variables REACT_APP_PADDLE_PRICE_*).');
      return;
    }
    console.log('Envoi priceId:', priceId);
    // Use camelCase 'priceId' to match backend expectations
    const res = await axios.post('/api/payments/paddle/create-checkout', { priceId: priceId });
    const checkoutUrl = res.data?.checkoutUrl || res.data?.url;
    if (checkoutUrl) {
      console.log('Checkout URL:', checkoutUrl);
      try {
        window.location.assign(checkoutUrl);
      } catch (assignErr) {
        console.warn('assign() failed, trying window.open', assignErr);
        const w = window.open(checkoutUrl, '_self');
        if (!w) {
          alert('Impossible d’ouvrir le paiement. URL: ' + checkoutUrl);
        }
      }
    } else {
      alert('Erreur: URL de paiement Paddle non disponible');
    }
  } catch (e) {
    console.error('Paddle checkout error:', e?.response?.status, e?.response?.data);
    alert('Erreur de paiement Paddle');
  }
}

function Pricing() {
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Abonnements</h1>

      {/* Removed free account banner to avoid suggesting free sign-up */}

      <section className="space-y-6">
        <div className="rounded-lg border p-4">
          <h2 className="text-xl font-semibold mb-2">Abonnements au code</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li>Accès à la Web App</li>
            <li>Livre de code en ligne (E-book)</li>
            <li>Questions officielles du code de la route israélien</li>
            <li>Examens blancs</li>
            <li>Coaching / cours privés de code</li>
          </ul>
          <div className="mt-4 grid gap-2">
            <div>14 jours / <span className="font-semibold">119₪</span></div>
            <div>30 jours / <span className="font-semibold">189₪</span> <span className="line-through opacity-70">238₪</span></div>
            <div>Chaque semaine supplémentaire <span className="font-semibold">49₪</span></div>
            <div className="mt-3 flex gap-2">
              <Button variant="outline" onClick={() => startPaddleCheckout(PADDLE_PRICES.CODE.DAYS_14)}>Payer 14 jours (Paddle)</Button>
              <Button variant="outline" onClick={() => startPaddleCheckout(PADDLE_PRICES.CODE.DAYS_30)}>Payer 30 jours (Paddle)</Button>
            </div>
          </div>
        </div>

        <div className="rounded-lg border p-4">
          <h2 className="text-xl font-semibold mb-2">Vidéos pédagogiques</h2>
          <p className="mb-2">
            Vidéos pédagogiques sur les 28 objectifs dans l'apprentissage de la conduite +
            parcours examens de conduite filmés et commentés + situations réelles à anticiper
            en format "Conduite Commentée"
          </p>
          <div className="grid gap-2">
            <div>1 mois / <span className="font-semibold">199₪</span></div>
            <div>2 mois / <span className="font-semibold">349₪</span> <span className="line-through opacity-70">398₪</span></div>
            <div>3 mois / <span className="font-semibold">489₪</span> <span className="line-through opacity-70">597₪</span></div>
            <div>Chaque semaine supplémentaire <span className="font-semibold">49₪</span></div>
            <div className="mt-3 flex gap-2">
              <Button variant="outline" onClick={() => startPaddleCheckout(PADDLE_PRICES.VIDEOS.MONTH_1)}>Payer 1 mois (Paddle)</Button>
              <Button variant="outline" onClick={() => startPaddleCheckout(PADDLE_PRICES.VIDEOS.MONTH_2)}>Payer 2 mois (Paddle)</Button>
              <Button variant="outline" onClick={() => startPaddleCheckout(PADDLE_PRICES.VIDEOS.MONTH_3)}>Payer 3 mois (Paddle)</Button>
            </div>
          </div>
        </div>

        <div className="rounded-lg border p-4">
          <h2 className="text-xl font-semibold mb-2">Offre combinée</h2>
          <p className="mb-2">
            2 leçons de conduite offertes d'une valeur de 390₪ / 420₪ pour tout abonnement au
            Code & Vidéos pédagogiques*
          </p>
          <p>
            Toute personne ayant déjà le code en poche et qui souscrit à l'abonnement de 3 mois
            et plus aux Vidéos pédagogiques bénéficiera automatiquement de 2 leçons de conduite offertes.
          </p>
        </div>
      
      {/* Gestion d'abonnement via Paddle à implémenter si nécessaire */}
      </section>

    </div>
  );
}

export default Pricing;
