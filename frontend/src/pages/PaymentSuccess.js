import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import FunnelShell from '../components/funnel/FunnelShell';
import { TextField, PasswordField, FormError, Notice } from '../components/funnel/fields';
import { Button } from '../components/ui/button';
import { forgetPlan, formatDate, formatPrice, rememberEmail, readRememberedEmail } from '../lib/funnel';
import { CheckCircle2, Loader2 } from 'lucide-react';

const MAX_POLLING_ATTEMPTS = 10;
const POLLING_INTERVAL_MS = 2000;

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
      await onDone(data.access_token, email.trim());
    } catch (err) {
      setError(err?.response?.data?.detail || "Impossible de finaliser ton accès. Réessaie ou contacte-nous.");
      setSubmitting(false);
    }
  };

  return (
    <FunnelShell
      step={3}
      title="Paiement bien reçu"
      subtitle="Dernière étape : choisis ton mot de passe pour ouvrir ton accès."
    >
      <form onSubmit={submit} className="space-y-4">
        <Notice tone="success">
          Ton abonnement est payé. Il ne reste qu'à créer tes identifiants
          {emailHint ? <> — utilise de préférence l'email du paiement ({emailHint}).</> : '.'}
        </Notice>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <TextField label="Prénom" placeholder="Sarah" autoComplete="given-name" autoFocus required
            value={firstName} onChange={(e) => setFirstName(e.target.value)} />
          <TextField label="Nom" placeholder="Cohen" autoComplete="family-name" required
            value={lastName} onChange={(e) => setLastName(e.target.value)} />
        </div>
        <TextField label="Email" type="email" placeholder="nom@exemple.com" autoComplete="email"
          inputMode="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <PasswordField label="Mot de passe" placeholder="Au moins 6 caractères" autoComplete="new-password"
          minLength={6} required value={password} onChange={(e) => setPassword(e.target.value)}
          hint="C'est celui qui te servira à te connecter." />

        <FormError>{error}</FormError>

        <Button type="submit" className="h-10 w-full" disabled={submitting}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Activer mon accès'}
        </Button>
      </form>
    </FunnelShell>
  );
}

