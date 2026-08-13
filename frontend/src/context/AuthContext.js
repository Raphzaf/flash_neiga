import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [token, setToken] = useState(null);
    const [initialized, setInitialized] = useState(false);

    // 🎯 Initialisation au montage UNIQUEMENT
    useEffect(() => {
        const initAuth = async () => {
            const storedToken = localStorage.getItem('token');
            
            if (storedToken) {
                setToken(storedToken);
                try {
                    // Force le token dans les headers avant la requête
                    axios.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;
                    const res = await axios.get('/api/auth/me');
                    setUser(res.data);
                } catch (error) {
                    console.error("❌ Failed to load user:", error.response?.status);
                    // Token invalide, nettoyer
                    localStorage.removeItem('token');
                    setToken(null);
                    delete axios.defaults.headers.common['Authorization'];
                }
            }
            
            setLoading(false);
            setInitialized(true);
        };

        initAuth();
    }, []); // 🔒 Dependency array vide = exécution unique !

    // Ouvre la session à partir d'un token déjà obtenu (connexion classique,
    // inscription, ou rattachement d'un paiement à un compte).
    const loginWithToken = async (newToken) => {
        localStorage.setItem('token', newToken);
        axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
        setToken(newToken);

        // Charger l'utilisateur immédiatement
        try {
            const userRes = await axios.get('/api/auth/me');
            setUser(userRes.data);
        } catch (error) {
            console.error("Failed to load user after login:", error);
            throw error;
        }

        return true;
    };

    const login = async (email, password) => {
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);

        const res = await axios.post('/api/auth/login', formData);
        return await loginWithToken(res.data.access_token);
    };

    const register = async (email, password, firstName, lastName) => {
        // L'inscription renvoie déjà un token : inutile de rejouer une connexion.
        const res = await axios.post('/api/auth/register', {
            email,
            password,
            first_name: firstName,
            last_name: lastName,
        });
        return await loginWithToken(res.data.access_token);
    };

    const logout = () => {
        localStorage.removeItem('token');
        delete axios.defaults.headers.common['Authorization'];
        setToken(null);
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{
            user,
            login,
            loginWithToken,
            register,
            logout,
            loading, 
            isAuthenticated: !!user,
            token
        }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
