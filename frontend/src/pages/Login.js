import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardHeader, CardContent, CardFooter } from '../components/ui/card';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';

export default function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [errors, setErrors] = useState({ email: '', password: '' });
    const { login } = useAuth();
    const navigate = useNavigate();
    const [isLoading, setIsLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        // Front validations
        const nextErrors = { email: '', password: '' };
        // Basic email format check (HTML5 will also validate type="email")
        if (!email) {
            nextErrors.email = 'Veuillez renseigner votre email.';
        }
        // Password minimum length for UX feedback
        if (!password) {
            nextErrors.password = 'Veuillez renseigner votre mot de passe.';
        }
        setErrors(nextErrors);
        if (nextErrors.email || nextErrors.password) {
            return; // Do not submit if client-side validation fails
        }

        setIsLoading(true);
        try {
            await login(email, password);
            toast.success("Connexion réussie !");
            navigate('/');
        } catch (error) {
            toast.error("Erreur de connexion. Vérifiez vos identifiants.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <main className="flex h-screen items-center justify-center p-4 bg-slate-50 dark:bg-slate-950">
            <Card className="w-full max-w-md shadow-lg border-0" aria-labelledby="login-title" aria-describedby="login-subtitle">
                <CardHeader className="space-y-1 text-center">
                    <h1 id="login-title" className="text-3xl font-heading font-bold text-primary">Flash Neiga</h1>
                    <h2 id="login-subtitle" className="text-base font-medium text-muted-foreground">Connectez-vous pour accéder à votre entraînement</h2>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
                        <div className="space-y-2">
                            <Label htmlFor="email">Email</Label>
                            <Input 
                                id="email" 
                                type="email" 
                                placeholder="votre@email.com" 
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                aria-required="true"
                                aria-invalid={Boolean(errors.email)}
                                aria-describedby={errors.email ? 'email-error' : undefined}
                                data-testid="login-email-input"
                            />
                            {errors.email && (
                                <p id="email-error" className="text-sm text-red-600 mt-1">{errors.email}</p>
                            )}
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="password">Mot de passe</Label>
                            <Input 
                                id="password" 
                                type="password" 
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                aria-required="true"
                                aria-invalid={Boolean(errors.password)}
                                aria-describedby={errors.password ? 'password-error' : undefined}
                                data-testid="login-password-input"
                            />
                            {errors.password && (
                                <p id="password-error" className="text-sm text-red-600 mt-1">{errors.password}</p>
                            )}
                        </div>
                        <Button 
                            type="submit" 
                            className="w-full" 
                            disabled={isLoading}
                            data-testid="login-submit-button"
                        >
                            {isLoading ? 'Chargement...' : 'Se connecter'}
                        </Button>
                    </form>
                </CardContent>
                <CardFooter className="justify-center">
                    <section aria-label="Inscription">
                        <p className="text-sm text-muted-foreground">
                            Pas encore de compte ? <Link to="/pricing" className="text-primary hover:underline">Voir les abonnements</Link>
                        </p>
                    </section>
                </CardFooter>
            </Card>
        </main>
    );
}
