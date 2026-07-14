import React, { useState } from "react";
import axios from "axios";
import { HYP_CONFIG, PLAN_DETAILS, formatPrice } from '../config/hypConfig';
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { useAuth } from "../context/AuthContext";

async function startHypCheckout(planId, userEmail = null, userId = null) {
  try {
    console.log('Starting HYP checkout for plan:', planId);

    const body = {
      plan_id: planId,
      user_email: userEmail,
      user_id: userId
    };

    const res = await axios.post('/api/payments/hyp/create-payment', body);
    const paymentUrl = res.data?.payment_url;
    
    if (paymentUrl) {
      console.log('Redirecting to HYP payment URL:', paymentUrl);
      window.location.href = paymentUrl;
    } else {
      alert('❌ Erreur: URL de paiement non disponible');
    }
  } catch (e) {
    console.error('HYP checkout error:', e?.response?.status, e?.response?.data);
    const errorDetail = e?.response?.data?.detail || 'Erreur inconnue';
    alert(`❌ Erreur de paiement: ${errorDetail}`);
  }
}

function Pricing() {
  const [loading, setLoading] = useState(null);
  const { user } = useAuth();

  const handleCheckout = async (planId) => {
    setLoading(planId);
    try {
      // Pass the logged-in user's id/email so the subscription is linked to
      // their account once the payment is confirmed by HYP.
      await startHypCheckout(planId, user?.email || null, user?.id || null);
    } finally {
      setLoading(null);
    }
  };

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
              <div className="font-semibold text-lg text-slate-900 dark:text-white">
                14 jours - {formatPrice(PLAN_DETAILS.code_14d.price)}
              </div>
              <Button 
                variant="outline" 
                className="w-full mt-2" 
                onClick={() => handleCheckout(HYP_CONFIG.plans.CODE.DAYS_14)}
                disabled={loading === HYP_CONFIG.plans.CODE.DAYS_14}
              >
                {loading === HYP_CONFIG.plans.CODE.DAYS_14 ? 'Chargement...' : 'Souscrire 14 jours'}
              </Button>
            </div>
            
            <div className="p-3 bg-blue-50 dark:bg-blue-950/30 rounded border-2 border-blue-300 dark:border-blue-600">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-lg text-slate-900 dark:text-white">
                    30 jours - {formatPrice(PLAN_DETAILS.code_30d.price)}
                  </span>
                  {PLAN_DETAILS.code_30d.originalPrice && (
                    <span className="ml-2 line-through opacity-60 text-sm text-slate-600 dark:text-slate-400">
                      {formatPrice(PLAN_DETAILS.code_30d.originalPrice)}
                    </span>
                  )}
                </div>
                {PLAN_DETAILS.code_30d.discount && (
                  <span className="bg-blue-600 text-white px-2 py-1 rounded text-xs font-bold">
                    {PLAN_DETAILS.code_30d.discount}
                  </span>
                )}
              </div>
              <Button 
                variant="default" 
                className="w-full mt-2 bg-blue-600 hover:bg-blue-700" 
                onClick={() => handleCheckout(HYP_CONFIG.plans.CODE.DAYS_30)}
                disabled={loading === HYP_CONFIG.plans.CODE.DAYS_30}
              >
                {loading === HYP_CONFIG.plans.CODE.DAYS_30 ? 'Chargement...' : 'Souscrire 30 jours'}
              </Button>
            </div>
            
            <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded">
              <div className="font-semibold text-slate-900 dark:text-white">
                Extension hebdomadaire - {formatPrice(PLAN_DETAILS.code_ext.price)}
              </div>
              <Button 
                variant="outline" 
                size="sm"
                className="w-full mt-2" 
                onClick={() => handleCheckout(HYP_CONFIG.plans.CODE.EXTENSION)}
                disabled={loading === HYP_CONFIG.plans.CODE.EXTENSION}
              >
                {loading === HYP_CONFIG.plans.CODE.EXTENSION ? 'Chargement...' : 'Prolonger d\'une semaine'}
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
              <div className="font-semibold text-lg text-slate-900 dark:text-white">
                1 mois - {formatPrice(PLAN_DETAILS.video_1m.price)}
              </div>
              <Button 
                variant="outline" 
                className="w-full mt-2" 
                onClick={() => handleCheckout(HYP_CONFIG.plans.VIDEO.MONTH_1)}
                disabled={loading === HYP_CONFIG.plans.VIDEO.MONTH_1}
              >
                {loading === HYP_CONFIG.plans.VIDEO.MONTH_1 ? 'Chargement...' : 'Souscrire 1 mois'}
              </Button>
            </div>
            
            <div className="p-3 bg-purple-50 dark:bg-purple-950/30 rounded border-2 border-purple-300 dark:border-purple-600">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-lg text-slate-900 dark:text-white">
                    2 mois - {formatPrice(PLAN_DETAILS.video_2m.price)}
                  </span>
                  {PLAN_DETAILS.video_2m.originalPrice && (
                    <span className="ml-2 line-through opacity-60 text-sm text-slate-600 dark:text-slate-400">
                      {formatPrice(PLAN_DETAILS.video_2m.originalPrice)}
                    </span>
                  )}
                </div>
                {PLAN_DETAILS.video_2m.discount && (
                  <span className="bg-purple-600 text-white px-2 py-1 rounded text-xs font-bold">
                    {PLAN_DETAILS.video_2m.discount}
                  </span>
                )}
              </div>
              <Button 
                variant="default" 
                className="w-full mt-2 bg-purple-600 hover:bg-purple-700" 
                onClick={() => handleCheckout(HYP_CONFIG.plans.VIDEO.MONTH_2)}
                disabled={loading === HYP_CONFIG.plans.VIDEO.MONTH_2}
              >
                {loading === HYP_CONFIG.plans.VIDEO.MONTH_2 ? 'Chargement...' : 'Souscrire 2 mois'}
              </Button>
            </div>
            
            <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded border-2 border-purple-400 dark:border-purple-500">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-lg text-slate-900 dark:text-white">
                    3 mois - {formatPrice(PLAN_DETAILS.video_3m.price)}
                  </span>
                  {PLAN_DETAILS.video_3m.originalPrice && (
                    <span className="ml-2 line-through opacity-60 text-sm text-slate-600 dark:text-slate-400">
                      {formatPrice(PLAN_DETAILS.video_3m.originalPrice)}
                    </span>
                  )}
                </div>
                {PLAN_DETAILS.video_3m.discount && (
                  <span className="bg-purple-700 text-white px-2 py-1 rounded text-xs font-bold">
                    {PLAN_DETAILS.video_3m.discount}
                  </span>
                )}
              </div>
              <Button 
                variant="default" 
                className="w-full mt-2 bg-purple-700 hover:bg-purple-800" 
                onClick={() => handleCheckout(HYP_CONFIG.plans.VIDEO.MONTH_3)}
                disabled={loading === HYP_CONFIG.plans.VIDEO.MONTH_3}
              >
                {loading === HYP_CONFIG.plans.VIDEO.MONTH_3 ? 'Chargement...' : 'Souscrire 3 mois'}
              </Button>
            </div>
            
            <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded">
              <div className="font-semibold text-slate-900 dark:text-white">
                Extension hebdomadaire - {formatPrice(PLAN_DETAILS.video_ext.price)}
              </div>
              <Button 
                variant="outline" 
                size="sm"
                className="w-full mt-2" 
                onClick={() => handleCheckout(HYP_CONFIG.plans.VIDEO.EXTENSION)}
                disabled={loading === HYP_CONFIG.plans.VIDEO.EXTENSION}
              >
                {loading === HYP_CONFIG.plans.VIDEO.EXTENSION ? 'Chargement...' : 'Prolonger d\'une semaine'}
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
            <tr className="bg-purple-50 dark:bg-purple-950/30">
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">Vidéos 2 mois</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 font-semibold text-slate-900 dark:text-white">349₪</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 line-through text-slate-600 dark:text-slate-400">398₪</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-purple-600 dark:text-purple-400 font-bold">-12%</td>
            </tr>
            <tr className="bg-purple-100 dark:bg-purple-900/30">
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">Vidéos 3 mois</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 font-semibold text-slate-900 dark:text-white">489₪</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 line-through text-slate-600 dark:text-slate-400">597₪</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-purple-700 dark:text-purple-300 font-bold">-18%</td>
            </tr>
            <tr>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-900 dark:text-white">Extension 1 semaine</td>
              <td className="px-4 py-2 border border-slate-300 dark:border-slate-600 font-semibold text-slate-900 dark:text-white">49₪</td>
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
