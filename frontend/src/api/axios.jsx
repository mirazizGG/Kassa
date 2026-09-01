import axios from "axios";

// VITE_API_URL bo'sh ("") bo'lsa — nisbiy so'rovlar (backend frontendni o'zi beradi).
// Umuman berilmagan bo'lsa — lokal ishlab chiqish uchun localhost:8000.
export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

console.log(`[API Config] Connecting to: ${API_URL}`);

const api = axios.create({
  baseURL: API_URL,
  timeout: 60000, // Increase timeout to 60s to handle Render cold starts
});

// Add a request interceptor to include the auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// Add a response interceptor to handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear stored auth data
      localStorage.removeItem("token");
      localStorage.removeItem("role");
      localStorage.removeItem("username");
      // Redirect to login page
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

export default api;
