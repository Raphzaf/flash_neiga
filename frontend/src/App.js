import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, Link, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Exam from "./pages/Exam";
import ExamDetails from "./pages/ExamDetails";
import Training from "./pages/Training";
import Mistakes from "./pages/Mistakes";
import TrapQuestions from "./pages/TrapQuestions";
import Profile from "./pages/Profile";
import ChatWidget from "./components/ChatWidget";
import Signs from "./pages/Signs";
import Stats from "./pages/Stats";
import Admin from "./pages/Admin";
import AdminCRM from "./pages/AdminCRM";
import Pricing from "./pages/Pricing";
import Subscribe from "./pages/Subscribe";
import Checkout from "./pages/Checkout";
import Courses from "./pages/Courses";
import PaymentSuccess from './pages/PaymentSuccess';
import PaymentFailure from './pages/PaymentFailure';
import { Toaster } from "sonner";
import axios from 'axios';
import Terms from "./pages/Terms";
import Privacy from "./pages/Privacy";
import Refund from "./pages/Refund";

const FullScreenLoader = ({ label }) => (
    <div className="flex h-screen items-center justify-center text-slate-900 dark:text-white">{label}</div>
);

// Écrans du tunnel : ils portent déjà leurs propres mentions légales, en
// cohérence avec leur fond. Le pied de page de l'application y ferait double
// emploi et casserait la continuité visuelle du parcours.
const FUNNEL_ROUTES = ['/login', '/register', '/subscribe', '/checkout', '/payment'];

const AppFooter = () => {
    const { pathname } = useLocation();
    if (FUNNEL_ROUTES.some((route) => pathname.startsWith(route))) return null;

    return (
        <footer className="relative z-10 border-t border-white/[0.05] bg-slate-950/50 backdrop-blur-md py-10">
            <div className="max-w-7xl mx-auto px-6">
                <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                    <div className="text-slate-500 text-xs font-medium tracking-widest">
                        © 2026 <span className="text-slate-200">FLASH NEIGA</span>
                    </div>

                    <nav className="flex flex-wrap justify-center gap-x-8 gap-y-2 text-[11px] uppercase tracking-[0.2em] font-bold">
                        <Link to="/conditions-generales" className="text-slate-400 hover:text-primary transition-colors">
                            CGU
                        </Link>
                        <Link to="/politique-confidentialite" className="text-slate-400 hover:text-primary transition-colors">
                            Confidentialité
                        </Link>
                        <Link to="/politique-remboursement" className="text-slate-400 hover:text-primary transition-colors">
                            Remboursement
                        </Link>
                    </nav>
                </div>
            </div>
        </footer>
    );
};

// Route accessible à tout compte connecté (y compris sans abonnement) :
// le tunnel d'abonnement et le profil en font partie.
const AuthenticatedRoute = () => {
    const { isAuthenticated, loading, hasAccess } = useAuth();
    const location = useLocation();

    if (loading) return <FullScreenLoader label="Chargement..." />;
    if (!isAuthenticated) return <Navigate to="/login" state={{ from: location }} replace />;
    return (
        <>
            <Outlet />
            {/* L'assistant reste disponible pour un abonné qui passe par son
                profil ; il n'a pas lieu d'être pendant le tunnel d'achat. */}
            {hasAccess && !location.pathname.startsWith('/checkout')
                && !location.pathname.startsWith('/subscribe') && <ChatWidget />}
        </>
    );
};

// Route de contenu : réservée aux élèves dont l'abonnement est actif (les
// administrateurs ne sont pas soumis au paywall). Sans abonnement, on envoie au
// choix d'une formule plutôt que d'attendre un 402 en pleine page.
const SubscribedRoute = () => {
    const { isAuthenticated, loading, subscription, subscriptionLoading, hasAccess } = useAuth();
    const location = useLocation();

    if (loading) return <FullScreenLoader label="Chargement..." />;
    if (!isAuthenticated) return <Navigate to="/login" state={{ from: location }} replace />;
    // On attend de connaître l'état réel de l'abonnement avant de trancher.
    if (subscriptionLoading || !subscription) return <FullScreenLoader label="Chargement..." />;
    if (!hasAccess) return <Navigate to="/subscribe" replace />;

    return (
        <>
            <Outlet />
            <ChatWidget />
        </>
    );
};

function App() {
  return (
    <AuthProvider>
  {/* On utilise une couleur solide profonde avec un dégradé radial CSS natif */}
  <div className="min-h-screen bg-slate-50 dark:bg-[#0c1a2e] text-slate-900 dark:text-slate-200 antialiased selection:bg-primary/30 relative">
    
    {/* Effet de lumière diffuse en arrière-plan (remplace le grain qui bugguait) */}
    <div className="fixed inset-0 overflow-hidden pointer-events-none">
      <div className="absolute -top-[10%] -left-[10%] w-[40%] h-[40%] rounded-full bg-sky-400/10 blur-[120px]" />
      <div className="absolute bottom-[10%] right-[10%] w-[30%] h-[30%] rounded-full bg-yellow-400/10 blur-[100px]" />
    </div>

    <BrowserRouter>
      <div className="relative z-10 flex flex-col min-h-screen">
        <main className="flex-grow">
          <Routes>
            {/* ===== Tunnel : compte → formule → paiement ===== */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/pricing" element={<Pricing />} />
            <Route path="/payment/success" element={<PaymentSuccess />} />
            <Route path="/payment/failure" element={<PaymentFailure />} />

            {/* Pages légales */}
            <Route path="/conditions-generales" element={<Terms />} />
            <Route path="/politique-confidentialite" element={<Privacy />} />
            <Route path="/politique-remboursement" element={<Refund />} />

            {/* Anciennes URLs : conservées pour ne casser aucun lien déjà
                envoyé, mais elles rejoignent le parcours unique. */}
            <Route path="/pricing/success" element={<Navigate to="/payment/success" replace />} />
            <Route path="/subscription-success" element={<Navigate to="/payment/success" replace />} />
            <Route path="/pricing/cancel" element={<Navigate to="/payment/failure" replace />} />

            {/* Connecté, avec ou sans abonnement */}
            <Route element={<AuthenticatedRoute />}>
              <Route path="/subscribe" element={<Subscribe />} />
              <Route path="/checkout" element={<Checkout />} />
              <Route path="/profile" element={<Profile />} />
            </Route>

            {/* Contenu réservé aux abonnés */}
            <Route element={<SubscribedRoute />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/exam" element={<Exam />} />
              <Route path="/exam/:id" element={<ExamDetails />} />
              <Route path="/training" element={<Training />} />
              <Route path="/mistakes" element={<Mistakes />} />
              <Route path="/questions-pieges" element={<TrapQuestions />} />
              <Route path="/courses" element={<Courses />} />
              <Route path="/signs" element={<Signs />} />
              <Route path="/stats" element={<Stats />} />
              <Route path="/admin" element={<Admin />} />
              <Route path="/admin/crm" element={<AdminCRM />} />
            </Route>

            {/* Aucune route morte : tout le reste revient à l'accueil. */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>

        <AppFooter />
      </div>
    </BrowserRouter>

    <Toaster 
      position="top-center" 
      toastOptions={{
        style: {
          background: 'rgba(15, 23, 42, 0.8)',
          color: '#fff',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '16px'
        },
      }} 
    />
  </div>
</AuthProvider>

  );
}

export default App;
