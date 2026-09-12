'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { Brain, Eye, EyeOff, Loader2, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { AxiosError } from 'axios';

export default function LoginPage() {
  const router = useRouter();
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (isRegister) {
        await register({ email, password });
        toast.success('Account created! Welcome to NEXUS.');
      } else {
        await login({ email, password });
        toast.success('Welcome back!');
      }
      router.push('/dashboard');
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail: string }>;
      const msg = axiosErr.response?.data?.detail || 'Authentication failed';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-nexus-bg relative overflow-hidden">
      {/* Background decorations */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-nexus-accent/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-nexus-accent/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-md px-6">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-nexus-accent/20 rounded-2xl mb-4">
            <Brain className="w-8 h-8 text-nexus-accent" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">NEXUS</h1>
          <p className="text-nexus-text-muted mt-1">Autonomous Career Intelligence</p>
        </div>

        {/* Card */}
        <div className="nexus-card">
          {/* Toggle */}
          <div className="flex bg-nexus-surface-2 rounded-lg p-1 mb-6">
            <button
              type="button"
              onClick={() => setIsRegister(false)}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
                !isRegister
                  ? 'bg-nexus-accent text-white shadow-sm'
                  : 'text-nexus-text-muted hover:text-nexus-text'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => setIsRegister(true)}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
                isRegister
                  ? 'bg-nexus-accent text-white shadow-sm'
                  : 'text-nexus-text-muted hover:text-nexus-text'
              }`}
            >
              Create Account
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-nexus-text-muted mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="nexus-input"
                placeholder="you@example.com"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-nexus-text-muted mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="nexus-input pr-10"
                  placeholder={isRegister ? 'Min 8 characters' : '••••••••'}
                  minLength={isRegister ? 8 : undefined}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-nexus-text-dim hover:text-nexus-text"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <button type="submit" disabled={loading} className="nexus-btn-primary w-full justify-center">
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              {isRegister ? 'Create Account' : 'Sign In'}
            </button>
          </form>
        </div>

        <p className="text-center text-nexus-text-dim text-xs mt-6">
          Powered by Gemini AI &bull; pgvector Semantic Search
        </p>
      </div>
    </div>
  );
}
