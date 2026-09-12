import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import type { AuthState } from '@/types/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 120_000,
});

// ---------------------------------------------------------------------------
// Auth token management (localStorage)
// ---------------------------------------------------------------------------
const AUTH_KEY = 'nexus_auth';

export function getAuth(): AuthState | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthState;
  } catch {
    return null;
  }
}

export function setAuth(state: AuthState): void {
  localStorage.setItem(AUTH_KEY, JSON.stringify(state));
}

export function clearAuth(): void {
  localStorage.removeItem(AUTH_KEY);
}

// ---------------------------------------------------------------------------
// Request interceptor — inject JWT Bearer token
// ---------------------------------------------------------------------------
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const auth = getAuth();
  if (auth?.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`;
  }
  return config;
});

// ---------------------------------------------------------------------------
// Response interceptor — redirect on 401
// ---------------------------------------------------------------------------
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      clearAuth();
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

export default api;
