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
    <main className="min-h-screen flex items-center justify-center relative px-4 overflow-hidden bg-gradient-to-br from-slate-950 via-blue-950 to-slate-900 animate-gradient">
      
      {/* Orbes décoratifs en arrière-plan pour le côté "premium" avec animations améliorées */}
      <div className="absolute top-10 -left-20 w-96 h-96 bg-gradient-to-br from-sky-500/30 to-blue-600/30 rounded-full mix-blend-screen filter blur-3xl opacity-40 animate-blob" />
      <div className="absolute bottom-10 -right-20 w-96 h-96 bg-gradient-to-br from-yellow-500/30 to-amber-600/30 rounded-full mix-blend-screen filter blur-3xl opacity-40 animate-blob animation-delay-2000" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-gradient-to-br from-sky-500/20 to-cyan-600/20 rounded-full mix-blend-screen filter blur-3xl opacity-30 animate-float animation-delay-4000" />
      
      {/* Particules décoratives subtiles */}
      <div className="absolute top-20 left-20 w-2 h-2 bg-white/30 rounded-full animate-glow-pulse" />
      <div className="absolute top-40 right-32 w-1 h-1 bg-sky-400/40 rounded-full animate-glow-pulse animation-delay-2000" />
      <div className="absolute bottom-32 left-40 w-1.5 h-1.5 bg-yellow-400/40 rounded-full animate-glow-pulse animation-delay-4000" />
      <div className="absolute bottom-20 right-20 w-2 h-2 bg-blue-400/30 rounded-full animate-glow-pulse" />

      <Card className="relative z-10 w-full max-w-md bg-white/[0.04] backdrop-blur-2xl border-white/[0.12] shadow-[0_8px_32px_0_rgba(0,0,0,0.4),0_0_60px_0_rgba(56,189,248,0.15)] rounded-[2rem] overflow-hidden animate-fade-in-up before:absolute before:inset-0 before:rounded-[2rem] before:p-[1px] before:bg-gradient-to-br before:from-white/20 before:via-white/5 before:to-transparent before:-z-10">
        <CardHeader className="text-center space-y-4 pt-10 pb-6">
          <div className="mx-auto w-16 h-16 rounded-2xl bg-gradient-to-tr from-sky-500 via-blue-500 to-cyan-600 p-[1px] shadow-lg shadow-sky-500/40 animate-glow-pulse">
            <div className="w-full h-full rounded-2xl bg-slate-950 flex items-center justify-center">
              <img src="/brand-logo.svg" alt="Logo" className="h-8 w-8 brightness-125 filter drop-shadow-[0_0_8px_rgba(56,189,248,0.5)]" />
            </div>
          </div>
          
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-white via-sky-200 to-white bg-clip-text text-transparent filter drop-shadow-[0_2px_8px_rgba(255,255,255,0.3)]">
              Flash Neiga
            </h1>
          </div>
        </CardHeader>

        <CardContent className="px-8 pb-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-200 ml-1" htmlFor="email">
                Email Professionnel
              </Label>
              <div className="relative group">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 group-focus-within:text-sky-400 transition-all duration-300 group-focus-within:drop-shadow-[0_0_6px_rgba(56,189,248,0.6)]" />
                <Input
                  id="email"
                  type="email"
                  placeholder="nom@exemple.com"
                  className="pl-10 bg-white/[0.06] border-white/[0.12] text-white placeholder:text-slate-500 rounded-xl h-12 transition-all duration-300 focus:border-sky-400/50 focus:ring-4 focus:ring-sky-500/20 focus:bg-white/[0.08] focus:shadow-[0_0_20px_rgba(56,189,248,0.15)] hover:border-white/[0.18]"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="px-1">
                <Label className="text-xs font-semibold uppercase tracking-wider text-slate-200" htmlFor="password">
                  Mot de passe
                </Label>
              </div>
              <div className="relative group">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 group-focus-within:text-sky-400 transition-all duration-300 group-focus-within:drop-shadow-[0_0_6px_rgba(56,189,248,0.6)]" />
                <Input
                  id="password"
                  type="password"
                  className="pl-10 bg-white/[0.06] border-white/[0.12] text-white placeholder:text-slate-500 rounded-xl h-12 transition-all duration-300 focus:border-sky-400/50 focus:ring-4 focus:ring-sky-500/20 focus:bg-white/[0.08] focus:shadow-[0_0_20px_rgba(56,189,248,0.15)] hover:border-white/[0.18]"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            <div className="flex items-center space-x-2 px-1">
              <Checkbox id="remember" checked={rememberMe} onCheckedChange={(v) => setRememberMe(!!v)} className="border-white/30 data-[state=checked]:bg-gradient-to-br data-[state=checked]:from-sky-500 data-[state=checked]:to-blue-600 data-[state=checked]:border-sky-400/50 transition-all duration-200" />
              <label htmlFor="remember" className="text-sm text-slate-300 cursor-pointer select-none hover:text-white transition-colors">
                Rester connecté
              </label>
            </div>

            <Button
              type="submit"
              disabled={isLoading}
              className="w-full h-12 rounded-xl bg-gradient-to-r from-sky-500 via-blue-500 to-cyan-600 hover:from-sky-400 hover:via-blue-400 hover:to-cyan-500 text-white font-bold text-base shadow-[0_0_30px_rgba(56,189,248,0.4)] transition-all duration-300 active:scale-[0.98] hover:scale-[1.02] hover:shadow-[0_0_40px_rgba(56,189,248,0.6)] relative overflow-hidden group disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              <span className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000" />
              {isLoading ? (
                <Loader2 className="h-5 w-5 animate-spin relative z-10" />
              ) : (
                <span className="flex items-center gap-2 relative z-10">
                  Se connecter <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform duration-300" />
                </span>
              )}
            </Button>
          </form>
        </CardContent>

        <CardFooter className="bg-white/[0.03] border-t border-white/[0.08] py-6 backdrop-blur-sm">
          <div className="w-full text-center">
            <p className="text-sm text-slate-300">
              Nouveau ici ?{' '}
              <Link to="/register" className="text-transparent bg-gradient-to-r from-sky-400 to-cyan-400 bg-clip-text font-semibold hover:from-sky-300 hover:to-cyan-300 transition-all duration-300 underline-offset-4 hover:underline hover:drop-shadow-[0_0_8px_rgba(56,189,248,0.5)]">
                Créer un compte
              </Link>
            </p>
          </div>
        </CardFooter>
      </Card>
    </main>
  );
}
