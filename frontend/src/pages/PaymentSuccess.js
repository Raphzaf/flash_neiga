import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { CheckCircle, Home } from 'lucide-react';

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

    // Auto-redirect to training page after 5 seconds
    const timer = setTimeout(() => {
      navigate('/training');
    }, 5000);

    return () => clearTimeout(timer);
  }, [transactionId, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-500 mx-auto mb-4"></div>
          <p className="text-slate-300">Vérification du paiement...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 p-6">
        <div className="max-w-md w-full bg-white/[0.03] backdrop-blur-xl border border-white/[0.05] rounded-2xl shadow-xl p-8 text-center">
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <h1 className="text-2xl font-bold text-white mb-4">
            Erreur
          </h1>
          <p className="text-slate-300 mb-6">
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
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-6">
      <div className="max-w-md w-full bg-white/[0.03] backdrop-blur-xl border border-white/[0.05] rounded-2xl shadow-xl p-8 text-center">
        {/* Success Icon */}
        <div className="mb-6">
          <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-emerald-500/10">
            <CheckCircle className="h-10 w-10 text-emerald-500" />
          </div>
        </div>

        {/* Success Message */}
        <h1 className="text-3xl font-bold text-white mb-4">
          Payment Successful!
        </h1>
        
        <p className="text-slate-300 mb-6">
          Votre abonnement a été activé avec succès.
        </p>

        {/* Transaction Details */}
        {transaction && (
          <div className="bg-white/[0.05] backdrop-blur-sm rounded-xl p-4 mb-6 text-left border border-white/[0.05]">
            <h3 className="font-semibold text-white mb-3">
              Détails de la transaction
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">Plan :</span>
                <span className="font-medium text-white">
                  {transaction.plan_id}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Montant :</span>
                <span className="font-medium text-white">
                  {transaction.amount}₪
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Date :</span>
                <span className="font-medium text-white">
                  {new Date(transaction.created_at || Date.now()).toLocaleDateString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Statut :</span>
                <span className="font-medium text-emerald-500">
                  {transaction.status}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">ID :</span>
                <span className="font-mono text-xs text-white">
                  {transaction.id.substring(0, 8)}...
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="space-y-3">
          <Button 
            onClick={() => navigate('/training')} 
            className="w-full bg-emerald-600 hover:bg-emerald-700 transition-colors"
          >
            Access My Training
          </Button>
          
          <button
            onClick={() => navigate('/')}
            className="w-full flex items-center justify-center gap-2 text-slate-400 hover:text-white transition-colors text-sm"
          >
            <Home className="h-4 w-4" />
            Back to Home
          </button>
          
          <p className="text-sm text-slate-500">
            Redirection automatique dans 5 secondes...
          </p>
        </div>

        {/* Additional Info */}
        <div className="mt-6 pt-6 border-t border-white/[0.05]">
          <p className="text-xs text-slate-400">
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
