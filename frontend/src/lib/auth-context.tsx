'use client';

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { AuthState, LoginRequest, RegisterRequest, TokenResponse } from '@/types/api';
import api, { clearAuth, getAuth, setAuth } from '@/lib/api';

interface AuthContextValue {
  user: AuthState | null;
  isLoading: boolean;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<TokenResponse>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthState | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = getAuth();
    if (stored) setUser(stored);
    setIsLoading(false);
  }, []);

  const login = useCallback(async (data: LoginRequest) => {
    const res = await api.post<TokenResponse>('/api/auth/login', data);
    const authState: AuthState = {
      accessToken: res.data.access_token,
      userId: res.data.user_id,
      email: res.data.email,
    };
    setAuth(authState);
    setUser(authState);
  }, []);

  const register = useCallback(async (data: RegisterRequest): Promise<TokenResponse> => {
    const res = await api.post<TokenResponse>('/api/auth/register', data);
    if (res.data.is_verified) {
      const authState: AuthState = {
        accessToken: res.data.access_token,
        userId: res.data.user_id,
        email: res.data.email,
      };
      setAuth(authState);
      setUser(authState);
    }
    return res.data;
  }, []);

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
    window.location.href = '/login';
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
