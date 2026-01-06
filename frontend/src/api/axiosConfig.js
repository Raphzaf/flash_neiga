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
    if (error.response?.status === 401) {
      console.warn('🚫 Unauthorized (401) - Clearing token');
      localStorage.removeItem('token');
      delete axios.defaults.headers.common['Authorization'];
      
      // Secure redirection
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default axios;
// ✅ PAS de useEffect ici !
