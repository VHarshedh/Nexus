'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import {
  Brain,
  Sparkles,
  Search,
  ExternalLink,
  ShieldCheck,
  Cpu,
  TrendingUp,
  Briefcase,
  MapPin,
  ArrowRight,
  Database,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';

interface StatsResponse {
  status: string;
  timestamp: string;
  counts: {
    total_listings: number;
    vectorized_listings: number;
    vector_percentage: number;
    total_users: number;
    total_resumes: number;
    total_matches: number;
    total_briefings: number;
  };
  sources: Record<string, number>;
  recent_listings: Array<{
    id: string;
    title: string;
    company: string;
    location: string;
    remote_ok: boolean;
    stipend: string;
    skills: string[];
    source_name: string;
    source_url: string;
    scraped_at: string | null;
    has_embedding: boolean;
  }>;
}

export default function HomePage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSource, setSelectedSource] = useState<string>('all');
  const [onlyWithStipend, setOnlyWithStipend] = useState(false);

  const { data: stats, isLoading, isError, refetch } = useQuery<StatsResponse>({
    queryKey: ['system-stats'],
    queryFn: async () => {
      const res = await api.get<StatsResponse>('/api/stats');
      return res.data;
    },
    refetchInterval: 15_000,
  });

  const sourceLabels: Record<string, string> = {
    all: 'All Sources',
    levels_fyi: 'Levels.fyi 💰',
    remoteok: 'RemoteOK',
    remotive: 'Remotive',
    weworkremotely: 'We Work Remotely',
    arbeitnow: 'Arbeitnow',
    github: 'HN Hiring',
    hn_who_is_hiring: 'HN Hiring',
    adzuna: 'Adzuna',
  };

  const filteredListings = (stats?.recent_listings || []).filter((item) => {
    const sName = (item.source_name || '').toLowerCase();
    const matchesSource =
      selectedSource === 'all' ||
      sName.includes(selectedSource.toLowerCase()) ||
      (selectedSource === 'github' && (sName.includes('hiring') || sName.includes('github') || sName.includes('hn')));
    const query = searchQuery.toLowerCase();
    const matchesQuery =
      !query ||
      item.title.toLowerCase().includes(query) ||
      item.company.toLowerCase().includes(query) ||
      item.skills.some((s) => s.toLowerCase().includes(query));
    const matchesStipend =
      !onlyWithStipend ||
      (!!item.stipend &&
        item.stipend.toLowerCase() !== 'not specified' &&
        item.stipend.trim() !== '');
    return matchesSource && matchesQuery && matchesStipend;
  });

  return (
    <div className="min-h-screen bg-nexus-bg text-nexus-text">
      {/* Top Navigation */}
      <nav className="sticky top-0 z-50 backdrop-blur-md bg-nexus-bg/80 border-b border-nexus-border/60">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-nexus-accent/20 border border-nexus-accent/30 flex items-center justify-center shadow-lg shadow-nexus-accent/10">
              <Brain className="w-5 h-5 text-nexus-accent" />
            </div>
            <div>
              <span className="text-lg font-bold text-white tracking-tight">NEXUS</span>
              <span className="hidden sm:inline-block ml-2 text-xs text-nexus-text-dim border-l border-nexus-border pl-2">
                Career Intelligence
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <a
              href="http://localhost:8000"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden md:inline-flex items-center gap-1.5 text-xs text-nexus-text-muted hover:text-white px-3 py-1.5 rounded-lg bg-nexus-surface-2 border border-nexus-border transition-colors"
            >
              <Database size={13} className="text-cyan-400" />
              <span>Backend Control (Port 8000)</span>
            </a>
            <Link href="/login" className="nexus-btn-ghost text-sm">
              Sign In
            </Link>
            <Link href="/login" className="nexus-btn-primary text-sm">
              <span>Get Started</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-12 pb-16 px-6">
        {/* Background glow accents */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[350px] bg-nexus-accent/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-1/3 left-1/4 w-[400px] h-[250px] bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative max-w-5xl mx-auto text-center space-y-6">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-nexus-surface-2 border border-nexus-border shadow-inner">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-semibold text-emerald-400">
              {stats ? `${stats.counts.total_listings} Opportunities Ingested` : 'Live Pipeline Active'}
            </span>
            <span className="text-nexus-border">&bull;</span>
            <span className="text-xs text-nexus-text-muted">768-dim Vectorized</span>
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white leading-tight">
            Autonomous Career Intelligence <br />
            <span className="bg-gradient-to-r from-nexus-accent via-indigo-400 to-cyan-400 bg-clip-text text-transparent">
              Matched in Milliseconds.
            </span>
          </h1>

          <p className="max-w-2xl mx-auto text-base sm:text-lg text-nexus-text-muted">
            Ingests real-time job board listings via anti-detection stealth scrapers, enforces structure
            via Gemini AI, and computes cosine similarity against your resume using PostgreSQL pgvector.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
            <Link href="/login" className="nexus-btn-primary px-6 py-3 text-base shadow-xl shadow-nexus-accent/20">
              <Sparkles size={18} />
              <span>Upload Resume to Match</span>
            </Link>
            <a
              href="#explorer"
              className="nexus-btn-secondary px-5 py-3 text-base"
            >
              <Search size={16} />
              <span>Explore Live Jobs</span>
            </a>
          </div>
        </div>
      </section>

      {/* Real-Time Telemetry Grid */}
      <section className="max-w-7xl mx-auto px-6 pb-12">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="nexus-card bg-nexus-surface/80 border-nexus-border hover:border-cyan-500/40 transition-all">
            <div className="flex items-center justify-between text-nexus-text-muted mb-2">
              <span className="text-xs font-semibold tracking-wider uppercase">Total Ingested Jobs</span>
              <Briefcase size={16} className="text-cyan-400" />
            </div>
            <div className="text-3xl font-bold text-white">
              {isLoading ? '...' : stats?.counts.total_listings ?? 0}
            </div>
            <div className="text-xs text-nexus-text-dim mt-1 flex items-center gap-1.5">
              <CheckCircle2 size={12} className="text-emerald-400" />
              <span>Live in PostgreSQL pgvector</span>
            </div>
          </div>

          <div className="nexus-card bg-nexus-surface/80 border-nexus-border hover:border-emerald-500/40 transition-all">
            <div className="flex items-center justify-between text-nexus-text-muted mb-2">
              <span className="text-xs font-semibold tracking-wider uppercase">AI Vectorization</span>
              <Cpu size={16} className="text-emerald-400" />
            </div>
            <div className="text-3xl font-bold text-white">
              {isLoading ? '...' : `${stats?.counts.vector_percentage ?? 100}%`}
            </div>
            <div className="text-xs text-emerald-400 mt-1 flex items-center gap-1.5">
              <span>{stats?.counts.vectorized_listings ?? 0} listings with 768-dim vectors</span>
            </div>
          </div>

          <div className="nexus-card bg-nexus-surface/80 border-nexus-border hover:border-nexus-accent/40 transition-all">
            <div className="flex items-center justify-between text-nexus-text-muted mb-2">
              <span className="text-xs font-semibold tracking-wider uppercase">Active Scrapers</span>
              <ShieldCheck size={16} className="text-nexus-accent" />
            </div>
            <div className="text-3xl font-bold text-white">5 Sources</div>
            <div className="text-xs text-nexus-text-dim mt-1">
              <span>&lt; 10% bot detection probability</span>
            </div>
          </div>

          <div className="nexus-card bg-nexus-surface/80 border-nexus-border hover:border-purple-500/40 transition-all">
            <div className="flex items-center justify-between text-nexus-text-muted mb-2">
              <span className="text-xs font-semibold tracking-wider uppercase">Search Latency</span>
              <TrendingUp size={16} className="text-purple-400" />
            </div>
            <div className="text-3xl font-bold text-white">&lt; 50 ms</div>
            <div className="text-xs text-nexus-text-dim mt-1">
              <span>Sub-millisecond cosine distance</span>
            </div>
          </div>
        </div>

        {/* Source Breakdown Badges */}
        {stats?.sources && (
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <span className="text-xs text-nexus-text-dim font-medium mr-1">Ingestion Sources:</span>
            {Object.entries(stats.sources).map(([source, count]) => (
              <span
                key={source}
                className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md bg-nexus-surface-2 border border-nexus-border text-nexus-text-muted"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                <span className="font-medium text-white">{sourceLabels[source] || source}:</span>
                <span className="text-nexus-text-dim">{count}</span>
              </span>
            ))}
          </div>
        )}
      </section>

      {/* Live Opportunities Explorer */}
      <section id="explorer" className="max-w-7xl mx-auto px-6 pb-24">
        <div className="nexus-card border-nexus-border bg-nexus-surface/90 shadow-2xl p-6 sm:p-8">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-nexus-border">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <span>⚡</span> Real-Time Job Opportunity Feed
              </h2>
              <p className="text-xs text-nexus-text-muted mt-1">
                Showing latest scraped opportunities synchronized directly from the backend database.
              </p>
            </div>

            <button
              type="button"
              onClick={() => refetch()}
              className="nexus-btn-ghost text-xs self-start md:self-auto border border-nexus-border"
            >
              <RefreshCw size={12} />
              <span>Refresh Telemetry</span>
            </button>
          </div>

          {/* Search and Filters */}
          <div className="pt-6 pb-6 flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-nexus-text-dim" size={16} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter by role (e.g. Senior Python), company, or skills (FastAPI, React)..."
                className="nexus-input pl-10"
              />
            </div>

            {/* Source Pills & Stipend Filter */}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-1.5">
                {['all', 'levels_fyi', 'remoteok', 'remotive', 'weworkremotely', 'arbeitnow', 'github'].map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setSelectedSource(key)}
                    className={`text-xs px-3 py-2 rounded-lg font-medium transition-all ${
                      selectedSource === key
                        ? 'bg-nexus-accent text-white shadow-sm'
                        : 'bg-nexus-surface-2 text-nexus-text-muted hover:text-white border border-nexus-border'
                    }`}
                  >
                    {sourceLabels[key] || key}
                  </button>
                ))}
              </div>

              {/* Explicit Stipend Only Toggle */}
              <button
                type="button"
                onClick={() => setOnlyWithStipend(!onlyWithStipend)}
                className={`text-xs px-3 py-2 rounded-lg font-medium transition-all flex items-center gap-1.5 ${
                  onlyWithStipend
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm'
                    : 'bg-nexus-surface-2 text-nexus-text-muted hover:text-white border border-nexus-border'
                }`}
              >
                <span>💰</span>
                <span>Explicit Stipend / Salary Only</span>
                {onlyWithStipend && (
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                )}
              </button>
            </div>
          </div>

          {/* Job Feed Cards */}
          {isLoading ? (
            <div className="text-center py-16 space-y-3">
              <div className="w-8 h-8 border-2 border-nexus-accent border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-sm text-nexus-text-muted">Loading live opportunities from backend...</p>
            </div>
          ) : isError ? (
            <div className="text-center py-16 space-y-2 text-rose-400">
              <p className="font-semibold">Unable to connect to the backend API.</p>
              <p className="text-xs text-nexus-text-dim">
                Make sure `uvicorn app.main:app --reload --port 8000` is running.
              </p>
            </div>
          ) : filteredListings.length === 0 ? (
            <div className="text-center py-16 text-nexus-text-dim text-sm">
              No matching listings found for this query.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredListings.map((job) => (
                <div
                  key={job.id}
                  className="nexus-card bg-nexus-surface-2/60 border-nexus-border hover:border-nexus-accent/50 hover:bg-nexus-surface-2 transition-all group flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold text-white group-hover:text-nexus-accent transition-colors text-base line-clamp-1">
                          {job.title}
                        </h3>
                        <p className="text-sm text-cyan-400 font-medium mt-0.5">{job.company}</p>
                      </div>

                      <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-nexus-surface border border-nexus-border text-nexus-text-dim uppercase tracking-wider whitespace-nowrap">
                        {job.source_name}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-nexus-text-muted mt-2.5">
                      <span className="flex items-center gap-1">
                        <MapPin size={12} className="text-nexus-text-dim" />
                        <span>{job.location}</span>
                      </span>
                      {job.remote_ok && (
                        <span className="text-emerald-400 font-medium bg-emerald-500/10 px-1.5 py-0.5 rounded text-[11px]">
                          Remote
                        </span>
                      )}
                    </div>

                    {/* Skills pills */}
                    {job.skills && job.skills.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-3">
                        {job.skills.slice(0, 4).map((skill, idx) => (
                          <span
                            key={idx}
                            className="text-[11px] px-2 py-0.5 rounded bg-nexus-surface text-nexus-text-muted border border-nexus-border/60"
                          >
                            {skill}
                          </span>
                        ))}
                        {job.skills.length > 4 && (
                          <span className="text-[11px] px-1.5 py-0.5 rounded text-nexus-text-dim">
                            +{job.skills.length - 4}
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between pt-4 mt-4 border-t border-nexus-border/50 text-xs">
                    <span className="text-amber-400 font-mono font-medium">
                      {job.stipend !== 'Not specified' ? job.stipend : 'Compensation unlisted'}
                    </span>

                    <div className="flex items-center gap-3">
                      {job.has_embedding && (
                        <span className="text-[11px] text-emerald-400 font-mono flex items-center gap-1">
                          <CheckCircle2 size={11} /> 768-dim Vector
                        </span>
                      )}
                      <a
                        href={job.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-nexus-accent hover:text-white flex items-center gap-1 font-medium transition-colors"
                      >
                        <span>Apply</span>
                        <ExternalLink size={12} />
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-nexus-border/60 py-8 px-6 text-center text-xs text-nexus-text-dim">
        <p>
          NEXUS Autonomous Career Intelligence &bull; Powered by Gemini 3.5 Flash Lite & Gemini Embedding 2
        </p>
      </footer>
    </div>
  );
}
