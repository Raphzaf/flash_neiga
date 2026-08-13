import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, useLocation, useSearchParams, Link } from 'react-router-dom';
import FunnelShell from '../components/funnel/FunnelShell';
import { TextField, PasswordField, FormError, Notice, primaryButtonClass, secondaryButtonClass } from '../components/funnel/fields';
import { readRememberedEmail } from '../lib/funnel';
import { ArrowRight, Loader2, UserPlus } from 'lucide-react';

// Message d'accueil selon la raison qui a amené l'élève ici : il doit toujours
// comprendre pourquoi on lui demande de se connecter.
const REASONS = {
  'payment-success': {
    tone: 'success',
    text: 'Ton abonnement est actif. Connecte-toi avec le mot de passe choisi à l\'inscription pour commencer.',
  },
  subscribe: { tone: 'info', text: 'Connecte-toi pour choisir ta formule et accéder à la plateforme.' },
  session: { tone: 'info', text: 'Ta session a expiré. Reconnecte-toi pour reprendre où tu en étais.' },
};

export default function Login() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { login, isAuthenticated, hasAccess, loading, subscription, subscriptionLoading } = useAuth();

  const [email, setEmail] = useState(searchParams.get('email') || readRememberedEmail() || '');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const reason = REASONS[searchParams.get('reason')];
  // Destination demandée avant la redirection vers la connexion (route protégée).
  const from = location.state?.from?.pathname;

  // Déjà connecté : on ne réaffiche pas un formulaire de connexion. La
  // destination dépend de l'abonnement — on attend donc de le connaître, sinon
  // un élève à jour serait renvoyé vers le tunnel d'achat le temps d'un rendu.
  useEffect(() => {
    if (loading || !isAuthenticated) return;
    if (subscriptionLoading || !subscription) return;
    navigate(from || (hasAccess ? '/' : '/subscribe'), { replace: true });
  }, [loading, isAuthenticated, subscription, subscriptionLoading, hasAccess, from, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await login(email.trim(), password);
      // La redirection est portée par l'effet ci-dessus, une fois l'état
      // d'abonnement connu : on ne devine jamais où envoyer l'élève.
    } catch (err) {
      setError(err?.response?.data?.detail || 'Email ou mot de passe incorrect.');
      setIsLoading(false);
    }
  };

  return (
    <FunnelShell
      title="Content de te revoir"
      subtitle="Connecte-toi à ton espace Flash Neiga."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {reason && <Notice tone={reason.tone}>{reason.text}</Notice>}

        <TextField
          label="Email"
          type="email"
          placeholder="nom@exemple.com"
          autoComplete="email"
          inputMode="email"
          autoFocus={!email}
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <PasswordField
          label="Mot de passe"
          placeholder="Ton mot de passe"
          autoComplete="current-password"
          autoFocus={!!email}
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <FormError>{error}</FormError>

        <button type="submit" disabled={isLoading || !email || !password} className={primaryButtonClass}>
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Se connecter <ArrowRight className="h-4 w-4" /></>}
        </button>

        <div className="flex items-center gap-3 py-1">
          <span className="h-px flex-1 bg-white/20" />
          <span className="text-xs uppercase tracking-wider text-white/50">ou</span>
          <span className="h-px flex-1 bg-white/20" />
        </div>

        <Link to="/register" className={secondaryButtonClass}>
          <UserPlus className="h-4 w-4" /> Je n'ai pas encore de compte
        </Link>

        <p className="pt-1 text-center text-xs text-white/70">
          Mot de passe oublié ? Écris-nous à{' '}
          <a href="mailto:support@flash-neiga.com" className="underline hover:text-white">support@flash-neiga.com</a>,
          on te réinitialise l'accès.
        </p>
      </form>
    </FunnelShell>
  );
}
