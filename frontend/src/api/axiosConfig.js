import axios from 'axios';

// Get backend URL from environment variable
// Fallback to localhost for local development
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

// Configure axios defaults
axios.defaults.baseURL = BACKEND_URL;
axios.defaults.headers.common['Content-Type'] = 'application/json';

// Log the backend URL in development
if (process.env.NODE_ENV === 'development') {
  console.log('🔗 Backend URL:', BACKEND_URL);
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

// Add response interceptor for better error handling
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - could trigger logout here
      console.warn('Unauthorized request - token may be invalid');
    }
    return Promise.reject(error);
  }
);

export default axios;
