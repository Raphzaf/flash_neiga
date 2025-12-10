import React, { useState } from 'react';
import { Sparkles } from 'lucide-react';
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
    const [fullName, setFullName] = useState('');
    const { register } = useAuth();
    const navigate = useNavigate();
    const [isLoading, setIsLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            await register(email, password, fullName);
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
                        <div className="space-y-2">
                            <Label htmlFor="fullname">Nom complet</Label>
                            <Input 
                                id="fullname" 
                                type="text" 
                                placeholder="John Doe"
                                value={fullName}
                                onChange={(e) => setFullName(e.target.value)}
                                required
                                data-testid="register-name-input"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="email">Email</Label>
                            <Input 
                                id="email" 
                                type="email" 
                                placeholder="votre@email.com" 
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                data-testid="register-email-input"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="password">Mot de passe</Label>
                            <Input 
                                id="password" 
                                type="password" 
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                data-testid="register-password-input"
                            />
                        </div>
                        <Button 
                            type="submit" 
                            className="w-full" 
                            disabled={isLoading}
                            data-testid="register-submit-button"
                        >
                            {isLoading ? 'Chargement...' : "S'inscrire"}
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

            {/* Optional: embedded pricing table if configured */}
            {process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY && process.env.REACT_APP_STRIPE_PRICING_TABLE_ID && (
                <div className="mt-6">
                    <stripe-pricing-table
                        pricing-table-id={process.env.REACT_APP_STRIPE_PRICING_TABLE_ID}
                        publishable-key={process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY}
                    >
                    </stripe-pricing-table>
                </div>
            )}
            </Card>
        </div>
    );
}
