import React from "react";
import axios from "axios";
import { PADDLE_PRICES } from '../config/paddlePrices';
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";

const UNCONFIGURED_PRICE_ID = 'TO_BE_CREATED';

async function startPaddleCheckout(priceId) {
  try {
    if (!priceId || String(priceId).startsWith('pri_FILL_ME') || String(priceId) === UNCONFIGURED_PRICE_ID) {
      alert('⚠️ Ce prix n\'est pas encore configuré. Veuillez créer les price IDs avec le script backend/scripts/create_paddle_extensions.py');
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
          alert('Impossible d\'ouvrir le paiement. URL: ' + checkoutUrl);
        }
      }
    } else {
      alert('❌ Erreur: URL de paiement Paddle non disponible');
    }
  } catch (e) {
    console.error('Paddle checkout error:', e?.response?.status, e?.response?.data);
    const errorDetail = e?.response?.data?.detail || 'Erreur inconnue';
    alert(`❌ Erreur de paiement Paddle: ${errorDetail}`);
  }
}

function Pricing() {
  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 text-center">Abonnements Flash Neiga</h1>

      <div className="grid md:grid-cols-2 gap-6 mb-6">
        {/* Code Subscription Card */}
        <div className="rounded-lg border-2 border-blue-200 p-6 bg-white shadow-lg">
          <h2 className="text-2xl font-bold mb-3 text-blue-700">📚 Abonnement au Code</h2>
          <ul className="list-disc pl-5 space-y-2 mb-4 text-sm">
            <li>Accès à la Web App</li>
            <li>Livre de code en ligne (E-book)</li>
            <li>Questions officielles du code israélien</li>
            <li>Examens blancs</li>
            <li>Coaching / cours privés de code</li>
          </ul>
          
          <div className="space-y-3">
            <div className="p-3 bg-gray-50 rounded">
              <div className="font-semibold text-lg">14 jours - 119₪</div>
              <Button 
                variant="outline" 
                className="w-full mt-2" 
                onClick={() => startPaddleCheckout(PADDLE_PRICES.CODE.DAYS_14)}
              >
                Souscrire 14 jours
              </Button>
            </div>
            
            <div className="p-3 bg-blue-50 rounded border-2 border-blue-300">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-lg">30 jours - 189₪</span>
                  <span className="ml-2 line-through opacity-60 text-sm">238₪</span>
                </div>
                <span className="bg-blue-600 text-white px-2 py-1 rounded text-xs font-bold">-21%</span>
              </div>
              <Button 
                variant="default" 
                className="w-full mt-2 bg-blue-600 hover:bg-blue-700" 
                onClick={() => startPaddleCheckout(PADDLE_PRICES.CODE.DAYS_30)}
              >
                Souscrire 30 jours
              </Button>
            </div>
            
            <div className="p-3 bg-gray-50 rounded">
              <div className="font-semibold">Extension hebdomadaire - 49₪</div>
              <Button 
                variant="outline" 
                size="sm"
                className="w-full mt-2" 
                onClick={() => startPaddleCheckout(PADDLE_PRICES.CODE.WEEK_EXTENSION)}
              >
                Prolonger d'une semaine
              </Button>
            </div>
          </div>
        </div>

        {/* Videos Subscription Card */}
        <div className="rounded-lg border-2 border-purple-200 p-6 bg-white shadow-lg">
          <h2 className="text-2xl font-bold mb-3 text-purple-700">🎥 Vidéos Pédagogiques</h2>
          <p className="mb-4 text-sm text-gray-600">
            Vidéos sur les 28 objectifs dans l'apprentissage de la conduite + 
            parcours examens filmés et commentés + situations réelles à anticiper 
            en format "Conduite Commentée"
          </p>
          
          <div className="space-y-3">
            <div className="p-3 bg-gray-50 rounded">
              <div className="font-semibold text-lg">1 mois - 199₪</div>
              <Button 
                variant="outline" 
                className="w-full mt-2" 
                onClick={() => startPaddleCheckout(PADDLE_PRICES.VIDEOS.MONTH_1)}
              >
                Souscrire 1 mois
              </Button>
            </div>
            
            <div className="p-3 bg-purple-50 rounded border-2 border-purple-300">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-lg">2 mois - 349₪</span>
                  <span className="ml-2 line-through opacity-60 text-sm">398₪</span>
                </div>
                <span className="bg-purple-600 text-white px-2 py-1 rounded text-xs font-bold">-12%</span>
              </div>
              <Button 
                variant="default" 
                className="w-full mt-2 bg-purple-600 hover:bg-purple-700" 
                onClick={() => startPaddleCheckout(PADDLE_PRICES.VIDEOS.MONTH_2)}
              >
                Souscrire 2 mois
              </Button>
            </div>
            
            <div className="p-3 bg-purple-100 rounded border-2 border-purple-400">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-lg">3 mois - 489₪</span>
                  <span className="ml-2 line-through opacity-60 text-sm">597₪</span>
                </div>
                <span className="bg-purple-700 text-white px-2 py-1 rounded text-xs font-bold">-18%</span>
              </div>
              <Button 
                variant="default" 
                className="w-full mt-2 bg-purple-700 hover:bg-purple-800" 
                onClick={() => startPaddleCheckout(PADDLE_PRICES.VIDEOS.MONTH_3)}
              >
                Souscrire 3 mois
              </Button>
            </div>
            
            <div className="p-3 bg-gray-50 rounded">
              <div className="font-semibold">Extension hebdomadaire - 49₪</div>
              <Button 
                variant="outline" 
                size="sm"
                className="w-full mt-2" 
                onClick={() => startPaddleCheckout(PADDLE_PRICES.VIDEOS.WEEK_EXTENSION)}
              >
                Prolonger d'une semaine
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Combo Offer Section */}
      <div className="rounded-lg border-2 border-green-300 p-6 bg-gradient-to-r from-green-50 to-yellow-50 shadow-lg">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-3xl">🎁</span>
          <h2 className="text-2xl font-bold text-green-800">Offre Combinée - 2 Leçons Offertes!</h2>
        </div>
        
        <div className="bg-white rounded p-4 mb-4">
          <p className="font-semibold text-lg mb-2 text-green-700">
            Valeur: 390₪ - 420₪
          </p>
          <p className="text-gray-700 mb-2">
            <strong>Comment en bénéficier:</strong>
          </p>
          <ul className="list-disc pl-5 space-y-1 text-sm text-gray-600">
            <li>Souscrivez au <strong>Code</strong> ET aux <strong>Vidéos 3 mois</strong></li>
            <li>OU si vous avez déjà le code, souscrivez aux <strong>Vidéos 3 mois</strong></li>
          </ul>
        </div>
        
        <div className="bg-yellow-100 border-l-4 border-yellow-500 p-4 rounded">
          <p className="text-sm text-gray-700">
            ℹ️ Le bonus de 2 leçons de conduite offertes sera automatiquement enregistré 
            lors de votre souscription aux Vidéos 3 mois si vous êtes éligible.
          </p>
        </div>
      </div>

      {/* Pricing Summary Table */}
      <div className="mt-8 overflow-x-auto">
        <h3 className="text-xl font-bold mb-4">📋 Tableau récapitulatif des prix</h3>
        <table className="min-w-full bg-white border rounded-lg">
          <thead className="bg-gray-100">
            <tr>
              <th className="px-4 py-2 text-left border">Offre</th>
              <th className="px-4 py-2 text-left border">Prix</th>
              <th className="px-4 py-2 text-left border">Prix barré</th>
              <th className="px-4 py-2 text-left border">Réduction</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="px-4 py-2 border">Code 14 jours</td>
              <td className="px-4 py-2 border font-semibold">119₪</td>
              <td className="px-4 py-2 border">-</td>
              <td className="px-4 py-2 border">-</td>
            </tr>
            <tr className="bg-blue-50">
              <td className="px-4 py-2 border">Code 30 jours</td>
              <td className="px-4 py-2 border font-semibold">189₪</td>
              <td className="px-4 py-2 border line-through">238₪</td>
              <td className="px-4 py-2 border text-blue-600 font-bold">-21%</td>
            </tr>
            <tr>
              <td className="px-4 py-2 border">Vidéos 1 mois</td>
              <td className="px-4 py-2 border font-semibold">199₪</td>
              <td className="px-4 py-2 border">-</td>
              <td className="px-4 py-2 border">-</td>
            </tr>
            <tr className="bg-purple-50">
              <td className="px-4 py-2 border">Vidéos 2 mois</td>
              <td className="px-4 py-2 border font-semibold">349₪</td>
              <td className="px-4 py-2 border line-through">398₪</td>
              <td className="px-4 py-2 border text-purple-600 font-bold">-12%</td>
            </tr>
            <tr className="bg-purple-100">
              <td className="px-4 py-2 border">Vidéos 3 mois</td>
              <td className="px-4 py-2 border font-semibold">489₪</td>
              <td className="px-4 py-2 border line-through">597₪</td>
              <td className="px-4 py-2 border text-purple-700 font-bold">-18%</td>
            </tr>
            <tr>
              <td className="px-4 py-2 border">Extension 1 semaine</td>
              <td className="px-4 py-2 border font-semibold">49₪</td>
              <td className="px-4 py-2 border">-</td>
              <td className="px-4 py-2 border">-</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default Pricing;
