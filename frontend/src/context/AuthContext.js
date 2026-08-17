import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';
import axios from 'axios';
import { rememberEmail } from '../lib/funnel';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [token, setToken] = useState(null);
    const [initialized, setInitialized] = useState(false);
    // État d'abonnement tel que le serveur le voit : c'est lui qui décide si
    // l'élève entre dans l'application ou passe par le choix d'une formule.
    const [subscription, setSubscription] = useState(null);
    const [subscriptionLoading, setSubscriptionLoading] = useState(false);
    // Vrai quand la session a été invalidée en cours de route (jeton expiré).
    const [sessionExpired, setSessionExpired] = useState(false);

    const loadSubscription = useCallback(async () => {
        setSubscriptionLoading(true);
        try {
            const { data } = await axios.get('/api/subscriptions/me');
            setSubscription(data);
            return data;
        } catch (error) {
            console.warn('Statut d\'abonnement indisponible:', error?.response?.status);
            // On répond quand même quelque chose : sans cela, les écrans qui
            // attendent de connaître l'abonnement resteraient bloqués sur un
            // chargement infini en cas de coupure réseau.
            const unknown = { has_access: false, active: false, subscription: null, unavailable: true };
            setSubscription(unknown);
            return unknown;
        } finally {
            setSubscriptionLoading(false);
        }
    }, []);

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
                    rememberEmail(res.data?.email);
                    await loadSubscription();
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
    }, [loadSubscription]); // 🔒 Ne s'exécute qu'une fois : loadSubscription est stable

    // Ouvre la session à partir d'un token déjà obtenu (connexion classique,
    // inscription, ou rattachement d'un paiement à un compte).
    const loginWithToken = async (newToken) => {
        setSessionExpired(false);
        localStorage.setItem('token', newToken);
        axios.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
        setToken(newToken);

        // Charger l'utilisateur immédiatement
        try {
            const userRes = await axios.get('/api/auth/me');
            setUser(userRes.data);
            rememberEmail(userRes.data?.email);
        } catch (error) {
            console.error("Failed to load user after login:", error);
            throw error;
        }

        await loadSubscription();
        return true;
    };

    const login = async (email, password) => {
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);

        const res = await axios.post('/api/auth/login', formData);
        return await loginWithToken(res.data.access_token);
    };

    const register = async (email, password, firstName, lastName, phone) => {
        // L'inscription renvoie déjà un token : inutile de rejouer une connexion.
        const res = await axios.post('/api/auth/register', {
            email,
            password,
            first_name: firstName,
            last_name: lastName,
            phone,
        });
        return await loginWithToken(res.data.access_token);
    };

    // `expired` distingue une déconnexion volontaire d'une session devenue
    // invalide : les gardes de routes s'en servent pour expliquer à l'élève
    // pourquoi on lui redemande ses identifiants.
    const logout = ({ expired = false } = {}) => {
        localStorage.removeItem('token');
        delete axios.defaults.headers.common['Authorization'];
        setToken(null);
        setUser(null);
        setSubscription(null);
        setSessionExpired(expired);
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
            token,
            initialized,
            subscription,
            subscriptionLoading,
            // `has_access` inclut les administrateurs, non soumis au paywall.
            hasAccess: !!subscription?.has_access,
            sessionExpired,
            refreshSubscription: loadSubscription,
        }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
