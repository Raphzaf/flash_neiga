import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Exam from "./pages/Exam";
import Training from "./pages/Training";
import Signs from "./pages/Signs";
import Stats from "./pages/Stats";
import Admin from "./pages/Admin";
import { Toaster } from "sonner";

// Protected Route Component
const ProtectedRoute = () => {
    const { isAuthenticated, loading } = useAuth();
    
    if (loading) return <div className="flex h-screen items-center justify-center">Chargement...</div>;
    
    return isAuthenticated ? <Outlet /> : <Navigate to="/login" />;
};

function App() {
  return (
    <AuthProvider>
      <div className="min-h-screen bg-background text-foreground antialiased">
        <BrowserRouter>
            <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                
                <Route element={<ProtectedRoute />}>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/exam" element={<Exam />} />
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
