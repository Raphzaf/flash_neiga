import axios from 'axios';

// Determine backend URL based on environment, with robust fallbacks
const getBackendURL = () => {
  const envUrl = process.env.REACT_APP_BACKEND_URL?.trim();
  const isBrowser = typeof window !== 'undefined';
  const isLocalHost = isBrowser && /^(localhost|127\.0\.0\.1)$/i.test(window.location.hostname);
  const isEnvLocalhost = envUrl && /(^http:\/\/localhost|^http:\/\/127\.0\.0\.1)/i.test(envUrl);

  if (envUrl) {
    if (!isLocalHost && isEnvLocalhost) {
      return '';
    }
    return envUrl.replace(/\/$/, '');
  }

  if (process.env.NODE_ENV === 'production') {
    return isLocalHost ? 'http://localhost:8000' : '';
  }

  return 'http://localhost:8000';
};

const BACKEND_URL = getBackendURL();

// Configure axios defaults
axios.defaults.baseURL = BACKEND_URL;
axios.defaults.withCredentials = true;

// Log configuration in development
if (process.env.NODE_ENV === 'development') {
  console.log('🔗 Backend URL:', BACKEND_URL || 'Using relative paths (proxy)');
}

// Add request interceptor to automatically include Authorization token
axios.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
      if (process.env.NODE_ENV === 'development') {
        console.log('📤 Request with token:', token.substring(0, 10) + '...');
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Better error handling
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    // 402 = abonnement requis : on renvoie l'élève au choix d'une formule.
    // Distinct du 401 (session expirée) : le compte reste valide, seul l'accès
    // au contenu est fermé. Filet de sécurité — en temps normal la garde de
    // route a déjà redirigé sans passer par un appel refusé.
    if (error.response?.status === 402) {
      if (window.location.pathname !== '/subscribe') {
        window.location.href = '/subscribe';
      }
      return Promise.reject(error);
    }

    // Ces appels traitent eux-mêmes leur 401 (échec de connexion, paiement
    // lancé sans compte) : les rediriger vers /login ferait perdre à l'élève sa
    // saisie ou la formule qu'il venait de choisir.
    const url = error.config?.url || '';
    const handledLocally = /\/api\/auth\/(login|register)|\/api\/payments\//.test(url);

    if (error.response?.status === 401 && !handledLocally) {
      console.warn('🚫 Unauthorized (401) - Clearing token');
      localStorage.removeItem('token');
      delete axios.defaults.headers.common['Authorization'];

      // Retour à la connexion, en expliquant pourquoi.
      if (window.location.pathname !== '/login') {
        window.location.href = '/login?reason=session';
      }
    }
    return Promise.reject(error);
  }
);

export default axios;
// ✅ PAS de useEffect ici !
