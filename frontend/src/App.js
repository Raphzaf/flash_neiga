import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
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
import { Toaster } from "sonner";
import axios from 'axios';

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
      const sessionId = params.get('session_id');
      if (!sessionId) {
        setAllowed(false);
        return;
      }
      (async () => {
        try {
          const res = await axios.get(`/api/payments/validate-session`, { params: { session_id: sessionId } });
          setAllowed(Boolean(res.data?.valid));
        } catch {
          setAllowed(false);
        }
      })();
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
                {/* Registration gated: requires valid Stripe session_id */}
                <Route path="/register" element={<RegisterGate />} />
              {/* Public pricing routes so users can view plans before login */}
              <Route path="/pricing" element={<Pricing />} />
              <Route path="/pricing/success" element={<div className='p-6'>Paiement réussi. Merci ! Vous pouvez gérer votre abonnement ci-dessous.</div>} />
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
        </BrowserRouter>
        <Toaster position="top-center" />
      </div>
    </AuthProvider>
  );
}

export default App;