export default function PaymentSuccess() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, loginWithToken, refreshSubscription } = useAuth();

  const [transaction, setTransaction] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pollAttempt, setPollAttempt] = useState(0);
  const timers = useRef([]);

  // HYP renvoie l'identifiant de commande dans `Order` ; nos propres URLs
  // utilisent `transaction_id`. Les deux sont acceptés.
  const transactionId = searchParams.get('transaction_id') || searchParams.get('Order');

  useEffect(() => {
    let cancelled = false;
    const schedule = (fn, delay) => { timers.current.push(setTimeout(fn, delay)); };

    // Si HYP a renvoyé le résultat dans l'URL (CCode), on le transmet au backend
    // pour que l'abonnement soit ouvert même si la notification serveur à
    // serveur n'est pas configurée. La signature est vérifiée côté serveur.
    const notifyBackend = async () => {
      if (searchParams.get('CCode') === null) return;
      try {
        await axios.post('/api/payments/hyp/callback', Object.fromEntries(searchParams.entries()));
      } catch (err) {
        console.warn('Notification du paiement échouée (le sondage prend le relais):', err?.response?.status);
      }
    };

    const fetchTransaction = async (attempt = 0) => {
      if (cancelled) return;
      if (!transactionId) {
        setError("Nous n'avons pas retrouvé la référence de ton paiement.");
        setLoading(false);
        return;
      }
      try {
        const { data } = await axios.get(`/api/payments/hyp/transaction/${transactionId}`);
        if (data.status === 'completed' || attempt >= MAX_POLLING_ATTEMPTS) {
          setTransaction(data);
          setLoading(false);
          if (data.status === 'completed') {
            forgetPlan();
            // L'abonnement vient peut-être d'être ouvert : on rafraîchit l'état
            // côté serveur plutôt que de le supposer.
            refreshSubscription();
          }
        } else {
          setPollAttempt(attempt + 1);
          schedule(() => fetchTransaction(attempt + 1), POLLING_INTERVAL_MS);
        }
      } catch (err) {
        if (attempt < MAX_POLLING_ATTEMPTS) {
          setPollAttempt(attempt + 1);
          schedule(() => fetchTransaction(attempt + 1), POLLING_INTERVAL_MS);
        } else {
          setError("Nous n'arrivons pas à confirmer ton paiement pour le moment.");
          setLoading(false);
        }
      }
    };

    notifyBackend().finally(() => fetchTransaction());

    const scheduled = timers.current;
    return () => {
      cancelled = true;
      scheduled.forEach(clearTimeout);
    };
  }, [transactionId, searchParams, refreshSubscription]);

  const handleClaimed = useCallback(async (accessToken, email) => {
    rememberEmail(email);
    await loginWithToken(accessToken);
    navigate('/', { replace: true });
  }, [loginWithToken, navigate]);

  if (loading) {
    return (
      <FunnelShell step={3} title="Validation de ton paiement" subtitle="Encore quelques secondes…">
        <div className="flex flex-col items-center gap-2 py-6 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          {pollAttempt > 0 && <p className="text-xs">Vérification {pollAttempt}/{MAX_POLLING_ATTEMPTS}</p>}
        </div>
      </FunnelShell>
    );
  }

  if (error) {
    return (
      <FunnelShell step={3} title="Paiement en attente de confirmation">
        <div className="space-y-4">
          <FormError>{error}</FormError>
          <p className="text-sm text-muted-foreground">
            Si ta carte a été débitée, ton accès sera ouvert automatiquement. Écris-nous à{' '}
            <a href="mailto:support@flash-neiga.com" className="underline hover:text-foreground">support@flash-neiga.com</a>
            {transactionId && <> en indiquant la référence <span className="font-mono">{transactionId.slice(0, 8)}</span></>}.
          </p>
          <Button variant="outline" className="w-full" asChild>
            <Link to="/subscribe">Revenir aux formules</Link>
          </Button>
        </div>
      </FunnelShell>
    );
  }

  // Paiement encaissé sans compte rattaché : on ouvre l'accès ici, tout de suite.
  if (transaction?.needs_account) {
    return (
      <ClaimAccessForm
        transactionId={transaction.id}
        emailHint={transaction.email_hint}
        onDone={handleClaimed}
      />
    );
  }

  const pending = transaction?.status !== 'completed';
  const sub = transaction?.subscription;
  const loginEmail = user?.email || readRememberedEmail() || '';

  return (
    <FunnelShell
      step={3}
      title={pending ? 'Paiement en cours de validation' : 'Ton abonnement est actif'}
      subtitle={
        pending
          ? "Ta banque n'a pas encore confirmé le paiement. Ton accès s'ouvrira dès validation."
          : 'Merci ! Tout est en place, tu peux commencer.'
      }
    >
      <div className="space-y-5">
        {!pending && (
          <div className="flex justify-center">
            <CheckCircle2 className="h-10 w-10 text-emerald-600 dark:text-emerald-400" />
          </div>
        )}

        <dl className="space-y-2 rounded-lg border border-slate-200 p-4 text-sm dark:border-slate-700">
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Formule</dt>
            <dd className="text-right text-slate-900 dark:text-slate-200">
              {sub?.plan_name || transaction?.plan_name || '—'}
            </dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Montant</dt>
            <dd className="text-slate-900 dark:text-slate-200">
              {formatPrice(transaction?.amount, transaction?.currency)}
            </dd>
          </div>
          {sub?.end_date && (
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Accès jusqu'au</dt>
              <dd className="font-medium text-slate-900 dark:text-white">{formatDate(sub.end_date)}</dd>
            </div>
          )}
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Référence</dt>
            <dd className="font-mono text-xs text-muted-foreground">{transaction?.id?.slice(0, 8)}</dd>
          </div>
        </dl>

        {user ? (
          <Button className="h-10 w-full" asChild>
            <Link to="/">Accéder à la plateforme</Link>
          </Button>
        ) : (
          <>
            <Button className="h-10 w-full" asChild>
              <Link to={`/login?reason=payment-success${loginEmail ? `&email=${encodeURIComponent(loginEmail)}` : ''}`}>
                Me connecter
              </Link>
            </Button>
            <p className="text-center text-xs text-muted-foreground">
              Connecte-toi avec l'email et le mot de passe choisis à l'inscription.
            </p>
          </>
        )}

        <p className="text-center text-xs text-muted-foreground">
          Un reçu t'a été envoyé par email. Un souci d'accès ? Écris-nous à{' '}
          <a href="mailto:support@flash-neiga.com" className="underline hover:text-foreground">support@flash-neiga.com</a>{' '}
          en indiquant ta référence de paiement.
        </p>
      </div>
    </FunnelShell>
  );
}
