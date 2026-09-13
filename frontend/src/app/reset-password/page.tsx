'use client';

import React, { Suspense, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import api from '@/lib/api';
import { AxiosError } from 'axios';
import { Brain, Check, CheckCircle2, Eye, EyeOff, Loader2, Lock, Sparkles, XCircle } from 'lucide-react';
import toast from 'react-hot-toast';

function parseErrorDetail(err: unknown, defaultMsg: string): string {
  const axiosErr = err as AxiosError<{ detail?: unknown }>;
  const detail = axiosErr.response?.data?.detail;
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d: any) => {
        if (typeof d === 'string') return d;
        if (d && typeof d.msg === 'string') {
          return d.msg.replace(/^Value error,\s*/i, '');
        }
        return 'Validation error';
      })
      .join('; ');
  }
  return defaultMsg;
}

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const hasLetter = /[a-zA-Z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const hasSymbol = /[^a-zA-Z0-9\s]/.test(password);
  const isComplexEnough = hasLetter && hasNumber && hasSymbol;

  if (!token) {
    return (
      <div className="nexus-card text-center py-8 px-6 space-y-5">
        <div className="w-14 h-14 bg-red-500/20 text-red-400 rounded-2xl flex items-center justify-center mx-auto">
          <XCircle size={32} />
        </div>
        <div>
          <h2 className="text-xl font-bold text-white">Missing Reset Link</h2>
          <p className="text-sm text-nexus-text-muted mt-2">
            No valid reset token was found in this request. Password reset tokens are time-limited (10 minutes) and single-use.
          </p>
        </div>
        <Link href="/login" className="nexus-btn-primary inline-flex justify-center text-xs px-5 py-2">
          Return to Sign In
        </Link>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match.');
      return;
    }

    if (!isComplexEnough) {
      setErrorMessage('Password must include letters, numbers, and at least one symbol (e.g. !@#$%^&*).');
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      await api.post('/api/auth/reset-password', {
        token,
        new_password: password,
      });
      setSuccess(true);
      toast.success('Password reset successfully!');
      setTimeout(() => {
        router.push('/login');
      }, 2500);
    } catch (err) {
      const msg = parseErrorDetail(err, 'Password reset failed. The link may have expired or already been used.');
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="nexus-card py-7 px-6 space-y-6">
      {success ? (
        <div className="text-center space-y-5 animate-in fade-in zoom-in-95 duration-200">
          <div className="w-16 h-16 bg-emerald-500/20 text-emerald-400 rounded-2xl flex items-center justify-center mx-auto">
            <CheckCircle2 size={36} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Password Reset Complete!</h2>
            <p className="text-sm text-nexus-text-muted mt-2">
              Your password has been updated securely. Redirecting you to the sign in page…
            </p>
          </div>
          <Link
            href="/login"
            className="nexus-btn-primary inline-flex justify-center text-xs px-6 py-2.5 mx-auto"
          >
            Sign In Now
          </Link>
        </div>
      ) : (
        <>
          <div className="text-center space-y-1">
            <div className="w-12 h-12 bg-nexus-accent/20 text-nexus-accent rounded-xl flex items-center justify-center mx-auto mb-3">
              <Lock size={22} />
            </div>
            <h2 className="text-xl font-bold text-white">Create New Password</h2>
            <p className="text-xs text-nexus-text-muted">
              Choose a strong password. This reset token expires in <strong>10 minutes</strong>.
            </p>
          </div>

          {errorMessage && (
            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
              {errorMessage}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-nexus-text-muted mb-1.5">
                New Password
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
                  placeholder="Letters, numbers & symbol"
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

            <div>
              <label className="block text-xs font-medium text-nexus-text-muted mb-1.5">
                Confirm New Password
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
                  placeholder="Repeat your new password"
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

            {/* Password requirements indicators */}
            <div className="p-3 rounded-xl bg-nexus-surface/60 border border-nexus-border space-y-1.5 text-[11px]">
              <div className="text-nexus-text-muted font-medium mb-1">Password Requirements:</div>
              <div className="flex items-center gap-2">
                <div className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${hasLetter ? 'bg-emerald-500/20 text-emerald-400' : 'bg-nexus-surface text-nexus-text-dim'}`}>
                  {hasLetter ? <Check size={10} /> : '•'}
                </div>
                <span className={hasLetter ? 'text-emerald-400' : 'text-nexus-text-dim'}>At least one letter</span>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${hasNumber ? 'bg-emerald-500/20 text-emerald-400' : 'bg-nexus-surface text-nexus-text-dim'}`}>
                  {hasNumber ? <Check size={10} /> : '•'}
                </div>
                <span className={hasNumber ? 'text-emerald-400' : 'text-nexus-text-dim'}>At least one number</span>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${hasSymbol ? 'bg-emerald-500/20 text-emerald-400' : 'bg-nexus-surface text-nexus-text-dim'}`}>
                  {hasSymbol ? <Check size={10} /> : '•'}
                </div>
                <span className={hasSymbol ? 'text-emerald-400' : 'text-nexus-text-dim'}>At least one symbol (e.g. !@#$%^&*)</span>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="nexus-btn-primary w-full justify-center text-sm py-2.5"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              Update Password
            </button>

            <div className="text-center pt-2">
              <Link href="/login" className="text-xs text-nexus-text-muted hover:text-white transition-colors">
                &larr; Back to Sign In
              </Link>
            </div>
          </form>
        </>
      )}
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-nexus-bg relative overflow-hidden px-4">
      {/* Background decorations */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-nexus-accent/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-nexus-accent/20 rounded-2xl mb-4">
            <Brain className="w-8 h-8 text-nexus-accent" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">NEXUS</h1>
          <p className="text-nexus-text-muted mt-1">Autonomous Career Intelligence</p>
        </div>

        <Suspense
          fallback={
            <div className="nexus-card text-center py-12">
              <Loader2 className="w-8 h-8 text-nexus-accent animate-spin mx-auto mb-3" />
              <p className="text-sm text-nexus-text-muted">Loading reset form...</p>
            </div>
          }
        >
          <ResetPasswordContent />
        </Suspense>
      </div>
    </div>
  );
}
