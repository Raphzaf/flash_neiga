import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, Link } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Exam from "./pages/Exam";
import ExamDetails from "./pages/ExamDetails";
import Training from "./pages/Training";
import Signs from "./pages/Signs";
import Stats from "./pages/Stats";
import Admin from "./pages/Admin";
import Pricing from "./pages/Pricing";
import SubscriptionSuccess from './pages/SubscriptionSuccess';
import { Toaster } from "sonner";
import axios from 'axios';
import Terms from "./pages/Terms";
import Privacy from "./pages/Privacy";
import Refund from "./pages/Refund";

// Protected Route Component
const ProtectedRoute = () => {
    const { isAuthenticated, loading } = useAuth();
    
    if (loading) return <div className="flex h-screen items-center justify-center">Chargement...</div>;
    
    return isAuthenticated ? <Outlet /> : <Navigate to="/login" />;
};

function App() {
  const RegisterGate = () => {
    const [allowed, setAllowed] = useState(null);
    useEffect(() => {
      const params = new URLSearchParams(window.location.search);
      const provider = params.get('provider');
      // Allow only Paddle provider to proceed (Stripe removed)
      if (provider === 'paddle') {
        setAllowed(true);
      } else {
        setAllowed(false);
      }
    }, []);
    if (allowed === null) return <div className="flex h-screen items-center justify-center">Vérification du paiement...</div>;
    return allowed ? <Register /> : <Navigate to="/pricing" />;
  };
  return (
    <AuthProvider>
      <div className="min-h-screen bg-background text-foreground antialiased">
        <BrowserRouter>
            <Routes>
                <Route path="/login" element={<Login />} />
                {/* Registration gated: requires Paddle provider flag */}
                <Route path="/register" element={<RegisterGate />} />
                {/* Conditions générales (public) */}
                <Route path="/conditions-generales" element={<Terms />} />
                {/* Politique de confidentialité (public) */}
                <Route path="/politique-confidentialite" element={<Privacy />} />
                {/* Politique de remboursement (public) */}
                <Route path="/politique-remboursement" element={<Refund />} />
              {/* Public pricing routes so users can view plans before login */}
              <Route path="/pricing" element={<Pricing />} />
              <Route path="/pricing/success" element={<div className='p-6'>Paiement réussi. Merci ! Vous pouvez gérer votre abonnement ci-dessous.</div>} />
              <Route path="/subscription-success" element={<SubscriptionSuccess />} />
              <Route path="/pricing/cancel" element={<div className='p-6'>Paiement annulé. Réessayez quand vous êtes prêt.</div>} />
                
                <Route element={<ProtectedRoute />}>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/exam" element={<Exam />} />
                  <Route path="/exam/:id" element={<ExamDetails />} />
                    <Route path="/training" element={<Training />} />
                    <Route path="/signs" element={<Signs />} />
                    <Route path="/stats" element={<Stats />} />
                    <Route path="/admin" element={<Admin />} />
                </Route>
            </Routes>
            <footer className="mt-12 border-t py-6 text-center text-sm text-muted-foreground space-x-4">
              <Link to="/conditions-generales" className="hover:underline">Conditions générales</Link>
              <span>•</span>
              <Link to="/politique-confidentialite" className="hover:underline">Politique de confidentialité</Link>
              <span>•</span>
              <Link to="/politique-remboursement" className="hover:underline">Politique de remboursement</Link>
            </footer>
        </BrowserRouter>
        <Toaster position="top-center" />
      </div>
    </AuthProvider>
  );
}

export default App;
