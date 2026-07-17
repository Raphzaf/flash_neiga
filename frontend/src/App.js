import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, Link } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Exam from "./pages/Exam";
import ExamDetails from "./pages/ExamDetails";
import Training from "./pages/Training";
import Mistakes from "./pages/Mistakes";
import Signs from "./pages/Signs";
import Stats from "./pages/Stats";
import Admin from "./pages/Admin";
import Pricing from "./pages/Pricing";
import Courses from "./pages/Courses";
import SubscriptionSuccess from './pages/SubscriptionSuccess';
import PaymentSuccess from './pages/PaymentSuccess';
import PaymentFailure from './pages/PaymentFailure';
import { Toaster } from "sonner";
import axios from 'axios';
import Terms from "./pages/Terms";
import Privacy from "./pages/Privacy";
import Refund from "./pages/Refund";

// Protected Route Component
const ProtectedRoute = () => {
    const { isAuthenticated, loading } = useAuth();
    
    if (loading) return <div className="flex h-screen items-center justify-center text-slate-900 dark:text-white">Chargement...</div>;
    
    return isAuthenticated ? <Outlet /> : <Navigate to="/login" />;
};

function App() {
  const RegisterGate = () => {
    const [allowed, setAllowed] = useState(null);
    useEffect(() => {
      const params = new URLSearchParams(window.location.search);
      const provider = params.get('provider');
      // Allow Verifone/HYP providers
      if (provider === 'verifone' || provider === 'hyp') {
        setAllowed(true);
      } else {
        setAllowed(false);
      }
    }, []);
    if (allowed === null) return <div className="flex h-screen items-center justify-center text-slate-900 dark:text-white">Vérification du paiement...</div>;
    return allowed ? <Register /> : <Navigate to="/pricing" />;
  };
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
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<RegisterGate />} />
            <Route path="/conditions-generales" element={<Terms />} />
            <Route path="/politique-confidentialite" element={<Privacy />} />
            <Route path="/politique-remboursement" element={<Refund />} />
            <Route path="/pricing" element={<Pricing />} />
            
            <Route path="/pricing/success" element={
              <div className='min-h-[60vh] flex items-center justify-center text-center p-12'>
                <h2 className="text-2xl font-light tracking-wide">
                  ✨ <span className="font-semibold text-white">Paiement réussi.</span> <br/>
                  <span className="text-slate-400 text-lg">Bienvenue dans l'aventure !</span>
                </h2>
              </div>
            } />
            
            <Route path="/subscription-success" element={<SubscriptionSuccess />} />
            
            {/* HYP Payment Callback Routes */}
            <Route path="/payment/success" element={<PaymentSuccess />} />
            <Route path="/payment/failure" element={<PaymentFailure />} />
            
            <Route path="/pricing/cancel" element={
              <div className='min-h-[60vh] flex items-center justify-center p-12 text-slate-400'>
                Paiement annulé. Nous restons à votre disposition.
              </div>
            } />
            
            <Route element={<ProtectedRoute />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/exam" element={<Exam />} />
              <Route path="/exam/:id" element={<ExamDetails />} />
              <Route path="/training" element={<Training />} />
              <Route path="/mistakes" element={<Mistakes />} />
              <Route path="/courses" element={<Courses />} />
              <Route path="/signs" element={<Signs />} />
              <Route path="/stats" element={<Stats />} />
              <Route path="/admin" element={<Admin />} />
            </Route>
          </Routes>
        </main>

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
