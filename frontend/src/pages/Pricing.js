import React from "react";
import axios from "axios";
import { Button } from "../components/ui/button";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

async function startCheckout(plan_key) {
  try {
    // Allow direct price_id via env if mapping fails
    const priceEnvMap = {
      code_14d: process.env.REACT_APP_STRIPE_PRICE_CODE_14D,
      code_30d: process.env.REACT_APP_STRIPE_PRICE_CODE_30D,
      video_1m: process.env.REACT_APP_STRIPE_PRICE_VIDEO_1M,
      video_2m: process.env.REACT_APP_STRIPE_PRICE_VIDEO_2M,
      video_3m: process.env.REACT_APP_STRIPE_PRICE_VIDEO_3M,
    };
    const price_id = priceEnvMap[plan_key];
    const payload = price_id ? { price_id } : { plan_key };
    const res = await axios.post(`${BACKEND_URL}/api/payments/create-checkout-session`, payload);
    if (res.data?.url) {
      window.location.href = res.data.url;
    }
  } catch (e) {
    console.error("Failed to start checkout", e);
    alert("Impossible de démarrer le paiement. Réessayez plus tard.");
  }
}

function Pricing() {
  const publishableKey = process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY;
  const pricingTableId = process.env.REACT_APP_STRIPE_PRICING_TABLE_ID;
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Abonnements</h1>

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
              <Button onClick={() => startCheckout("code_14d")}>
                Payer 14 jours
              </Button>
              <Button variant="secondary" onClick={() => startCheckout("code_30d")}>
                Payer 30 jours
              </Button>
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
              <Button onClick={() => startCheckout("video_1m")}>
                Payer 1 mois
              </Button>
              <Button variant="secondary" onClick={() => startCheckout("video_2m")}>
                Payer 2 mois
              </Button>
              <Button variant="outline" onClick={() => startCheckout("video_3m")}>
                Payer 3 mois
              </Button>
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
      
      <div className="rounded-lg border p-4">
        <h2 className="text-xl font-semibold mb-2">Gérer mon abonnement</h2>
        <p className="text-sm text-muted-foreground mb-3">Accédez au portail client Stripe pour gérer votre abonnement.</p>
        <Button onClick={async () => {
          const sessionId = new URLSearchParams(window.location.search).get("session_id");
          if (!sessionId) {
            alert("Aucune session Stripe trouvée.");
            return;
          }
          try {
            const res = await axios.post(`${BACKEND_URL}/api/payments/create-portal-session`, { session_id: sessionId });
            if (res.data?.url) window.location.href = res.data.url;
          } catch (e) {
            console.error(e);
            alert("Impossible d'ouvrir le portail client.");
          }
        }}>Ouvrir le portail client</Button>
      </div>
      </section>

      {/* Embedded Stripe Pricing Table (no-code) */}
      {publishableKey && pricingTableId ? (
        <div className="mt-8">
          <stripe-pricing-table
            pricing-table-id={pricingTableId}
            publishable-key={publishableKey}
          >
          </stripe-pricing-table>
        </div>
      ) : (
        <div className="mt-8 text-sm text-muted-foreground">
          Configurez `REACT_APP_STRIPE_PUBLISHABLE_KEY` et `REACT_APP_STRIPE_PRICING_TABLE_ID` pour afficher la grille tarifaire intégrée.
        </div>
      )}
    </div>
  );
}

export default Pricing;
