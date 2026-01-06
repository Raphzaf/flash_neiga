import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardHeader, CardContent, CardFooter } from '../components/ui/card';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import { Mail, Lock, Loader2, ArrowRight } from 'lucide-react'; // Icônes pour le "cachet"

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({ email: '', password: '' });
  const [rememberMe, setRememberMe] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    // ... (votre logique reste la même)
    setIsLoading(true);
    try {
      await login(email, password);
      toast.success('Ravi de vous revoir !');
      navigate('/');
    } catch (error) {
      toast.error('Identifiants incorrects.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-slate-900 via-slate-950 to-black px-4 overflow-hidden">
      
      {/* Orbes décoratifs en arrière-plan pour le côté "premium" */}
      <div className="absolute top-0 -left-4 w-72 h-72 bg-primary/20 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob" />
      <div className="absolute bottom-0 -right-4 w-72 h-72 bg-secondary/20 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-2000" />

      <Card className="relative z-10 w-full max-w-md bg-white/[0.03] backdrop-blur-xl border-white/[0.08] shadow-2xl rounded-[2rem] overflow-hidden">
        <CardHeader className="text-center space-y-4 pt-10 pb-6">
          <div className="mx-auto w-16 h-16 rounded-2xl bg-gradient-to-tr from-primary to-violet-500 p-[1px] shadow-lg shadow-primary/20">
            <div className="w-full h-full rounded-2xl bg-slate-950 flex items-center justify-center">
              <img src="/brand-logo.svg" alt="Logo" className="h-8 w-8 brightness-125" />
            </div>
          </div>
          
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight text-white">
              Flash Neiga
            </h1>
            <p className="text-sm text-slate-400 font-light">
              L'art de capturer l'instant.
            </p>
          </div>
        </CardHeader>

        <CardContent className="px-8 pb-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-400 ml-1" htmlFor="email">
                Email Professionnel
              </Label>
              <div className="relative group">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 group-focus-within:text-primary transition-colors" />
                <Input
                  id="email"
                  type="email"
                  placeholder="nom@exemple.com"
                  className="pl-10 bg-white/[0.05] border-white/[0.1] text-white rounded-xl h-12 focus:ring-primary/50 transition-all duration-300"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="px-1">
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-400" htmlFor="password">
                  Mot de passe
                </Label>
              </div>
              <div className="relative group">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 group-focus-within:text-primary transition-colors" />
                <Input
                  id="password"
                  type="password"
                  className="pl-10 bg-white/[0.05] border-white/[0.1] text-white rounded-xl h-12 focus:ring-primary/50 transition-all duration-300"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            <div className="flex items-center space-x-2 px-1">
              <Checkbox id="remember" checked={rememberMe} onCheckedChange={(v) => setRememberMe(!!v)} className="border-white/20 data-[state=checked]:bg-primary" />
              <label htmlFor="remember" className="text-sm text-slate-400 cursor-pointer select-none">
                Rester connecté
              </label>
            </div>

            <Button
              type="submit"
              disabled={isLoading}
              className="w-full h-12 rounded-xl bg-primary hover:bg-primary/90 text-white font-bold text-base shadow-lg shadow-primary/25 transition-all active:scale-[0.98]"
            >
              {isLoading ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <span className="flex items-center gap-2">
                  Se connecter <ArrowRight className="h-4 w-4" />
                </span>
              )}
            </Button>
          </form>
        </CardContent>

        <CardFooter className="bg-white/[0.02] border-t border-white/[0.05] py-6">
          <div className="w-full text-center">
            <p className="text-sm text-slate-300">
              Nouveau ici ?{' '}
              <Link to="/register" className="text-primary font-semibold hover:text-primary/90 transition-colors underline-offset-4 hover:underline">
                Créer un compte
              </Link>
            </p>
          </div>
        </CardFooter>
      </Card>
    </main>
  );
}
