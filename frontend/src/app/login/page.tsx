'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Script from 'next/script';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { AlertCircle, Brain, Eye, EyeOff, Loader2, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { AxiosError } from 'axios';

export default function LoginPage() {
  const router = useRouter();
  const { user, login, register, loginWithGoogle } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [googleInitialized, setGoogleInitialized] = useState(false);

  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';

  // Auto-redirect if already authenticated
  useEffect(() => {
    if (user) {
      router.push('/dashboard');
    }
  }, [user, router]);

  // Handle response from Google OAuth popup
  const handleGoogleCredentialResponse = useCallback(
    async (response: { credential?: string }) => {
      if (!response.credential) return;
      setLoading(true);
      setErrorMessage(null);
      try {
        await loginWithGoogle(response.credential);
        toast.success('Welcome to NEXUS!');
        window.location.href = '/dashboard';
      } catch (err) {
        const axiosErr = err as AxiosError<{ detail?: string }>;
        const msg = axiosErr.response?.data?.detail || 'Google sign-in failed. Please try again.';
        setErrorMessage(msg);
        toast.error(msg);
      } finally {
        setLoading(false);
      }
    },
    [loginWithGoogle]
  );

  // Initialize Google Identity Services button
  const initializeGoogleBtn = useCallback(() => {
    if (!googleClientId) return;
    if (typeof window === 'undefined' || !window.google?.accounts?.id) return;

    try {
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: handleGoogleCredentialResponse,
      });

      const container = document.getElementById('google-btn-container');
      if (container) {
        container.innerHTML = '';
        window.google.accounts.id.renderButton(container, {
          theme: 'filled_black',
          size: 'large',
          text: 'continue_with',
          shape: 'pill',
          width: 360,
          logo_alignment: 'left',
        });
        setGoogleInitialized(true);
      }
    } catch (err) {
      console.error('Failed to initialize Google Sign-In:', err);
    }
  }, [googleClientId, handleGoogleCredentialResponse]);

  // Attempt button rendering when window is available or script has loaded
  useEffect(() => {
    if (googleClientId && window.google?.accounts?.id) {
      initializeGoogleBtn();
    }
  }, [googleClientId, initializeGoogleBtn]);

  // Email & Password Fallback submit handler
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMessage(null);

    try {
      if (isRegister) {
        if (password !== confirmPassword) {
          setErrorMessage('Passwords do not match.');
          setLoading(false);
          return;
        }
        await register({ email, password });
        toast.success('Account created! Welcome to NEXUS.');
        window.location.href = '/dashboard';
      } else {
        await login({ email, password });
        toast.success('Welcome back!');
        window.location.href = '/dashboard';
      }
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail?: unknown }>;
      let msg = 'Authentication failed';
      const detail = axiosErr.response?.data?.detail;
      if (typeof detail === 'string') {
        msg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        msg = detail
          .map((d: any) => {
            if (typeof d === 'string') return d;
            if (d && typeof d.msg === 'string') {
              return d.msg.replace(/^Value error,\s*/i, '');
            }
            return 'Validation error';
          })
          .join('; ');
      }
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-nexus-bg relative overflow-hidden">
      {/* Load Google Identity Services SDK */}
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onLoad={initializeGoogleBtn}
      />

      {/* Ambient background decorations */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-nexus-accent/15 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-500/15 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-nexus-accent/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-md px-6 py-12">
        {/* Logo & Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-nexus-accent/20 rounded-2xl mb-4 shadow-lg shadow-nexus-accent/10">
            <Brain className="w-8 h-8 text-nexus-accent" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">NEXUS</h1>
          <p className="text-nexus-text-muted mt-1 text-sm">Autonomous Career Intelligence</p>
        </div>

        {/* Card */}
        <div className="nexus-card shadow-2xl backdrop-blur-md">
          {/* Error Banner */}
          {errorMessage && (
            <div className="flex items-start gap-3 p-3.5 mb-5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm animate-in fade-in duration-200">
              <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400 mt-0.5" />
              <p className="flex-1 leading-snug">{errorMessage}</p>
            </div>
          )}

          {/* PRIMARY: Google Sign-In */}
          <div className="space-y-3">
            <label className="block text-xs font-semibold uppercase tracking-wider text-nexus-text-muted text-center">
              Quick Sign In
            </label>

            <div className="flex flex-col items-center justify-center min-h-[46px]">
              {/* Google Button Container (Populated by Google's GSI) */}
              <div id="google-btn-container" className="flex justify-center w-full" />

              {/* Fallback button if Client ID isn't set yet */}
              {!googleClientId && (
                <div className="w-full text-center p-3 rounded-xl bg-nexus-surface-2/60 border border-nexus-border text-xs text-nexus-text-dim">
                  Add <code className="text-nexus-accent font-mono">NEXT_PUBLIC_GOOGLE_CLIENT_ID</code> in <code className="font-mono">.env.local</code> to enable 1-click Google Sign-In.
                </div>
              )}
            </div>
          </div>

          {/* Divider */}
          <div className="relative my-6 text-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-nexus-border/60" />
            </div>
            <span className="relative bg-nexus-surface px-3 text-[11px] text-nexus-text-dim uppercase tracking-wider font-semibold">
              Or with email
            </span>
          </div>

          {/* Toggle: Sign In vs Create Account */}
          <div className="flex bg-nexus-surface-2 rounded-lg p-1 mb-5">
            <button
              type="button"
              onClick={() => {
                setIsRegister(false);
                setErrorMessage(null);
              }}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-all ${
                !isRegister
                  ? 'bg-nexus-accent text-white shadow-sm'
                  : 'text-nexus-text-muted hover:text-nexus-text'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setIsRegister(true);
                setErrorMessage(null);
              }}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-all ${
                isRegister
                  ? 'bg-nexus-accent text-white shadow-sm'
                  : 'text-nexus-text-muted hover:text-nexus-text'
              }`}
            >
              Create Account
            </button>
          </div>

          {/* Fallback Email & Password Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-nexus-text-muted mb-1.5">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (errorMessage) setErrorMessage(null);
                }}
                className="nexus-input text-sm"
                placeholder="you@example.com"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-nexus-text-muted mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (errorMessage) setErrorMessage(null);
                  }}
                  className="nexus-input pr-10 text-sm"
                  placeholder="••••••••"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-nexus-text-dim hover:text-nexus-text"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {isRegister && (
              <div>
                <label className="block text-xs font-medium text-nexus-text-muted mb-1.5">
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => {
                      setConfirmPassword(e.target.value);
                      if (errorMessage) setErrorMessage(null);
                    }}
                    className="nexus-input pr-10 text-sm"
                    placeholder="••••••••"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-nexus-text-dim hover:text-nexus-text"
                  >
                    {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="nexus-btn-primary w-full justify-center text-sm py-2.5 mt-2"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              {isRegister ? 'Register & Sign In' : 'Sign In with Email'}
            </button>
          </form>
        </div>

        <p className="text-center text-nexus-text-dim text-xs mt-6">
          NEXUS Career Intelligence &bull; Powered by Gemini AI
        </p>
      </div>
    </div>
  );
}
