'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { CostSummaryResponse, FeatureCostItem, DailySpendItem, TokenUsageRecord } from '@/types/api';
import {
  Coins,
  TrendingUp,
  Activity,
  Calendar,
  Layers,
  Sparkles,
  Bot,
  FileText,
  Video,
  RefreshCw,
  Clock,
  Info
} from 'lucide-react';
import { cn } from '@/lib/utils';

// Mapping feature keys to stylish icons and color accents
const FEATURE_META: Record<string, { icon: any; color: string; bg: string; border: string }> = {
  career_agent: {
    icon: Bot,
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/30',
  },
  resume_parsing: {
    icon: FileText,
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
  },
  match_justifications: {
    icon: Sparkles,
    color: 'text-nexus-accent',
    bg: 'bg-nexus-accent/10',
    border: 'border-nexus-accent/30',
  },
  video_briefing: {
    icon: Video,
    color: 'text-rose-400',
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/30',
  },
  job_extraction: {
    icon: Layers,
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
  },
};

const DEFAULT_META = {
  icon: Activity,
  color: 'text-nexus-text',
  bg: 'bg-nexus-surface-2',
  border: 'border-nexus-border',
};

export default function CostDashboardPage() {
  const [currency, setCurrency] = useState<'INR' | 'USD'>('INR');
  const [days, setDays] = useState<number>(30);

  const { data, isLoading, isRefetching, refetch } = useQuery<CostSummaryResponse>({
    queryKey: ['cost-summary', days],
    queryFn: async () => {
      const res = await api.get(`/api/costs/summary?days=${days}`);
      return res.data;
    },
  });

  const formatCost = (inr: number, usd: number) => {
    if (currency === 'INR') {
      return `₹${inr.toFixed(4)}`;
    }
    return `$${usd.toFixed(6)}`;
  };

  const formatTokens = (tokens: number) => {
    if (tokens >= 1_000_000) {
      return `${(tokens / 1_000_000).toFixed(2)}M`;
    }
    if (tokens >= 1_000) {
      return `${(tokens / 1_000).toFixed(1)}k`;
    }
    return tokens.toLocaleString();
  };

  // Find max daily spend for bar scaling
  const maxDailySpend = data?.daily_trends?.reduce(
    (max, d) => Math.max(max, currency === 'INR' ? d.cost_inr : d.cost_usd),
    0
  ) || 1;

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-300 pb-12">

      {/* ── Page Header & Action Bar ────────────────────────────── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-2 border-b border-nexus-border/60">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-nexus-accent/15 border border-nexus-accent/30 flex items-center justify-center text-nexus-accent">
              <Coins className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                Cost & Token Intelligence
              </h1>
              <p className="text-sm text-nexus-text-muted">
                Real-time tracking of Gemini tokens and financial expenditure per feature.
              </p>
            </div>
          </div>
        </div>

        {/* Currency & Range Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Currency Toggle */}
          <div className="flex items-center bg-nexus-surface-2 p-1 rounded-xl border border-nexus-border">
            <button
              onClick={() => setCurrency('INR')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-semibold transition-all',
                currency === 'INR'
                  ? 'bg-nexus-accent text-white shadow-sm'
                  : 'text-nexus-text-muted hover:text-white'
              )}
            >
              ₹ INR
            </button>
            <button
              onClick={() => setCurrency('USD')}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-semibold transition-all',
                currency === 'USD'
                  ? 'bg-nexus-accent text-white shadow-sm'
                  : 'text-nexus-text-muted hover:text-white'
              )}
            >
              $ USD
            </button>
          </div>

          {/* Days selector */}
          <div className="flex items-center bg-nexus-surface-2 p-1 rounded-xl border border-nexus-border">
            {[7, 30, 90].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                  days === d
                    ? 'bg-nexus-surface-3 text-white'
                    : 'text-nexus-text-muted hover:text-white'
                )}
              >
                {d}d
              </button>
            ))}
          </div>

          {/* Refresh Button */}
          <button
            onClick={() => refetch()}
            disabled={isLoading || isRefetching}
            className="p-2.5 rounded-xl bg-nexus-surface-2 hover:bg-nexus-surface-3 text-nexus-text-muted hover:text-white border border-nexus-border transition-all disabled:opacity-50"
            title="Refresh statistics"
          >
            <RefreshCw className={cn('w-4 h-4', (isLoading || isRefetching) && 'animate-spin text-nexus-accent')} />
          </button>
        </div>
      </div>

      {/* ── Top Metrics Cards ───────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Spend */}
        <div className="nexus-card relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-nexus-accent/5 rounded-full blur-2xl group-hover:bg-nexus-accent/10 transition-all pointer-events-none" />
          <div className="flex items-center justify-between text-nexus-text-muted mb-2">
            <span className="text-xs font-medium tracking-wider uppercase">Total Spend</span>
            <Coins className="w-4 h-4 text-nexus-accent" />
          </div>
          <div className="text-2xl font-extrabold text-white">
            {formatCost(data?.total_cost_inr || 0, data?.total_cost_usd || 0)}
          </div>
          <div className="mt-2 flex items-center gap-1.5 text-xs text-nexus-text-dim">
            <span>Equivalent:</span>
            <span className="font-mono text-nexus-text-muted">
              {currency === 'INR'
                ? `$${(data?.total_cost_usd || 0).toFixed(6)} USD`
                : `₹${(data?.total_cost_inr || 0).toFixed(4)} INR`}
            </span>
          </div>
        </div>

        {/* Total Tokens */}
        <div className="nexus-card relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/5 rounded-full blur-2xl group-hover:bg-purple-500/10 transition-all pointer-events-none" />
          <div className="flex items-center justify-between text-nexus-text-muted mb-2">
            <span className="text-xs font-medium tracking-wider uppercase">Tokens Consumed</span>
            <Activity className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-extrabold text-white">
            {formatTokens(data?.total_tokens || 0)}
          </div>
          <div className="mt-2 text-xs text-nexus-text-dim">
            Across {data?.total_calls || 0} AI invocations
          </div>
        </div>

        {/* Today's Spend */}
        <div className="nexus-card relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-2xl group-hover:bg-emerald-500/10 transition-all pointer-events-none" />
          <div className="flex items-center justify-between text-nexus-text-muted mb-2">
            <span className="text-xs font-medium tracking-wider uppercase">Today's Spend</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-extrabold text-white">
            {formatCost(
              data?.today_cost_inr || 0,
              (data?.today_cost_inr || 0) / 86.5
            )}
          </div>
          <div className="mt-2 text-xs text-emerald-400/90 font-medium">
            {formatTokens(data?.today_tokens || 0)} tokens today
          </div>
        </div>

        {/* This Week's Spend */}
        <div className="nexus-card relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/5 rounded-full blur-2xl group-hover:bg-blue-500/10 transition-all pointer-events-none" />
          <div className="flex items-center justify-between text-nexus-text-muted mb-2">
            <span className="text-xs font-medium tracking-wider uppercase">This Week</span>
            <Calendar className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-extrabold text-white">
            {formatCost(
              data?.this_week_cost_inr || 0,
              (data?.this_week_cost_inr || 0) / 86.5
            )}
          </div>
          <div className="mt-2 text-xs text-blue-400/90 font-medium">
            {formatTokens(data?.this_week_tokens || 0)} tokens this week
          </div>
        </div>
      </div>

      {/* ── Feature Breakdown & Daily Trend ─────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* Feature Breakdown (7 cols) */}
        <div className="lg:col-span-7 nexus-card space-y-5">
          <div className="flex items-center justify-between border-b border-nexus-border/60 pb-3">
            <div>
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Layers className="w-4 h-4 text-nexus-accent" />
                Cost Breakdown Per Feature
              </h2>
              <p className="text-xs text-nexus-text-muted mt-0.5">
                Financial and token share across platform capabilities.
              </p>
            </div>
            <span className="text-xs text-nexus-text-dim">
              {data?.feature_breakdown?.length || 0} Features Active
            </span>
          </div>

          {(!data?.feature_breakdown || data.feature_breakdown.length === 0) ? (
            <div className="py-12 text-center text-nexus-text-dim text-sm">
              No feature usage recorded yet.
            </div>
          ) : (
            <div className="space-y-4">
              {data.feature_breakdown.map((item) => {
                const meta = FEATURE_META[item.feature] || DEFAULT_META;
                const IconComponent = meta.icon;
                return (
                  <div
                    key={item.feature}
                    className="p-3.5 rounded-xl bg-nexus-surface-2/60 border border-nexus-border/70 hover:border-nexus-border transition-all"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center border', meta.bg, meta.border, meta.color)}>
                          <IconComponent className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-sm font-medium text-white flex items-center gap-2">
                            {item.label}
                          </div>
                          <div className="text-xs text-nexus-text-dim">
                            {formatTokens(item.tokens)} tokens &bull; {item.call_count} call{item.call_count > 1 ? 's' : ''}
                          </div>
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="text-sm font-semibold text-white">
                          {formatCost(item.cost_inr, item.cost_usd)}
                        </div>
                        <div className="text-xs text-nexus-accent font-medium">
                          {item.percentage}% of spend
                        </div>
                      </div>
                    </div>

                    {/* Progress Bar */}
                    <div className="h-1.5 w-full bg-nexus-surface-3 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-nexus-accent rounded-full transition-all duration-500"
                        style={{ width: `${Math.max(item.percentage, 3)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Daily Spending Trend (5 cols) */}
        <div className="lg:col-span-5 nexus-card space-y-5">
          <div className="border-b border-nexus-border/60 pb-3">
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              14-Day Spending Trend
            </h2>
            <p className="text-xs text-nexus-text-muted mt-0.5">
              Daily token expenditure over the last two weeks.
            </p>
          </div>

          {/* Simple CSS-based bar chart */}
          <div className="pt-4">
            <div className="h-44 flex items-end justify-between gap-1.5 px-2">
              {data?.daily_trends?.map((day) => {
                const dayValue = currency === 'INR' ? day.cost_inr : day.cost_usd;
                const heightPercent = maxDailySpend > 0 ? (dayValue / maxDailySpend) * 100 : 0;
                const formattedDate = new Date(day.date).toLocaleDateString(undefined, {
                  month: 'short',
                  day: 'numeric',
                });

                return (
                  <div key={day.date} className="flex-1 flex flex-col items-center gap-1 group relative">
                    {/* Tooltip on hover */}
                    <div className="absolute -top-12 z-20 hidden group-hover:flex flex-col items-center bg-nexus-surface-3 border border-nexus-border px-2 py-1 rounded shadow-lg text-[10px] whitespace-nowrap pointer-events-none">
                      <span className="font-semibold text-white">{formatCost(day.cost_inr, day.cost_usd)}</span>
                      <span className="text-nexus-text-dim">{formatTokens(day.tokens)} tokens</span>
                    </div>

                    {/* Bar */}
                    <div className="w-full bg-nexus-surface-2 rounded-t-sm h-36 flex items-end">
                      <div
                        className={cn(
                          'w-full rounded-t-sm transition-all duration-300',
                          heightPercent > 0
                            ? 'bg-nexus-accent group-hover:bg-nexus-accent-light'
                            : 'bg-nexus-surface-3/30'
                        )}
                        style={{ height: `${Math.max(heightPercent, 4)}%` }}
                      />
                    </div>

                    {/* Date label */}
                    <span className="text-[10px] text-nexus-text-dim truncate w-full text-center">
                      {formattedDate.split(' ')[1] || formattedDate}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Pricing Model Notes */}
          <div className="p-3.5 rounded-xl bg-nexus-surface-2/70 border border-nexus-border text-xs text-nexus-text-muted space-y-1.5">
            <div className="flex items-center gap-1.5 font-medium text-white">
              <Info className="w-3.5 h-3.5 text-nexus-accent" />
              Gemini 3.5 Flash Lite Rates
            </div>
            <p className="text-nexus-text-dim">
              Input: $0.15 / 1M tokens (~₹12.98/1M) &bull; Output: $1.25 / 1M tokens (~₹108.13/1M) &bull; Embeddings: $0.025 / 1M (~₹2.16/1M)
            </p>
          </div>
        </div>
      </div>

      {/* ── Recent Token Activity Ledger ────────────────────────── */}
      <div className="nexus-card space-y-4">
        <div className="flex items-center justify-between border-b border-nexus-border/60 pb-3">
          <div>
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <Clock className="w-4 h-4 text-nexus-accent" />
              Live Activity Ledger
            </h2>
            <p className="text-xs text-nexus-text-muted mt-0.5">
              Detailed chronological record of recent LLM invocations.
            </p>
          </div>
          <span className="text-xs text-nexus-text-dim">
            Showing last {data?.recent_logs?.length || 0} calls
          </span>
        </div>

        {(!data?.recent_logs || data.recent_logs.length === 0) ? (
          <div className="py-12 text-center text-nexus-text-dim text-sm">
            No activity recorded yet. Try conversing with the AI Career Agent or uploading a resume!
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-nexus-border text-xs text-nexus-text-dim font-medium uppercase tracking-wider">
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Feature</th>
                  <th className="py-2.5 px-3">Model</th>
                  <th className="py-2.5 px-3 text-right">Input Tokens</th>
                  <th className="py-2.5 px-3 text-right">Output Tokens</th>
                  <th className="py-2.5 px-3 text-right">Total Tokens</th>
                  <th className="py-2.5 px-3 text-right">Cost ({currency})</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-nexus-border/50 text-xs">
                {data.recent_logs.map((log) => {
                  const meta = FEATURE_META[log.feature] || DEFAULT_META;
                  const Icon = meta.icon;
                  const formattedTime = new Date(log.created_at).toLocaleString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                  });

                  return (
                    <tr key={log.id} className="hover:bg-nexus-surface-2/50 transition-colors">
                      <td className="py-3 px-3 text-nexus-text-muted font-mono whitespace-nowrap">
                        {formattedTime}
                      </td>
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium border', meta.bg, meta.border, meta.color)}>
                          <Icon className="w-3 h-3" />
                          {log.label}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-nexus-text-muted font-mono whitespace-nowrap">
                        {log.model}
                      </td>
                      <td className="py-3 px-3 text-right text-nexus-text-muted font-mono">
                        {log.prompt_tokens.toLocaleString()}
                      </td>
                      <td className="py-3 px-3 text-right text-nexus-text-muted font-mono">
                        {log.completion_tokens.toLocaleString()}
                      </td>
                      <td className="py-3 px-3 text-right font-medium text-white font-mono">
                        {log.total_tokens.toLocaleString()}
                      </td>
                      <td className="py-3 px-3 text-right font-semibold text-nexus-accent font-mono whitespace-nowrap">
                        {formatCost(log.cost_inr, log.cost_usd)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
}
