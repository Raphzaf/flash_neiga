import axios from 'axios';

// Determine backend URL based on environment, with robust fallbacks
const getBackendURL = () => {
  const envUrl = process.env.REACT_APP_BACKEND_URL?.trim();
  const isBrowser = typeof window !== 'undefined';
  const isLocalHost = isBrowser && /^(localhost|127\.0\.0\.1)$/i.test(window.location.hostname);
  const isEnvLocalhost = envUrl && /(^http:\/\/localhost|^http:\/\/127\.0\.0\.1)/i.test(envUrl);

  // If explicitly set, honor it unless it's pointing to localhost while hosted remotely
  if (envUrl) {
    if (!isLocalHost && isEnvLocalhost) {
      // Ignore a baked-in localhost URL on a remote host like Netlify
      // and prefer proxy/relative path to avoid CORS issues.
      return '';
    }
    return envUrl.replace(/\/$/, '');
  }

  // Production: default to relative paths (Netlify proxy). If running locally
  // (serving build/ via a simple static server), fall back to localhost:8000.
  if (process.env.NODE_ENV === 'production') {
    return isLocalHost ? 'http://localhost:8000' : '';
  }

  // Development: point directly to local backend
  return 'http://localhost:8000';
};

const BACKEND_URL = getBackendURL();

// Configure axios defaults
axios.defaults.baseURL = BACKEND_URL;
axios.defaults.withCredentials = true; // Important for cookies/auth

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
      localStorage.removeItem('token');
      // Force full page reload to /login to clear all app state
      // This is intentional for security - ensures clean logout on auth failure
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default axios;
