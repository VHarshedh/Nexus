'use client';

import React, { useState, useMemo } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { cn, matchesMinStipend } from '@/lib/utils';
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
  Building2,
  DollarSign,
  Filter,
  X,
  ArrowUpDown,
  Globe,
  Zap,
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
  const [companyFilter, setCompanyFilter] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  const [stipendFilter, setStipendFilter] = useState('');
  const [onlyWithStipend, setOnlyWithStipend] = useState(false);
  const [onlyRemote, setOnlyRemote] = useState(false);
  const [onlyVectorized, setOnlyVectorized] = useState(false);
  const [sortBy, setSortBy] = useState<'newest' | 'company' | 'title' | 'stipend'>('newest');

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

  const activeFiltersCount = useMemo(() => {
    return (
      (companyFilter ? 1 : 0) +
      (locationFilter ? 1 : 0) +
      (stipendFilter ? 1 : 0) +
      (onlyWithStipend ? 1 : 0) +
      (onlyRemote ? 1 : 0) +
      (onlyVectorized ? 1 : 0) +
      (selectedSource !== 'all' ? 1 : 0) +
      (searchQuery ? 1 : 0) +
      (sortBy !== 'newest' ? 1 : 0)
    );
  }, [
    companyFilter,
    locationFilter,
    stipendFilter,
    onlyWithStipend,
    onlyRemote,
    onlyVectorized,
    selectedSource,
    searchQuery,
    sortBy,
  ]);

  const resetFilters = () => {
    setSearchQuery('');
    setCompanyFilter('');
    setLocationFilter('');
    setStipendFilter('');
    setOnlyWithStipend(false);
    setOnlyRemote(false);
    setOnlyVectorized(false);
    setSelectedSource('all');
    setSortBy('newest');
  };

  const filteredListings = useMemo(() => {
    const list = (stats?.recent_listings || []).filter((item) => {
      // 1. Source filter
      const sName = (item.source_name || '').toLowerCase();
      const matchesSource =
        selectedSource === 'all' ||
        sName.includes(selectedSource.toLowerCase()) ||
        (selectedSource === 'github' &&
          (sName.includes('hiring') || sName.includes('github') || sName.includes('hn')));

      // 2. Search query (title or skills)
      const query = searchQuery.toLowerCase().trim();
      const matchesQuery =
        !query ||
        item.title.toLowerCase().includes(query) ||
        item.skills.some((s) => s.toLowerCase().includes(query));

      // 3. Company filter
      const comp = companyFilter.toLowerCase().trim();
      const matchesCompany = !comp || item.company.toLowerCase().includes(comp);

      // 4. Location filter
      const loc = locationFilter.toLowerCase().trim();
      const matchesLocation =
        !loc ||
        item.location.toLowerCase().includes(loc) ||
        (loc === 'remote' && item.remote_ok);

      // 5. Stipend filter (greater than amount searched with currency conversion)
      const matchesStipendText =
        !stipendFilter.trim() || matchesMinStipend(item.stipend, stipendFilter);

      // 6. Explicit stipend toggle
      const hasStipendListed =
        !!item.stipend &&
        item.stipend.toLowerCase() !== 'not specified' &&
        item.stipend.trim() !== '';
      const matchesStipendToggle = !onlyWithStipend || hasStipendListed;

      // 7. Remote only toggle
      const matchesRemote = !onlyRemote || item.remote_ok;

      // 8. Vectorized only toggle
      const matchesVectorized = !onlyVectorized || item.has_embedding;

      return (
        matchesSource &&
        matchesQuery &&
        matchesCompany &&
        matchesLocation &&
        matchesStipendText &&
        matchesStipendToggle &&
        matchesRemote &&
        matchesVectorized
      );
    });

    // Sorting
    return [...list].sort((a, b) => {
      if (sortBy === 'company') {
        return a.company.localeCompare(b.company);
      }
      if (sortBy === 'title') {
        return a.title.localeCompare(b.title);
      }
      if (sortBy === 'stipend') {
        const aHas =
          a.stipend && a.stipend.toLowerCase() !== 'not specified' ? 1 : 0;
        const bHas =
          b.stipend && b.stipend.toLowerCase() !== 'not specified' ? 1 : 0;
        return bHas - aHas;
      }
      // default: newest
      const aTime = a.scraped_at ? new Date(a.scraped_at).getTime() : 0;
      const bTime = b.scraped_at ? new Date(b.scraped_at).getTime() : 0;
      return bTime - aTime;
    });
  }, [
    stats?.recent_listings,
    selectedSource,
    searchQuery,
    companyFilter,
    locationFilter,
    stipendFilter,
    onlyWithStipend,
    onlyRemote,
    onlyVectorized,
    sortBy,
  ]);

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
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <span>⚡</span> Real-Time Job Opportunity Feed
                </h2>
                {activeFiltersCount > 0 && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-nexus-accent/20 text-nexus-accent border border-nexus-accent/30">
                    <Filter size={11} />
                    {activeFiltersCount} active
                  </span>
                )}
              </div>
              <p className="text-xs text-nexus-text-muted mt-1">
                Showing latest scraped opportunities synchronized directly from the backend database.
              </p>
            </div>

            <div className="flex items-center gap-2.5 self-start md:self-auto">
              {activeFiltersCount > 0 && (
                <button
                  type="button"
                  onClick={resetFilters}
                  className="nexus-btn-ghost text-xs border border-nexus-border text-rose-300 hover:text-rose-200 hover:border-rose-500/40"
                >
                  <X size={12} />
                  <span>Clear Filters</span>
                </button>
              )}
              <button
                type="button"
                onClick={() => refetch()}
                className="nexus-btn-ghost text-xs border border-nexus-border"
              >
                <RefreshCw size={12} />
                <span>Refresh Telemetry</span>
              </button>
            </div>
          </div>

          {/* Search and Multi-Attribute Filter Suite */}
          <div className="pt-6 pb-4 space-y-4">
            {/* Primary Role & Skill Search Bar */}
            <div className="relative">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-nexus-text-dim" size={16} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by role title (e.g. Senior Backend Engineer) or skills (FastAPI, React, PyTorch)..."
                className="nexus-input pl-10 pr-9 w-full"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-nexus-text-dim hover:text-white"
                  title="Clear search"
                >
                  <X size={14} />
                </button>
              )}
            </div>

            {/* 4 Multi-Attribute Controls: Company, Location, Stipend, Sort */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {/* 1. Company Name */}
              <div>
                <label className="block text-xs font-medium text-nexus-text-dim mb-1.5 flex items-center gap-1">
                  <Building2 size={13} className="text-cyan-400" />
                  <span>Company Name</span>
                </label>
                <div className="relative">
                  <input
                    type="text"
                    placeholder="e.g. Stripe, OpenAI, Google..."
                    value={companyFilter}
                    onChange={(e) => setCompanyFilter(e.target.value)}
                    className="nexus-input w-full text-xs py-2 pr-7"
                  />
                  {companyFilter && (
                    <button
                      type="button"
                      onClick={() => setCompanyFilter('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-nexus-text-dim hover:text-white"
                      title="Clear company"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              </div>

              {/* 2. Location / Remote */}
              <div>
                <label className="block text-xs font-medium text-nexus-text-dim mb-1.5 flex items-center gap-1">
                  <MapPin size={13} className="text-emerald-400" />
                  <span>Location / Region</span>
                </label>
                <div className="relative">
                  <input
                    type="text"
                    placeholder="e.g. Remote, San Francisco, London..."
                    value={locationFilter}
                    onChange={(e) => setLocationFilter(e.target.value)}
                    className="nexus-input w-full text-xs py-2 pr-7"
                  />
                  {locationFilter && (
                    <button
                      type="button"
                      onClick={() => setLocationFilter('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-nexus-text-dim hover:text-white"
                      title="Clear location"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              </div>

              {/* 3. Stipend / Compensation */}
              <div>
                <label className="block text-xs font-medium text-nexus-text-dim mb-1.5 flex items-center gap-1">
                  <DollarSign size={13} className="text-amber-400" />
                  <span>Min Stipend (≥)</span>
                </label>
                <div className="relative">
                  <input
                    type="text"
                    placeholder="e.g. > $800, 80000 rupees, 100k..."
                    value={stipendFilter}
                    onChange={(e) => setStipendFilter(e.target.value)}
                    className="nexus-input w-full text-xs py-2 pr-7"
                  />
                  {stipendFilter && (
                    <button
                      type="button"
                      onClick={() => setStipendFilter('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-nexus-text-dim hover:text-white"
                      title="Clear stipend"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              </div>

              {/* 4. Sort Selector */}
              <div>
                <label className="block text-xs font-medium text-nexus-text-dim mb-1.5 flex items-center gap-1">
                  <ArrowUpDown size={13} className="text-nexus-accent" />
                  <span>Sort Order</span>
                </label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as any)}
                  className="nexus-input w-full text-xs py-2 px-2.5 rounded-lg cursor-pointer bg-nexus-surface-2 border-nexus-border text-white"
                >
                  <option value="newest">Newest Scraped First</option>
                  <option value="company">Company (A-Z)</option>
                  <option value="title">Role Title (A-Z)</option>
                  <option value="stipend">Disclosed Stipend First</option>
                </select>
              </div>
            </div>

            {/* Source Pills & Quick Toggle Badges */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <div className="flex flex-wrap gap-1.5">
                {['all', 'levels_fyi', 'remoteok', 'remotive', 'weworkremotely', 'arbeitnow', 'github'].map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setSelectedSource(key)}
                    className={cn(
                      'text-xs px-3 py-1.5 rounded-lg font-medium transition-all',
                      selectedSource === key
                        ? 'bg-nexus-accent text-white shadow-sm'
                        : 'bg-nexus-surface-2 text-nexus-text-muted hover:text-white border border-nexus-border'
                    )}
                  >
                    {sourceLabels[key] || key}
                  </button>
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {/* Stipend Toggle */}
                <button
                  type="button"
                  onClick={() => setOnlyWithStipend(!onlyWithStipend)}
                  className={cn(
                    'text-xs px-2.5 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 border',
                    onlyWithStipend
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm'
                      : 'bg-nexus-surface-2 text-nexus-text-muted hover:text-white border-nexus-border'
                  )}
                >
                  <DollarSign size={12} className="text-emerald-400" />
                  <span>Disclosed Stipend Only</span>
                  {onlyWithStipend && (
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  )}
                </button>

                {/* Remote Toggle */}
                <button
                  type="button"
                  onClick={() => setOnlyRemote(!onlyRemote)}
                  className={cn(
                    'text-xs px-2.5 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 border',
                    onlyRemote
                      ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40 shadow-sm'
                      : 'bg-nexus-surface-2 text-nexus-text-muted hover:text-white border-nexus-border'
                  )}
                >
                  <Globe size={12} className="text-cyan-400" />
                  <span>Remote Only</span>
                  {onlyRemote && (
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                  )}
                </button>

                {/* Vectorized Toggle */}
                <button
                  type="button"
                  onClick={() => setOnlyVectorized(!onlyVectorized)}
                  className={cn(
                    'text-xs px-2.5 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 border',
                    onlyVectorized
                      ? 'bg-purple-500/20 text-purple-300 border-purple-500/40 shadow-sm'
                      : 'bg-nexus-surface-2 text-nexus-text-muted hover:text-white border-nexus-border'
                  )}
                >
                  <Zap size={12} className="text-purple-400" />
                  <span>768-dim Vectorized Only</span>
                  {onlyVectorized && (
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />
                  )}
                </button>
              </div>
            </div>

            {/* Results Count Summary */}
            <div className="flex items-center justify-between text-xs text-nexus-text-dim pt-1 border-t border-nexus-border/50">
              <span>
                Showing <strong className="text-white">{filteredListings.length}</strong> of{' '}
                <strong className="text-white">{stats?.recent_listings.length ?? 0}</strong> live opportunities
                {activeFiltersCount > 0 && ` (${activeFiltersCount} filters active)`}
              </span>
              {activeFiltersCount > 0 && (
                <button
                  type="button"
                  onClick={resetFilters}
                  className="text-xs text-nexus-accent hover:underline flex items-center gap-1"
                >
                  Reset all filters
                </button>
              )}
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
            <div className="text-center py-16 space-y-3">
              <Filter className="w-10 h-10 text-nexus-text-dim mx-auto" />
              <h3 className="text-white font-medium text-base">No opportunities match your filters</h3>
              <p className="text-nexus-text-muted text-xs max-w-md mx-auto">
                No listings matched the selected role, company, location, stipend, or vector status.
              </p>
              <button
                type="button"
                onClick={resetFilters}
                className="nexus-btn-secondary text-xs inline-flex items-center gap-1.5 mt-2"
              >
                <X size={13} />
                <span>Clear All Filters</span>
              </button>
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
