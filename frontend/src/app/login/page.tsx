'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import api from '@/lib/api';
import { AlertCircle, Brain, Check, Eye, EyeOff, Loader2, Mail, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { AxiosError } from 'axios';

export default function LoginPage() {
  const router = useRouter();
  const { user, login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [isForgotPassword, setIsForgotPassword] = useState(false);
  const [forgotSent, setForgotSent] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Live password complexity checks
  const hasLetter = /[a-zA-Z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const hasSymbol = /[^a-zA-Z0-9\s]/.test(password);
  const isComplex = hasLetter && hasNumber && hasSymbol;

  // Auto-redirect if already authenticated
  React.useEffect(() => {
    if (user) {
      router.push('/dashboard');
    }
  }, [user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMessage(null);
    try {
      if (isForgotPassword) {
        await api.post('/api/auth/forgot-password', { email });
        setForgotSent(true);
        toast.success('Password reset email dispatched!');
      } else if (isRegister) {
        if (!isComplex) {
          setErrorMessage('Password must include letters, numbers, and at least one symbol (e.g. !@#$%^&*).');
          setLoading(false);
          return;
        }
        const res = await register({ email, password });
        if (!res.is_verified) {
          setRegisteredEmail(email);
          setPassword('');
          toast.success('Account created! Please verify your email.');
        } else {
          toast.success('Account created!');
          window.location.href = '/dashboard';
        }
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

  const handleResendVerification = async () => {
    const targetEmail = email || registeredEmail;
    if (!targetEmail) {
      toast.error('Please enter your email address.');
      return;
    }
    setResending(true);
    try {
      await api.post('/api/auth/resend-verification', { email: targetEmail });
      toast.success('Verification email sent! Check your inbox.');
    } catch {
      toast.error('Failed to resend verification email.');
    } finally {
      setResending(false);
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
          {/* Dedicated State: Registered Email Verification Screen */}
          {registeredEmail ? (
            <div className="text-center py-4 space-y-5 animate-in fade-in zoom-in-95 duration-200">
              <div className="w-16 h-16 bg-violet-500/20 text-violet-400 rounded-2xl flex items-center justify-center mx-auto shadow-inner">
                <Mail size={32} />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">Check Your Inbox</h2>
                <p className="text-sm text-nexus-text-muted mt-2 leading-relaxed">
                  We sent a confirmation link to <strong className="text-white">{registeredEmail}</strong>.
                  Please click the link in your email to activate your account before signing in.
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-nexus-surface/80 border border-nexus-border text-xs text-nexus-text-muted text-left space-y-1">
                <p>&bull; Verification links remain valid for 24 hours.</p>
                <p>&bull; Can't find the email? Please check your spam or junk folder.</p>
              </div>

              <div className="space-y-2 pt-2">
                <button
                  type="button"
                  onClick={handleResendVerification}
                  disabled={resending}
                  className="nexus-btn-ghost w-full justify-center text-xs py-2"
                >
                  {resending ? 'Resending verification email…' : 'Resend Verification Email'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setRegisteredEmail(null);
                    setIsRegister(false);
                    setErrorMessage(null);
                  }}
                  className="nexus-btn-primary w-full justify-center text-xs py-2.5"
                >
                  Return to Sign In
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Toggle (hidden when in forgot-password mode) */}
              {!isForgotPassword && (
                <div className="flex bg-nexus-surface-2 rounded-lg p-1 mb-6">
                  <button
                    type="button"
                    onClick={() => {
                      setIsRegister(false);
                      setErrorMessage(null);
                      setRegisteredEmail(null);
                    }}
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
                    onClick={() => {
                      setIsRegister(true);
                      setErrorMessage(null);
                      setRegisteredEmail(null);
                    }}
                    className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
                      isRegister
                        ? 'bg-nexus-accent text-white shadow-sm'
                        : 'text-nexus-text-muted hover:text-nexus-text'
                    }`}
                  >
                    Create Account
                  </button>
                </div>
              )}

              {/* Inline Error Banner */}
              {errorMessage && (
                <div className="flex items-start gap-3 p-3.5 mb-5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm animate-in fade-in duration-200">
                  <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400 mt-0.5" />
                  <div className="flex-1 leading-snug">
                    <p className="font-semibold">{errorMessage}</p>
                    {errorMessage.toLowerCase().includes('verify') && (
                      <div className="mt-2">
                        <p className="text-xs text-red-400/80">
                          Your account requires email verification.
                        </p>
                        <button
                          type="button"
                          onClick={handleResendVerification}
                          disabled={resending}
                          className="mt-1 text-xs font-semibold text-nexus-accent hover:underline disabled:opacity-50"
                        >
                          {resending ? 'Resending…' : 'Click here to resend verification email'}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Forgot Password View */}
              {isForgotPassword ? (
                <div className="space-y-4">
                  <div className="text-center mb-2">
                    <h2 className="text-lg font-semibold text-white">Reset Password</h2>
                    <p className="text-xs text-nexus-text-muted mt-1">
                      Enter your email address and we will send a secure reset link valid for <strong>10 minutes</strong>.
                    </p>
                  </div>

                  {forgotSent ? (
                    <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm space-y-3">
                      <p className="font-semibold text-emerald-400">Reset instructions dispatched</p>
                      <p className="text-xs text-emerald-300/80 leading-relaxed">
                        If an account exists for <strong className="text-white">{email}</strong>, a password reset email has been sent. The link expires in <strong>10 minutes</strong>.
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          setIsForgotPassword(false);
                          setForgotSent(false);
                        }}
                        className="nexus-btn-ghost w-full justify-center text-xs"
                      >
                        Back to Sign In
                      </button>
                    </div>
                  ) : (
                    <form onSubmit={handleSubmit} className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-nexus-text-muted mb-1.5">
                          Your Registered Email
                        </label>
                        <input
                          type="email"
                          value={email}
                          onChange={(e) => {
                            setEmail(e.target.value);
                            if (errorMessage) setErrorMessage(null);
                          }}
                          className="nexus-input"
                          placeholder="you@example.com"
                          required
                        />
                      </div>

                      <button
                        type="submit"
                        disabled={loading}
                        className="nexus-btn-primary w-full justify-center"
                      >
                        {loading ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Sparkles className="w-4 h-4" />
                        )}
                        Send Reset Link
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          setIsForgotPassword(false);
                          setErrorMessage(null);
                        }}
                        className="nexus-btn-ghost w-full justify-center text-xs"
                      >
                        Back to Sign In
                      </button>
                    </form>
                  )}
                </div>
              ) : (
                /* Sign In / Register Form */
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-nexus-text-muted mb-1.5">
                      Email
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => {
                        setEmail(e.target.value);
                        if (errorMessage) setErrorMessage(null);
                      }}
                      className="nexus-input"
                      placeholder="you@example.com"
                      required
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-sm font-medium text-nexus-text-muted">
                        Password
                      </label>
                      {!isRegister && (
                        <button
                          type="button"
                          onClick={() => {
                            setIsForgotPassword(true);
                            setErrorMessage(null);
                          }}
                          className="text-xs text-nexus-accent hover:underline"
                        >
                          Forgot password?
                        </button>
                      )}
                    </div>
                    <div className="relative">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => {
                          setPassword(e.target.value);
                          if (errorMessage) setErrorMessage(null);
                        }}
                        className="nexus-input pr-10"
                        placeholder={isRegister ? 'Letters, numbers & symbol' : '••••••••'}
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

                    {isRegister && (
                      <div className="p-2.5 mt-2 rounded-xl bg-nexus-surface/60 border border-nexus-border space-y-1 text-[11px]">
                        <div className="flex items-center gap-2">
                          <div className={`w-3.5 h-3.5 rounded-full flex items-center justify-center text-[9px] ${hasLetter ? 'bg-emerald-500/20 text-emerald-400' : 'bg-nexus-surface text-nexus-text-dim'}`}>
                            {hasLetter ? <Check size={9} /> : '•'}
                          </div>
                          <span className={hasLetter ? 'text-emerald-400' : 'text-nexus-text-dim'}>At least one letter</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className={`w-3.5 h-3.5 rounded-full flex items-center justify-center text-[9px] ${hasNumber ? 'bg-emerald-500/20 text-emerald-400' : 'bg-nexus-surface text-nexus-text-dim'}`}>
                            {hasNumber ? <Check size={9} /> : '•'}
                          </div>
                          <span className={hasNumber ? 'text-emerald-400' : 'text-nexus-text-dim'}>At least one number</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className={`w-3.5 h-3.5 rounded-full flex items-center justify-center text-[9px] ${hasSymbol ? 'bg-emerald-500/20 text-emerald-400' : 'bg-nexus-surface text-nexus-text-dim'}`}>
                            {hasSymbol ? <Check size={9} /> : '•'}
                          </div>
                          <span className={hasSymbol ? 'text-emerald-400' : 'text-nexus-text-dim'}>At least one symbol (e.g. !@#$%^&*)</span>
                        </div>
                      </div>
                    )}
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
              )}
            </>
          )}
        </div>

        <p className="text-center text-nexus-text-dim text-xs mt-6">
          Powered by Gemini AI &bull; pgvector Semantic Search
        </p>
      </div>
    </div>
  );
}
