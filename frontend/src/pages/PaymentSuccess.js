import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { CheckCircle, Home, DollarSign, Calendar, Package, KeyRound, Eye, EyeOff, Loader2 } from 'lucide-react';

// Constants for polling configuration
const MAX_POLLING_ATTEMPTS = 10;
const POLLING_INTERVAL_MS = 2000;
const AUTO_REDIRECT_DELAY_MS = 7000;

/**
 * Dernière étape quand un paiement est arrivé sans compte rattaché : l'élève
 * choisit son mot de passe ici et entre directement sur la plateforme. Sans ce
 * formulaire, il se retrouve devant une page de connexion pour un compte qui
 * n'existe pas.
 */
function ClaimAccessForm({ transactionId, emailHint, onDone }) {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    if (password.length < 6) {
      setError('Ton mot de passe doit contenir au moins 6 caractères.');
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await axios.post('/api/payments/hyp/claim', {
        transaction_id: transactionId,
        email: email.trim(),
        password,
        first_name: firstName.trim() || null,
        last_name: lastName.trim() || null,
      });
      await onDone(data.access_token);
    } catch (err) {
      setError(err?.response?.data?.detail || "Impossible de finaliser ton accès. Réessaie ou contacte-nous.");
    } finally {
      setSubmitting(false);
    }
  };

  const field = "w-full rounded-xl bg-white/[0.06] border border-white/[0.12] px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500";

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-6">
      <div className="max-w-md w-full bg-white/[0.03] backdrop-blur-xl border border-white/[0.05] rounded-2xl shadow-xl p-8">
        <div className="mx-auto mb-5 flex items-center justify-center h-16 w-16 rounded-full bg-emerald-500/10">
          <CheckCircle className="h-10 w-10 text-emerald-500" />
        </div>

        <h1 className="text-2xl font-bold text-white text-center mb-2">Paiement bien reçu !</h1>
        <p className="text-slate-300 text-center mb-1">
          Dernière étape : choisis ton mot de passe pour ouvrir ton accès.
        </p>
        <p className="text-slate-500 text-sm text-center mb-6">
          {emailHint
            ? <>Utilise de préférence l'email du paiement ({emailHint}).</>
            : "Utilise de préférence l'email indiqué lors du paiement."}
        </p>

        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input className={field} placeholder="Prénom" autoComplete="given-name" autoFocus
              value={firstName} onChange={(e) => setFirstName(e.target.value)} required />
            <input className={field} placeholder="Nom" autoComplete="family-name"
              value={lastName} onChange={(e) => setLastName(e.target.value)} required />
          </div>
          <input className={field} type="email" placeholder="Ton email" autoComplete="email" inputMode="email"
            value={email} onChange={(e) => setEmail(e.target.value)} required />
          <div className="relative">
            <input
              className={`${field} pr-11`}
              type={showPassword ? 'text' : 'password'}
              placeholder="Choisis ton mot de passe (6 caractères minimum)"
              autoComplete="new-password"
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button type="button" onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white">
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <Button type="submit" disabled={submitting} className="w-full bg-emerald-600 hover:bg-emerald-700">
            {submitting
              ? <Loader2 className="h-5 w-5 animate-spin" />
              : <span className="flex items-center gap-2"><KeyRound className="h-4 w-4" /> Activer mon accès</span>}
          </Button>
        </form>

        <p className="mt-5 text-xs text-slate-500 text-center">
          Ton abonnement est déjà payé : ce mot de passe est celui qui te servira à te connecter.
        </p>
      </div>
    </div>
  );
}

