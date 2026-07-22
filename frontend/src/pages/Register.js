import React, { useState } from 'react';
import { Sparkles, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardHeader, CardContent, CardFooter } from '../components/ui/card';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';

export default function Register() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const { register } = useAuth();
    const navigate = useNavigate();
    const [isLoading, setIsLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (password.length < 6) {
            toast.error("Ton mot de passe doit contenir au moins 6 caractères.");
            return;
        }
        setIsLoading(true);
        try {
            await register(email, password, firstName, lastName);
            toast.success("Compte créé avec succès !");
            navigate('/');
        } catch (error) {
            toast.error("Erreur lors de l'inscription. L'email est peut-être déjà utilisé.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex h-screen items-center justify-center p-4 bg-slate-50 dark:bg-slate-950">
            <Card className="w-full max-w-md shadow-lg border-0">
                <CardHeader className="space-y-1 text-center">
                    <h1 className="text-3xl font-heading font-bold text-primary">Flash Neiga</h1>
                    <p className="text-muted-foreground">Créez un compte pour commencer</p>
                    <div className="mt-3">
                    <Link to="/pricing" className="text-primary hover:underline" data-testid="register-view-pricing-link">
                        Voir les abonnements
                    </Link>
                    </div>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div className="space-y-2">
                                <Label htmlFor="firstname">Prénom</Label>
                                <Input
                                    id="firstname"
                                    type="text"
                                    placeholder="Ex : Sarah"
                                    autoComplete="given-name"
                                    autoFocus
                                    value={firstName}
                                    onChange={(e) => setFirstName(e.target.value)}
                                    required
                                    data-testid="register-firstname-input"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="lastname">Nom</Label>
                                <Input
                                    id="lastname"
                                    type="text"
                                    placeholder="Ex : Cohen"
                                    autoComplete="family-name"
                                    value={lastName}
                                    onChange={(e) => setLastName(e.target.value)}
                                    required
                                    data-testid="register-lastname-input"
                                />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="email">Email</Label>
                            <Input
                                id="email"
                                type="email"
                                placeholder="votre@email.com"
                                autoComplete="email"
                                inputMode="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                data-testid="register-email-input"
                            />
                            <p className="text-xs text-muted-foreground">Tu recevras tes accès et le suivi de ta progression sur cet email.</p>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="password">Mot de passe</Label>
                            <div className="relative">
                                <Input
                                    id="password"
                                    type={showPassword ? 'text' : 'password'}
                                    placeholder="Au moins 6 caractères"
                                    autoComplete="new-password"
                                    minLength={6}
                                    className="pr-10"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                    data-testid="register-password-input"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword((v) => !v)}
                                    aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                                >
                                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                </button>
                            </div>
                            <p className="text-xs text-muted-foreground">Choisis un mot de passe d'au moins 6 caractères.</p>
                        </div>
                        <Button
                            type="submit"
                            className="w-full"
                            disabled={isLoading || !firstName || !lastName || !email || !password}
                            data-testid="register-submit-button"
                        >
                            {isLoading ? 'Création du compte…' : "Créer mon compte"}
                        </Button>
                    </form>
                </CardContent>
                <CardFooter className="justify-center">
                    <p className="text-sm text-muted-foreground">
                        Déjà un compte ? <Link to="/login" className="text-primary hover:underline">Se connecter</Link>
                    </p>
                </CardFooter>
            {/* Abonnements highlight */}
            <div className="mt-8">
                <div className="rounded-2xl p-5 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-500 text-white shadow-lg">
                    <div className="flex items-center gap-2 mb-2">
                        <Sparkles className="h-5 w-5" />
                        <span className="text-sm uppercase tracking-wide opacity-90">Abonnements</span>
                    </div>
                    <div className="text-lg font-bold mb-2">Passez à la vitesse supérieure</div>
                    <div className="text-sm opacity-90 mb-4">Accédez aux examens illimités, suivi détaillé, et bien plus.</div>
                    <div className="flex gap-3">
                        <Link to="/pricing">
                            <Button variant="secondary" className="bg-white/90 text-indigo-700 hover:bg-white font-bold">Voir les abonnements</Button>
                        </Link>
                        <Link to="/pricing">
                            <Button variant="outline" className="border-white/60 text-white hover:bg-white/10">Comparer les offres</Button>
                        </Link>
                    </div>
                </div>
            </div>

            {/* Stripe pricing table removed */}
            </Card>
        </div>
    );
}
