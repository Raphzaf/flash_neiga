import axios from 'axios';

// Determine backend URL based on environment
const getBackendURL = () => {
  // In production (Netlify), use relative paths (proxy handles it)
  if (process.env.NODE_ENV === 'production') {
    return ''; // Empty string = relative paths, proxy handles routing
  }
  
  // In development, use env var or localhost
  return process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
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
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default axios;