function PaymentSuccess() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, loginWithToken } = useAuth();
  const [transaction, setTransaction] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pollAttempt, setPollAttempt] = useState(0);

  // HYP returns the internal order id in `Order`; our own success URL uses
  // `transaction_id`. Support both.
  const transactionId = searchParams.get('transaction_id') || searchParams.get('Order');

  useEffect(() => {
    let cancelled = false;

    // If HYP redirected the browser here with a result payload (CCode present),
    // forward it to the backend callback so the subscription is provisioned even
    // when the server-to-server notification is not configured. Verification is
    // still performed server-side via HYP APISign VERIFY.
    const notifyBackend = async () => {
      if (searchParams.get('CCode') === null) return;
      try {
        const params = Object.fromEntries(searchParams.entries());
        await axios.post('/api/payments/hyp/callback', params);
      } catch (err) {
        console.warn('Backend callback notification failed (will rely on polling):', err?.response?.status);
      }
    };

    // Fetch transaction details with polling
    const fetchTransaction = async (attempt = 0) => {
      if (cancelled) return;
      if (!transactionId) {
        setError('ID de transaction manquant');
        setLoading(false);
        return;
      }

      try {
        const response = await axios.get(`/api/payments/hyp/transaction/${transactionId}`);

        // Check if callback has been processed (transaction completed)
        if (response.data.status === 'completed' || attempt >= MAX_POLLING_ATTEMPTS) {
          setTransaction(response.data);
          setLoading(false);
        } else {
          // Transaction still pending, retry after polling interval
          setPollAttempt(attempt + 1);
          setTimeout(() => fetchTransaction(attempt + 1), POLLING_INTERVAL_MS);
        }
      } catch (err) {
        console.error('Error fetching transaction:', err);

        // Retry on error if not too many attempts
        if (attempt < MAX_POLLING_ATTEMPTS) {
          setPollAttempt(attempt + 1);
          setTimeout(() => fetchTransaction(attempt + 1), POLLING_INTERVAL_MS);
        } else {
          setError('Erreur lors de la récupération des détails de paiement');
          setLoading(false);
        }
      }
    };

    // Trigger provisioning first (best-effort), then start polling.
    notifyBackend().finally(() => fetchTransaction());

    return () => { cancelled = true; };
  }, [transactionId, searchParams]);

  // La redirection automatique n'a lieu que si l'élève peut réellement entrer :
  // connecté et abonnement ouvert. Sinon, il resterait bloqué sur une page de
  // connexion sans savoir quoi faire.
  const canEnter = !!user && !!transaction && !transaction.needs_account;
  useEffect(() => {
    if (!canEnter) return;
    const timer = setTimeout(() => navigate('/training'), AUTO_REDIRECT_DELAY_MS);
    return () => clearTimeout(timer);
  }, [canEnter, navigate]);

  const handleClaimed = useCallback(async (accessToken) => {
    await loginWithToken(accessToken);
    navigate('/training');
  }, [loginWithToken, navigate]);

  // Format date in French format
  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('fr-FR', {
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-500 mx-auto mb-4"></div>
          <p className="text-slate-300">Vérification du paiement...</p>
          {pollAttempt > 0 && (
            <p className="text-slate-500 text-sm mt-2">
              Tentative {pollAttempt + 1}/{MAX_POLLING_ATTEMPTS}
            </p>
          )}
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

  // Paiement encaissé sans compte : on ouvre l'accès ici, tout de suite.
  if (transaction?.needs_account) {
    return (
      <ClaimAccessForm
        transactionId={transaction.id}
        emailHint={transaction.email_hint}
        onDone={handleClaimed}
      />
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
          Paiement réussi !
        </h1>

        <p className="text-slate-300 mb-6">
          {transaction?.status === 'completed'
            ? 'Ton abonnement est activé.'
            : "Ton paiement est en cours de validation : ton accès s'ouvrira dans quelques instants."}
        </p>

        {/* Transaction Details */}
        {transaction && (
          <div className="bg-white/[0.05] backdrop-blur-sm rounded-xl p-4 mb-6 text-left border border-white/[0.05]">
            <h3 className="font-semibold text-white mb-3">
              Détails de la transaction
            </h3>
            <div className="space-y-2 text-sm">
              {/* Amount with icon */}
              <div className="flex justify-between items-center">
                <span className="text-slate-400 flex items-center gap-2">
                  <DollarSign className="h-4 w-4" />
                  Montant :
                </span>
                <span className="font-medium text-white">
                  {transaction.amount}₪
                </span>
              </div>

              {/* Subscription info with icon */}
              {transaction.subscription ? (
                <>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400 flex items-center gap-2">
                      <Package className="h-4 w-4" />
                      Formule :
                    </span>
                    <span className="font-medium text-white">
                      {transaction.subscription.plan_name}
                    </span>
                  </div>

                  {/* End date with icon */}
                  {transaction.subscription.end_date && (
                    <div className="flex justify-between items-center">
                      <span className="text-slate-400 flex items-center gap-2">
                        <Calendar className="h-4 w-4" />
                        Expire le :
                      </span>
                      <span className="font-medium text-emerald-400">
                        {formatDate(transaction.subscription.end_date)}
                      </span>
                    </div>
                  )}

                  <div className="flex justify-between">
                    <span className="text-slate-400">Statut :</span>
                    <span className="font-medium text-emerald-500">
                      {transaction.subscription.status}
                    </span>
                  </div>
                </>
              ) : (
                <div className="flex justify-between">
                  <span className="text-slate-400">Formule :</span>
                  <span className="font-medium text-white">
                    {transaction.plan_name || transaction.plan_id}
                  </span>
                </div>
              )}

              <div className="flex justify-between">
                <span className="text-slate-400">Date :</span>
                <span className="font-medium text-white">
                  {formatDate(transaction.created_at || new Date().toISOString())}
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
          {user ? (
            <>
              <Button
                onClick={() => navigate('/training')}
                className="w-full bg-emerald-600 hover:bg-emerald-700 transition-colors"
              >
                Accéder à mon entraînement
              </Button>
              <p className="text-sm text-slate-500">
                Redirection automatique dans 7 secondes...
              </p>
            </>
          ) : (
            // Abonnement rattaché à un compte, mais la session a été perdue en
            // route (paiement sur un autre appareil, navigateur relancé…).
            <>
              <Button
                onClick={() => navigate('/login')}
                className="w-full bg-emerald-600 hover:bg-emerald-700 transition-colors"
              >
                Me connecter pour commencer
              </Button>
              <p className="text-sm text-slate-400">
                Connecte-toi avec l'email et le mot de passe choisis avant le paiement.
              </p>
            </>
          )}

          <button
            onClick={() => navigate('/')}
            className="w-full flex items-center justify-center gap-2 text-slate-400 hover:text-white transition-colors text-sm"
          >
            <Home className="h-4 w-4" />
            Retour à l'accueil
          </button>
        </div>

        {/* Additional Info */}
        <div className="mt-6 pt-6 border-t border-white/[0.05]">
          <p className="text-xs text-slate-400">
            Un reçu de paiement t'a été envoyé par email.
            <br />
            Un souci pour accéder à ton abonnement ? Contacte-nous en indiquant
            l'identifiant de paiement ci-dessus.
          </p>
        </div>
      </div>
    </div>
  );
}

export default PaymentSuccess;
