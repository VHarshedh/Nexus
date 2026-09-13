'use client';

import React, { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import api from '@/lib/api';
import { AxiosError } from 'axios';
import { CheckCircle2, XCircle, Loader2, Brain, Sparkles, ArrowRight } from 'lucide-react';
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

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [loading, setLoading] = useState(true);
  const [success, setSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [resendEmail, setResendEmail] = useState('');
  const [resending, setResending] = useState(false);
  const [resendSent, setResendSent] = useState(false);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setErrorMsg('No verification token was provided in the link.');
      return;
    }

    let isMounted = true;
    async function verify() {
      try {
        await api.post('/api/auth/verify-email', { token });
        if (isMounted) {
          setSuccess(true);
          toast.success('Email verified successfully!');
        }
      } catch (err) {
        if (isMounted) {
          const msg = parseErrorDetail(err, 'Verification failed or link has expired.');
          setErrorMsg(msg);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    verify();
    return () => {
      isMounted = false;
    };
  }, [token]);

  const handleResend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resendEmail) return;
    setResending(true);
    try {
      await api.post('/api/auth/resend-verification', { email: resendEmail });
      setResendSent(true);
      toast.success('New verification link dispatched!');
    } catch {
      toast.error('Failed to resend verification link.');
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="nexus-card text-center py-8 px-6 space-y-6">
      {loading && (
        <div className="py-8 space-y-4">
          <Loader2 className="w-12 h-12 text-nexus-accent animate-spin mx-auto" />
          <h2 className="text-lg font-semibold text-white">Verifying your email…</h2>
          <p className="text-sm text-nexus-text-muted">
            Connecting to NEXUS authentication servers.
          </p>
        </div>
      )}

      {!loading && success && (
        <div className="space-y-5 animate-in fade-in zoom-in-95 duration-200">
          <div className="w-16 h-16 bg-emerald-500/20 text-emerald-400 rounded-2xl flex items-center justify-center mx-auto">
            <CheckCircle2 size={36} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Email Address Verified!</h2>
            <p className="text-sm text-nexus-text-muted mt-2 max-w-sm mx-auto">
              Your NEXUS account is now fully active. You can sign in and begin exploring semantic job matches and generating video briefings.
            </p>
          </div>
          <Link
            href="/login"
            className="nexus-btn-primary inline-flex items-center gap-2 justify-center px-6 py-2.5 mx-auto text-sm font-medium"
          >
            Continue to Sign In <ArrowRight size={16} />
          </Link>
        </div>
      )}

      {!loading && !success && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="w-16 h-16 bg-red-500/20 text-red-400 rounded-2xl flex items-center justify-center mx-auto">
            <XCircle size={36} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Verification Failed</h2>
            <p className="text-sm text-red-400 mt-2 max-w-sm mx-auto">
              {errorMsg}
            </p>
          </div>

          {resendSent ? (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm">
              <p className="font-medium text-emerald-400">New link dispatched</p>
              <p className="text-xs text-emerald-300/80 mt-1">
                Please check your inbox at <strong className="text-white">{resendEmail}</strong>.
              </p>
            </div>
          ) : (
            <div className="border-t border-nexus-border pt-5 text-left space-y-3">
              <p className="text-xs font-semibold text-nexus-text-muted uppercase tracking-wider text-center">
                Need a new verification link?
              </p>
              <form onSubmit={handleResend} className="space-y-3">
                <input
                  type="email"
                  value={resendEmail}
                  onChange={(e) => setResendEmail(e.target.value)}
                  placeholder="Enter your registered email"
                  className="nexus-input text-sm"
                  required
                />
                <button
                  type="submit"
                  disabled={resending}
                  className="nexus-btn-primary w-full justify-center text-xs"
                >
                  {resending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  Resend Verification Email
                </button>
              </form>
            </div>
          )}

          <div className="pt-2">
            <Link href="/login" className="text-xs text-nexus-text-muted hover:text-white transition-colors">
              &larr; Back to Sign In
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
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
              <p className="text-sm text-nexus-text-muted">Loading verification...</p>
            </div>
          }
        >
          <VerifyEmailContent />
        </Suspense>
      </div>
    </div>
  );
}
