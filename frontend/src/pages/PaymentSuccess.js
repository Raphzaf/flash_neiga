import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';

function PaymentSuccess() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [transaction, setTransaction] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const transactionId = searchParams.get('transaction_id');

  useEffect(() => {
    // Fetch transaction details
    const fetchTransaction = async () => {
      if (!transactionId) {
        setError('ID de transaction manquant');
        setLoading(false);
        return;
      }

      try {
        const response = await axios.get(`/api/payments/hyp/transaction/${transactionId}`);
        setTransaction(response.data);
        setLoading(false);
      } catch (err) {
        console.error('Error fetching transaction:', err);
        setError('Erreur lors de la récupération des détails de paiement');
        setLoading(false);
      }
    };

    fetchTransaction();

    // Auto-redirect to dashboard after 5 seconds
    const timer = setTimeout(() => {
      navigate('/dashboard');
    }, 5000);

    return () => clearTimeout(timer);
  }, [transactionId, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-blue-50 dark:from-slate-900 dark:to-slate-800">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto mb-4"></div>
          <p className="text-slate-700 dark:text-slate-300">Vérification du paiement...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-50 to-orange-50 dark:from-slate-900 dark:to-slate-800 p-6">
        <div className="max-w-md w-full bg-white dark:bg-slate-800 rounded-lg shadow-xl p-8 text-center">
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
            Erreur
          </h1>
          <p className="text-slate-600 dark:text-slate-300 mb-6">
            {error}
          </p>
          <Button onClick={() => navigate('/pricing')} className="w-full">
            Retour aux abonnements
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-blue-50 dark:from-slate-900 dark:to-slate-800 p-6">
      <div className="max-w-md w-full bg-white dark:bg-slate-800 rounded-lg shadow-xl p-8 text-center">
        {/* Success Icon */}
        <div className="mb-6">
          <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-100 dark:bg-green-900">
            <svg
              className="h-10 w-10 text-green-600 dark:text-green-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
        </div>

        {/* Success Message */}
        <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-4">
          Paiement réussi ! 🎉
        </h1>
        
        <p className="text-slate-600 dark:text-slate-300 mb-6">
          Votre abonnement a été activé avec succès.
        </p>

        {/* Transaction Details */}
        {transaction && (
          <div className="bg-slate-50 dark:bg-slate-700 rounded-lg p-4 mb-6 text-left">
            <h3 className="font-semibold text-slate-900 dark:text-white mb-3">
              Détails de la transaction
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-600 dark:text-slate-400">Plan :</span>
                <span className="font-medium text-slate-900 dark:text-white">
                  {transaction.plan_id}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600 dark:text-slate-400">Montant :</span>
                <span className="font-medium text-slate-900 dark:text-white">
                  {transaction.amount}₪
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600 dark:text-slate-400">Statut :</span>
                <span className="font-medium text-green-600 dark:text-green-400">
                  {transaction.status}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600 dark:text-slate-400">ID :</span>
                <span className="font-mono text-xs text-slate-900 dark:text-white">
                  {transaction.id.substring(0, 8)}...
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="space-y-3">
          <Button 
            onClick={() => navigate('/dashboard')} 
            className="w-full bg-green-600 hover:bg-green-700"
          >
            Accéder au tableau de bord
          </Button>
          
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Redirection automatique dans 5 secondes...
          </p>
        </div>

        {/* Additional Info */}
        <div className="mt-6 pt-6 border-t border-slate-200 dark:border-slate-700">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Un email de confirmation vous a été envoyé.
            <br />
            Vous pouvez commencer à utiliser votre abonnement immédiatement.
          </p>
        </div>
      </div>
    </div>
  );
}

export default PaymentSuccess;
