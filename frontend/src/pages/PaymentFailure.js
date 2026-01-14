import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { XCircle, RefreshCw, Mail, Home } from 'lucide-react';

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
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-6">
      <div className="max-w-md w-full bg-white/[0.03] backdrop-blur-xl border border-white/[0.05] rounded-2xl shadow-xl p-8 text-center">
        {/* Error Icon */}
        <div className="mb-6">
          <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-red-500/10">
            <XCircle className="h-10 w-10 text-red-500" />
          </div>
        </div>

        {/* Error Message */}
        <h1 className="text-3xl font-bold text-white mb-4">
          Payment Failed
        </h1>
        
        <p className="text-slate-300 mb-6">
          {errorMessage}
        </p>

        {/* Transaction ID */}
        {transactionId && (
          <div className="bg-white/[0.05] backdrop-blur-sm rounded-xl p-4 mb-6 border border-white/[0.05]">
            <p className="text-xs text-slate-400 mb-1">
              ID de transaction
            </p>
            <p className="font-mono text-sm text-white">
              {transactionId}
            </p>
          </div>
        )}

        {/* Common Reasons */}
        <div className="bg-white/[0.05] backdrop-blur-sm border border-white/[0.05] rounded-xl p-4 mb-6 text-left">
          <h3 className="font-semibold text-indigo-400 mb-2 text-sm">
            Raisons courantes d'échec :
          </h3>
          <ul className="text-sm text-slate-300 space-y-1 list-disc list-inside">
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
            className="w-full bg-indigo-600 hover:bg-indigo-700 transition-colors flex items-center justify-center gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            Retry Payment
          </Button>
          
          <Button 
            onClick={() => window.location.href = 'mailto:support@flash-neiga.com'}
            variant="outline"
            className="w-full border-white/[0.05] hover:bg-white/[0.05] transition-colors flex items-center justify-center gap-2"
          >
            <Mail className="h-4 w-4" />
            Contact Support
          </Button>
          
          <button
            onClick={() => navigate('/')}
            className="w-full flex items-center justify-center gap-2 text-slate-400 hover:text-white transition-colors text-sm"
          >
            <Home className="h-4 w-4" />
            Back to Home
          </button>
        </div>

        {/* Support Info */}
        <div className="mt-6 pt-6 border-t border-white/[0.05]">
          <p className="text-xs text-slate-400">
            Nous sommes là pour vous aider. N'hésitez pas à nous contacter si vous rencontrez des difficultés.
            <br />
            Support:{' '}
            <a 
              href="mailto:support@flash-neiga.com" 
              className="text-indigo-400 hover:text-indigo-300 hover:underline transition-colors"
            >
              support@flash-neiga.com
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

export default PaymentFailure;
