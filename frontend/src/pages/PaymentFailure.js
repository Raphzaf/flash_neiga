import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/button';

function PaymentFailure() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const transactionId = searchParams.get('transaction_id');
  const errorMessage = searchParams.get('error') || 'Le paiement a échoué ou a été annulé.';

  useEffect(() => {
    // Log the failure for analytics/debugging
    console.error('Payment failed:', { transactionId, errorMessage });
  }, [transactionId, errorMessage]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-50 to-orange-50 dark:from-slate-900 dark:to-slate-800 p-6">
      <div className="max-w-md w-full bg-white dark:bg-slate-800 rounded-lg shadow-xl p-8 text-center">
        {/* Error Icon */}
        <div className="mb-6">
          <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-red-100 dark:bg-red-900">
            <svg
              className="h-10 w-10 text-red-600 dark:text-red-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </div>
        </div>

        {/* Error Message */}
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-4">
          Paiement échoué
        </h1>
        
        <p className="text-slate-600 dark:text-slate-300 mb-6">
          {errorMessage}
        </p>

        {/* Transaction ID */}
        {transactionId && (
          <div className="bg-slate-50 dark:bg-slate-700 rounded-lg p-4 mb-6">
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">
              ID de transaction
            </p>
            <p className="font-mono text-sm text-slate-900 dark:text-white">
              {transactionId}
            </p>
          </div>
        )}

        {/* Common Reasons */}
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6 text-left">
          <h3 className="font-semibold text-blue-900 dark:text-blue-300 mb-2 text-sm">
            Raisons courantes d'échec :
          </h3>
          <ul className="text-sm text-blue-800 dark:text-blue-200 space-y-1 list-disc list-inside">
            <li>Fonds insuffisants sur la carte</li>
            <li>Informations de carte incorrectes</li>
            <li>Carte expirée</li>
            <li>Paiement refusé par la banque</li>
            <li>Paiement annulé par l'utilisateur</li>
          </ul>
        </div>

        {/* Action Buttons */}
        <div className="space-y-3">
          <Button 
            onClick={() => navigate('/pricing')} 
            className="w-full bg-blue-600 hover:bg-blue-700"
          >
            Réessayer le paiement
          </Button>
          
          <Button 
            onClick={() => navigate('/dashboard')} 
            variant="outline"
            className="w-full"
          >
            Retour au tableau de bord
          </Button>
        </div>

        {/* Support Info */}
        <div className="mt-6 pt-6 border-t border-slate-200 dark:border-slate-700">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Besoin d'aide ?
            <br />
            Contactez notre support à{' '}
            <a 
              href="mailto:support@flashneiga.com" 
              className="text-blue-600 dark:text-blue-400 hover:underline"
            >
              support@flashneiga.com
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

export default PaymentFailure;
