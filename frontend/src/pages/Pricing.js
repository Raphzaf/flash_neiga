import React from "react";
import axios from "axios";
import { VERIFONE_PLANS } from '../config/verifonePlans';
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";

async function startVerifoneCheckout(plan) {
  try {
    if (!plan || !plan.amount || !plan.currency) {
      alert('⚠️ Ce plan n\'est pas configuré correctement (montant/devise manquants).');
      return;
    }
    const body = {
      amount: plan.amount,
      currency: plan.currency,
      name: plan.name,
      productId: plan.productId,
      returnUrl: window.location.origin + '/subscription-success',
      test: true,
    };
    const res = await axios.post('/api/payments/verifone/create-checkout', body);
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
      alert('❌ Erreur: URL de paiement Verifone non disponible');
    }
  } catch (e) {
    console.error('Verifone checkout error:', e?.response?.status, e?.response?.data);
    const errorDetail = e?.response?.data?.detail || 'Erreur inconnue';
    alert(`❌ Erreur de paiement Verifone: ${errorDetail}`);
  }
}

function Pricing() {
  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 text-center text-slate-900 dark:text-white">Abonnements Flash Neiga</h1>

      <div className="grid md:grid-cols-2 gap-6 mb-6">
        {/* Code Subscription Card */}
        <div className="rounded-lg border-2 border-blue-300 dark:border-blue-600 p-6 bg-white dark:bg-slate-800 shadow-lg">
          <h2 className="text-2xl font-bold mb-3 text-blue-700 dark:text-blue-400">📚 Abonnement au Code</h2>
          <ul className="list-disc pl-5 space-y-2 mb-4 text-sm text-slate-700 dark:text-slate-200">
            <li>Accès à la Web App</li>
            <li>Livre de code en ligne (E-book)</li>
            <li>Questions officielles du code israélien</li>
            <li>Examens blancs</li>
            <li>Coaching / cours privés de code</li>
          </ul>
          
          <div className="space-y-3">
            <div className="p-3 bg-slate-50 dark:bg-slate-700 rounded">
              <div className="font-semibold text-lg text-slate-900 dark:text-white">14 jours - 119₪</div>
              <Button 
                variant="outline" 
                className="w-full mt-2" 
                onClick={() => startVerifoneCheckout(VERIFONE_PLANS.CODE.DAYS_14)}
              >
                Souscrire 14 jours
              </Button>
            </div>
            
            <div className="p-3 bg-blue-50 dark:bg-blue-950/30 rounded border-2 border-blue-300 dark:border-blue-600">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-lg text-slate-900 dark:text-white">30 jours - 189₪</span>
                  <span className="ml-2 line-through opacity-60 text-sm text-slate-600 dark:text-slate-400">238₪</span>
                </div>
                <span className="bg-blue-600 text-white px-2 py-1 rounded text-xs font-bold">-21%</span>
              </div>
              <Button 
                variant="default" 
                className="w-full mt-2 bg-blue-600 hover:bg-blue-700" 
                onClick={() => startVerifoneCheckout(VERIFONE_PLANS.CODE.DAYS_30)}
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
                onClick={() => startVerifoneCheckout(VERIFONE_PLANS.CODE.WEEK_EXTENSION)}
              >
                Prolonger d'une semaine
              </Button>
            </div>
          </div>
        </div>

        {/* Videos Subscription Card */}
        <div className="rounded-lg border-2 border-purple-300 dark:border-purple-600 p-6 bg-white dark:bg-slate-800 shadow-lg">
          <h2 className="text-2xl font-bold mb-3 text-purple-700 dark:text-purple-400">🎥 Vidéos Pédagogiques</h2>
          <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">
            Vidéos sur les 28 objectifs dans l'apprentissage de la conduite + 
            parcours examens filmés et commentés + situations réelles à anticiper 
            en format "Conduite Commentée"
          </p>
          
          <div className="space-y-3">
            <div className="p-3 bg-slate-50 dark:bg-slate-700 rounded">
              <div className="font-semibold text-lg text-slate-900 dark:text-white">1 mois - 199₪</div>
              <Button 
                variant="outline" 
                className="w-full mt-2" 
                onClick={() => startVerifoneCheckout(VERIFONE_PLANS.VIDEOS.MONTH_1)}
              >
                Souscrire 1 mois
              </Button>
            </div>
            
            <div className="p-3 bg-purple-50 dark:bg-purple-950/30 rounded border-2 border-purple-300 dark:border-purple-600">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-lg text-slate-900 dark:text-white">2 mois - 349₪</span>
                  <span className="ml-2 line-through opacity-60 text-sm text-slate-600 dark:text-slate-400">398₪</span>
                </div>
                <span className="bg-purple-600 text-white px-2 py-1 rounded text-xs font-bold">-12%</span>
              </div>
              <Button 
                variant="default" 
                className="w-full mt-2 bg-purple-600 hover:bg-purple-700" 
                onClick={() => startVerifoneCheckout(VERIFONE_PLANS.VIDEOS.MONTH_2)}
              >
                Souscrire 2 mois
              </Button>
            </div>
            
            <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded border-2 border-purple-400 dark:border-purple-500">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-lg text-slate-900 dark:text-white">3 mois - 489₪</span>
                  <span className="ml-2 line-through opacity-60 text-sm text-slate-600 dark:text-slate-400">597₪</span>
                </div>
                <span className="bg-purple-700 text-white px-2 py-1 rounded text-xs font-bold">-18%</span>
              </div>
              <Button 
                variant="default" 
                className="w-full mt-2 bg-purple-700 hover:bg-purple-800" 
                onClick={() => startVerifoneCheckout(VERIFONE_PLANS.VIDEOS.MONTH_3)}
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
                onClick={() => startVerifoneCheckout(VERIFONE_PLANS.VIDEOS.WEEK_EXTENSION)}
              >
                Prolonger d'une semaine
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Combo Offer Section */}
      <div className="rounded-lg border-2 border-green-300 dark:border-green-600 p-6 bg-gradient-to-r from-green-50 to-yellow-50 dark:from-green-950/30 dark:to-yellow-950/30 shadow-lg">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-3xl">🎁</span>
          <h2 className="text-2xl font-bold text-green-800 dark:text-green-300">Offre Combinée - 2 Leçons Offertes!</h2>
        </div>
        
        <div className="bg-white dark:bg-slate-800 rounded p-4 mb-4 border border-slate-200 dark:border-slate-700">
          <p className="font-semibold text-lg mb-2 text-green-700 dark:text-green-400">
            Valeur: 390₪ - 420₪
          </p>
          <p className="text-slate-700 dark:text-slate-200 mb-2">
            <strong>Comment en bénéficier:</strong>
          </p>
          <ul className="list-disc pl-5 space-y-1 text-sm text-slate-600 dark:text-slate-300">
            <li>Souscrivez au <strong>Code</strong> ET aux <strong>Vidéos 3 mois</strong></li>
            <li>OU si vous avez déjà le code, souscrivez aux <strong>Vidéos 3 mois</strong></li>
          </ul>
        </div>
        
        <div className="bg-yellow-100 dark:bg-yellow-900/30 border-l-4 border-yellow-500 dark:border-yellow-400 p-4 rounded">
          <p className="text-sm text-slate-700 dark:text-slate-200">
            ℹ️ Le bonus de 2 leçons de conduite offertes sera automatiquement enregistré 
            lors de votre souscription aux Vidéos 3 mois si vous êtes éligible.
          </p>
        </div>
      </div>

      {/* Pricing Summary Table */}
      <div className="mt-8 overflow-x-auto">
        <h3 className="text-xl font-bold mb-4 text-slate-900 dark:text-white">📋 Tableau récapitulatif des prix</h3>
        <table className="min-w-full bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded-lg">
          <thead className="bg-slate-100 dark:bg-slate-700">
            <tr>
              <th className="px-4 py-2 text-left border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">Offre</th>
              <th className="px-4 py-2 text-left border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">Prix</th>
              <th className="px-4 py-2 text-left border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">Prix barré</th>
              <th className="px-4 py-2 text-left border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">Réduction</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">Code 14 jours</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 font-semibold text-slate-900 dark:text-white">119₪</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">-</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">-</td>
            </tr>
            <tr className="bg-blue-50 dark:bg-blue-950/30">
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">Code 30 jours</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 font-semibold text-slate-900 dark:text-white">189₪</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 line-through text-slate-600 dark:text-slate-400">238₪</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-blue-600 dark:text-blue-400 font-bold">-21%</td>
            </tr>
            <tr>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">Vidéos 1 mois</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 font-semibold text-slate-900 dark:text-white">199₪</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">-</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">-</td>
            </tr>
            <tr className="bg-purple-50">
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">Vidéos 2 mois</td>
              <td className="px-4 py-2 border font-semibold">349₪</td>
              <td className="px-4 py-2 border line-through">398₪</td>
              <td className="px-4 py-2 border text-purple-600 font-bold">-12%</td>
            </tr>
            <tr className="bg-purple-100 dark:bg-purple-900/30">
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">Vidéos 3 mois</td>
              <td className="px-4 py-2 border font-semibold">489₪</td>
              <td className="px-4 py-2 border line-through">597₪</td>
              <td className="px-4 py-2 border text-purple-700 font-bold">-18%</td>
            </tr>
            <tr>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">Extension 1 semaine</td>
              <td className="px-4 py-2 border font-semibold">49₪</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">-</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">-</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default Pricing;
