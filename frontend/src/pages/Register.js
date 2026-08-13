import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import FunnelShell from '../components/funnel/FunnelShell';
import { TextField, PasswordField, FormError } from '../components/funnel/fields';
import { Button } from '../components/ui/button';
import { rememberPlan, readRememberedPlan } from '../lib/funnel';
import { Loader2 } from 'lucide-react';

const MIN_PASSWORD_LENGTH = 6;

export default function Register() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { register, isAuthenticated, loading } = useAuth();

    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    // Formule éventuellement choisie avant la création du compte (depuis la page
    // Formules) : elle est conservée pour reprendre le parcours au bon endroit.
    const planFromUrl = searchParams.get('plan');
    useEffect(() => {
        if (planFromUrl) rememberPlan(planFromUrl);
    }, [planFromUrl]);

    // Un compte déjà connecté n'a rien à faire sur la création de compte.
    useEffect(() => {
        if (!loading && isAuthenticated) navigate('/subscribe', { replace: true });
    }, [loading, isAuthenticated, navigate]);

    const nextStep = () => {
        const plan = planFromUrl || readRememberedPlan();
        return plan ? `/checkout?plan=${encodeURIComponent(plan)}` : '/subscribe';
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        if (password.length < MIN_PASSWORD_LENGTH) {
            setError(`Ton mot de passe doit contenir au moins ${MIN_PASSWORD_LENGTH} caractères.`);
            return;
        }
        setIsLoading(true);
        try {
            await register(email.trim(), password, firstName.trim(), lastName.trim());
            // Le compte est créé ET la session ouverte : on enchaîne directement
            // sur la suite du parcours, sans repasser par la connexion.
            navigate(nextStep(), { replace: true });
        } catch (err) {
            const detail = err?.response?.data?.detail;
            setError(
                typeof detail === 'string'
                    ? detail
                    : "Impossible de créer le compte. Cet email est peut-être déjà utilisé."
            );
            setIsLoading(false);
        }
    };

    return (
        <FunnelShell
            step={1}
            title="Créer mon compte"
            subtitle="Ton compte, ta formule, et tu commences."
            footer={
                <>
                    Tu as déjà un compte ?{' '}
                    <Link to="/login" className="font-medium text-foreground underline underline-offset-4">
                        Se connecter
                    </Link>
                </>
            }
        >
            <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <TextField
                        label="Prénom"
                        placeholder="Sarah"
                        autoComplete="given-name"
                        autoFocus
                        required
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                        data-testid="register-firstname-input"
                    />
                    <TextField
                        label="Nom"
                        placeholder="Cohen"
                        autoComplete="family-name"
                        required
                        value={lastName}
                        onChange={(e) => setLastName(e.target.value)}
                        data-testid="register-lastname-input"
                    />
                </div>

                <TextField
                    label="Email"
                    type="email"
                    placeholder="nom@exemple.com"
                    autoComplete="email"
                    inputMode="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    hint="C'est aussi ton identifiant de connexion."
                    data-testid="register-email-input"
                />

                <PasswordField
                    label="Mot de passe"
                    placeholder={`Au moins ${MIN_PASSWORD_LENGTH} caractères`}
                    autoComplete="new-password"
                    minLength={MIN_PASSWORD_LENGTH}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    hint="Garde-le : c'est avec lui que tu te connecteras après le paiement."
                    data-testid="register-password-input"
                />

                <FormError>{error}</FormError>

                <Button
                    type="submit"
                    className="h-10 w-full"
                    disabled={isLoading || !firstName || !lastName || !email || !password}
                    data-testid="register-submit-button"
                >
                    {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Continuer'}
                </Button>

                <p className="text-center text-xs text-muted-foreground">
                    En créant ton compte, tu acceptes nos{' '}
                    <Link to="/conditions-generales" className="underline hover:text-foreground">
                        conditions générales
                    </Link>.
                </p>
            </form>
        </FunnelShell>
    );
}
