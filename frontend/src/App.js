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

const AppFooter = () => {
    // Le pied de page suit le thème : en clair, il était rendu en dalle sombre,
    // ce qui coupait la page en deux.
    return (
        <footer className="relative z-10 border-t border-slate-200 py-8 dark:border-slate-800">
            <div className="mx-auto max-w-7xl px-6">
                <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                        © 2026 <span className="font-medium text-slate-700 dark:text-slate-200">Flash Neiga</span>
                    </div>

                    <nav className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-xs">
                        <Link to="/conditions-generales" className="text-slate-500 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-white">
                            CGU
                        </Link>
                        <Link to="/politique-confidentialite" className="text-slate-500 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-white">
                            Confidentialité
                        </Link>
                        <Link to="/politique-remboursement" className="text-slate-500 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-white">
                            Remboursement
                        </Link>
                    </nav>
                </div>
            </div>
        </footer>
    );
};

// La redirection vers la connexion explique pourquoi elle a lieu quand la
// session s'est invalidée en cours de route ; l'élève ne doit pas se retrouver
// devant un formulaire sans savoir ce qui s'est passé.
const loginRoute = (sessionExpired) => (sessionExpired ? '/login?reason=session' : '/login');

// Route accessible à tout compte connecté (y compris sans abonnement) :
// le tunnel d'abonnement et le profil en font partie.
const AuthenticatedRoute = () => {
    const { isAuthenticated, loading, hasAccess, sessionExpired } = useAuth();
    const location = useLocation();

    if (loading) return <FullScreenLoader label="Chargement..." />;
    if (!isAuthenticated) return <Navigate to={loginRoute(sessionExpired)} state={{ from: location }} replace />;
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
    const { isAuthenticated, loading, subscription, subscriptionLoading, hasAccess, sessionExpired } = useAuth();
    const location = useLocation();

    if (loading) return <FullScreenLoader label="Chargement..." />;
    if (!isAuthenticated) return <Navigate to={loginRoute(sessionExpired)} state={{ from: location }} replace />;
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
