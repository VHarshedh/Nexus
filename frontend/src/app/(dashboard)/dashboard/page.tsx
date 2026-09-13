'use client';

import React, { useCallback, useMemo, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { ResumeResponse, MatchResponse, MatchComputeResponse } from '@/types/api';
import { cn, formatDate, formatMatchScore, matchesMinStipend } from '@/lib/utils';
import { MAX_RESUME_FILE_BYTES, validateResumeFile } from '@/lib/resume-file';
import { MatchCard } from '@/components/match-card';
import { useAuth } from '@/lib/auth-context';
import { OnboardingWizard } from '@/components/onboarding-wizard';
import toast from 'react-hot-toast';
import {
  Upload,
  FileText,
  Zap,
  Loader2,
  MapPin,
  Wifi,
  Calendar,
  DollarSign,
  Bookmark,
  BookmarkCheck,
  ExternalLink,
  Sparkles,
  Search,
  Building2,
  SlidersHorizontal,
  ArrowUpDown,
  X,
  Filter,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Resume Upload Zone
// ---------------------------------------------------------------------------
function ResumeUploadZone() {
  const queryClient = useQueryClient();
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);

  const { data: resumes } = useQuery<ResumeResponse[]>({
    queryKey: ['resumes'],
    queryFn: async () => (await api.get('/api/resume/')).data,
  });

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      const validationError = validateResumeFile(file);
      if (validationError) {
        toast.error(validationError);
        return;
      }

      setUploading(true);
      setUploadProgress(0);
      const formData = new FormData();
      formData.append('file', file);

      try {
        await api.post('/api/resume/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (e) => {
            if (e.total) setUploadProgress(Math.round((e.loaded / e.total) * 100));
          },
        });
        toast.success('Resume uploaded successfully!');
        queryClient.invalidateQueries({ queryKey: ['resumes'] });
      } catch {
        toast.error('Failed to upload resume.');
      } finally {
        setUploading(false);
        setUploadProgress(0);
      }
    },
    [queryClient],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    maxSize: MAX_RESUME_FILE_BYTES,
    disabled: uploading,
  });

  return (
    <div className="nexus-card">
      <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        <FileText className="w-5 h-5 text-nexus-accent" />
        Resume Upload
      </h2>

      <div
        {...getRootProps()}
        className={cn(
          'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all duration-200',
          isDragActive
            ? 'border-nexus-accent bg-nexus-accent/10'
            : 'border-nexus-border hover:border-nexus-accent/50 hover:bg-nexus-surface-2',
          uploading && 'opacity-50 cursor-not-allowed',
        )}
      >
        <input {...getInputProps()} />
        <Upload className="w-10 h-10 text-nexus-text-dim mx-auto mb-3" />
        {isDragActive ? (
          <p className="text-nexus-accent font-medium">Drop your PDF here…</p>
        ) : (
          <>
            <p className="text-nexus-text-muted">Drag & drop your resume PDF, or click to browse</p>
            <p className="text-nexus-text-dim text-sm mt-1">PDF files only</p>
          </>
        )}
      </div>

      {/* Upload progress */}
      {uploading && (
        <div className="mt-4">
          <div className="flex items-center justify-between text-sm text-nexus-text-muted mb-1">
            <span>Uploading…</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="h-2 bg-nexus-surface-2 rounded-full overflow-hidden">
            <div
              className="h-full bg-nexus-accent rounded-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Existing resumes */}
      {resumes && resumes.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-sm text-nexus-text-dim">
            {resumes.length} resume{resumes.length > 1 ? 's' : ''} on file
          </p>
          {resumes.map((r) => (
            <div key={r.id} className="flex items-center gap-3 px-3 py-2 bg-nexus-surface-2 rounded-lg text-sm">
              <FileText className="w-4 h-4 text-nexus-accent flex-shrink-0" />
              <span className="text-nexus-text-muted truncate flex-1">
                {r.raw_text.slice(0, 60)}…
              </span>
              <span className="text-nexus-text-dim text-xs flex-shrink-0">{formatDate(r.uploaded_at)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Match Card
// ---------------------------------------------------------------------------
// The production card lives in components/match-card.tsx so it can be tested
// independently from this App Router route module.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function LegacyMatchCard({ match, onToggleSave }: { match: MatchResponse; onToggleSave: (id: string) => void }) {
  const listing = match.listing;
  if (!listing) return null;

  const { percent, color } = formatMatchScore(match.match_score);

  return (
    <div className="nexus-card-hover animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-white truncate">{listing.title || 'Untitled Position'}</h3>
          <p className="text-nexus-text-muted text-sm">{listing.company || 'Unknown Company'}</p>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={() => onToggleSave(match.id)}
            className={cn(
              'p-1.5 rounded-lg transition-all',
              match.saved
                ? 'text-nexus-accent bg-nexus-accent/15'
                : 'text-nexus-text-dim hover:text-nexus-accent hover:bg-nexus-surface-2',
            )}
            title={match.saved ? 'Remove from shortlist' : 'Save to shortlist'}
          >
            {match.saved ? <BookmarkCheck size={18} /> : <Bookmark size={18} />}
          </button>
          <a
            href={listing.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 rounded-lg text-nexus-text-dim hover:text-nexus-text hover:bg-nexus-surface-2 transition-all"
            title="View original listing"
          >
            <ExternalLink size={18} />
          </a>
        </div>
      </div>

      {/* Badges */}
      <div className="flex flex-wrap gap-2 mb-3">
        {listing.location && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-nexus-surface-2 text-nexus-text-muted text-xs rounded-md">
            <MapPin size={12} />
            {listing.location}
          </span>
        )}
        {listing.remote_ok && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-500/15 text-emerald-400 text-xs rounded-md">
            <Wifi size={12} />
            Remote
          </span>
        )}
        {listing.stipend && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-nexus-surface-2 text-nexus-text-muted text-xs rounded-md">
            <DollarSign size={12} />
            {listing.stipend}
          </span>
        )}
        {listing.deadline && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-nexus-surface-2 text-nexus-text-muted text-xs rounded-md">
            <Calendar size={12} />
            {formatDate(listing.deadline)}
          </span>
        )}
      </div>

      {/* Match Score Bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-nexus-text-muted">Match Score</span>
          <span className="font-semibold text-white">{percent}</span>
        </div>
        <div className="h-2 bg-nexus-surface-2 rounded-full overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all duration-500', color)}
            style={{ width: percent }}
          />
        </div>
      </div>

      {/* Justification */}
      {match.justification && (
        <p className="text-sm text-nexus-text-dim italic leading-relaxed">
          &ldquo;{match.justification}&rdquo;
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Skeleton Card
// ---------------------------------------------------------------------------
function SkeletonCard() {
  return (
    <div className="nexus-card animate-pulse">
      <div className="h-5 bg-nexus-surface-2 rounded w-3/4 mb-2" />
      <div className="h-4 bg-nexus-surface-2 rounded w-1/2 mb-4" />
      <div className="flex gap-2 mb-3">
        <div className="h-5 bg-nexus-surface-2 rounded w-20" />
        <div className="h-5 bg-nexus-surface-2 rounded w-16" />
      </div>
      <div className="h-2 bg-nexus-surface-2 rounded-full mb-3" />
      <div className="h-4 bg-nexus-surface-2 rounded w-full" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Dashboard Page
// ---------------------------------------------------------------------------
export default function DashboardPage() {
  const { user, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();

  // Filters State
  const [companyFilter, setCompanyFilter] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  const [minScore, setMinScore] = useState<number>(0);
  const [stipendFilter, setStipendFilter] = useState('');
  const [onlyWithStipend, setOnlyWithStipend] = useState(false);
  const [sortBy, setSortBy] = useState<'score_desc' | 'score_asc' | 'company' | 'title'>('score_desc');

  const { data: matches, isLoading: matchesLoading } = useQuery<MatchResponse[]>({
    queryKey: ['matches'],
    queryFn: async () => (await api.get('/api/matches/')).data,
  });

  const computeMutation = useMutation<MatchComputeResponse>({
    mutationFn: async () => (await api.post('/api/matches/compute')).data,
    onSuccess: (data) => {
      toast.success(`Found ${data.computed} matches!`);
      queryClient.invalidateQueries({ queryKey: ['matches'] });
    },
    onError: () => {
      toast.error('Failed to compute matches. Make sure you have a resume uploaded.');
    },
  });

  const saveMutation = useMutation({
    mutationFn: async (matchId: string) => (await api.patch(`/api/matches/${matchId}/save`)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matches'] });
    },
    onError: () => {
      toast.error('Failed to update shortlist.');
    },
  });

  // Filter and sort matches based on Company, Location, Score, and Stipend
  const filteredMatches = useMemo(() => {
    if (!matches) return [];

    return matches
      .filter((m) => {
        const listing = m.listing;
        if (!listing) return false;

        // 1. Company Name Filter
        if (companyFilter.trim()) {
          const comp = (listing.company || '').toLowerCase();
          if (!comp.includes(companyFilter.trim().toLowerCase())) {
            return false;
          }
        }

        // 2. Location / Remote Filter
        if (locationFilter.trim()) {
          const q = locationFilter.trim().toLowerCase();
          const loc = (listing.location || '').toLowerCase();
          const matchesRemote = q.includes('remote') && listing.remote_ok;
          if (!loc.includes(q) && !matchesRemote) {
            return false;
          }
        }

        // 3. Match Score Filter
        const scorePercent = Math.round(m.match_score * 100);
        if (scorePercent < minScore) {
          return false;
        }

        // 4. Stipend / Compensation Filter (greater than amount searched with currency conversion)
        if (onlyWithStipend && !listing.stipend?.trim()) {
          return false;
        }
        if (stipendFilter.trim()) {
          if (!matchesMinStipend(listing.stipend, stipendFilter)) {
            return false;
          }
        }

        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'score_desc') return b.match_score - a.match_score;
        if (sortBy === 'score_asc') return a.match_score - b.match_score;
        if (sortBy === 'company') {
          return (a.listing?.company || '').localeCompare(b.listing?.company || '');
        }
        if (sortBy === 'title') {
          return (a.listing?.title || '').localeCompare(b.listing?.title || '');
        }
        return 0;
      });
  }, [matches, companyFilter, locationFilter, minScore, stipendFilter, onlyWithStipend, sortBy]);

  const hasActiveFilters =
    Boolean(companyFilter.trim()) ||
    Boolean(locationFilter.trim()) ||
    minScore > 0 ||
    Boolean(stipendFilter.trim()) ||
    onlyWithStipend ||
    sortBy !== 'score_desc';

  const resetFilters = () => {
    setCompanyFilter('');
    setLocationFilter('');
    setMinScore(0);
    setStipendFilter('');
    setOnlyWithStipend(false);
    setSortBy('score_desc');
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-nexus-bg flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-nexus-accent" />
      </div>
    );
  }

  if (user && !user.onboarded) {
    return <OnboardingWizard />;
  }

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Sparkles className="w-7 h-7 text-nexus-accent" />
          Explore Matches
        </h1>
        <p className="text-nexus-text-muted mt-1">Upload your resume and discover AI-matched opportunities</p>
      </div>

      {/* Upload & Match Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ResumeUploadZone />

        <div className="nexus-card flex flex-col justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white mb-2 flex items-center gap-2">
              <Zap className="w-5 h-5 text-nexus-warning" />
              Semantic Matching
            </h2>
            <p className="text-nexus-text-muted text-sm mb-4">
              Uses pgvector cosine similarity and Gemini AI to match your resume against all scraped job listings,
              then generates a one-line justification for each match.
            </p>
          </div>

          <button
            onClick={() => computeMutation.mutate()}
            disabled={computeMutation.isPending}
            className="nexus-btn-primary w-full justify-center"
          >
            {computeMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Computing Matches…
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                Run Semantic Matching
              </>
            )}
          </button>

          {matches && matches.length > 0 && (
            <p className="text-sm text-nexus-text-dim mt-3 text-center">
              {matches.length} match{matches.length !== 1 ? 'es' : ''} found
            </p>
          )}
        </div>
      </div>

      {/* Matches Grid & Filters */}
      <div>
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div>
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-nexus-accent" />
              Your Matches
            </h2>
            <p className="text-nexus-text-muted text-xs mt-0.5">
              Matched listings ranked by profile similarity and relevance
            </p>
          </div>
          {matches && matches.length > 0 && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-nexus-surface-2 text-nexus-text border border-nexus-border font-medium">
              {filteredMatches.length === matches.length
                ? `${matches.length} opportunities`
                : `Showing ${filteredMatches.length} of ${matches.length}`}
            </span>
          )}
        </div>

        {/* Filter Controls Toolbar */}
        {matches && matches.length > 0 && (
          <div className="nexus-card mb-6 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-nexus-border">
              <div className="flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-nexus-accent" />
                <span className="font-semibold text-white text-sm">Filter Opportunities</span>
                {hasActiveFilters && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-nexus-accent/20 text-nexus-accent font-semibold border border-nexus-accent/30">
                    Filters Active
                  </span>
                )}
              </div>
              {hasActiveFilters && (
                <button
                  onClick={resetFilters}
                  className="text-xs text-nexus-accent hover:text-nexus-accent-hover transition-colors flex items-center gap-1 font-medium"
                >
                  <X size={13} />
                  Reset All Filters
                </button>
              )}
            </div>

            {/* 4 Filter Inputs: Company, Location, Stipend, Match Score */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {/* 1. Company Name */}
              <div>
                <label className="block text-xs font-medium text-nexus-text-dim mb-1.5 flex items-center gap-1">
                  <Building2 size={13} className="text-nexus-text-muted" />
                  Company Name
                </label>
                <div className="relative">
                  <input
                    type="text"
                    placeholder="e.g. Google, Stripe..."
                    value={companyFilter}
                    onChange={(e) => setCompanyFilter(e.target.value)}
                    className="nexus-input w-full text-xs py-2 pr-7"
                  />
                  {companyFilter && (
                    <button
                      onClick={() => setCompanyFilter('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-nexus-text-dim hover:text-white"
                      title="Clear company filter"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              </div>

              {/* 2. Location / Remote */}
              <div>
                <label className="block text-xs font-medium text-nexus-text-dim mb-1.5 flex items-center gap-1">
                  <MapPin size={13} className="text-nexus-text-muted" />
                  Location / Remote
                </label>
                <div className="relative">
                  <input
                    type="text"
                    placeholder="e.g. Remote, San Francisco..."
                    value={locationFilter}
                    onChange={(e) => setLocationFilter(e.target.value)}
                    className="nexus-input w-full text-xs py-2 pr-7"
                  />
                  {locationFilter && (
                    <button
                      onClick={() => setLocationFilter('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-nexus-text-dim hover:text-white"
                      title="Clear location filter"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              </div>

              {/* 3. Stipend / Salary */}
              <div>
                <label className="block text-xs font-medium text-nexus-text-dim mb-1.5 flex items-center gap-1">
                  <DollarSign size={13} className="text-nexus-text-muted" />
                  Min Stipend (≥)
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
                      onClick={() => setStipendFilter('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-nexus-text-dim hover:text-white"
                      title="Clear stipend filter"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              </div>

              {/* 4. Match Score Slider */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-medium text-nexus-text-dim flex items-center gap-1">
                    <Zap size={13} className="text-nexus-warning" />
                    Min Match Score
                  </label>
                  <span className="text-xs font-bold text-white">
                    {minScore === 0 ? 'Any Score' : `≥ ${minScore}%`}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={95}
                  step={5}
                  value={minScore}
                  onChange={(e) => setMinScore(Number(e.target.value))}
                  className="w-full accent-nexus-accent h-2 bg-nexus-surface-2 rounded-lg cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-nexus-text-dim mt-1">
                  <span>0%</span>
                  <span>50%</span>
                  <span>75%</span>
                  <span>95%</span>
                </div>
              </div>
            </div>

            {/* Quick Actions & Sorting Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-nexus-text-dim font-medium mr-1">Quick Score:</span>
                {[0, 60, 75, 85].map((score) => (
                  <button
                    key={score}
                    onClick={() => setMinScore(score)}
                    className={cn(
                      'px-2.5 py-1 text-xs rounded-md transition-all font-medium',
                      minScore === score
                        ? 'bg-nexus-accent text-white shadow-sm'
                        : 'bg-nexus-surface-2 text-nexus-text-muted hover:text-white hover:bg-nexus-surface-2/80 border border-nexus-border',
                    )}
                  >
                    {score === 0 ? 'Any' : `≥ ${score}%`}
                  </button>
                ))}

                <button
                  onClick={() => setOnlyWithStipend(!onlyWithStipend)}
                  className={cn(
                    'px-2.5 py-1 text-xs rounded-md transition-all font-medium flex items-center gap-1.5 border ml-1',
                    onlyWithStipend
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                      : 'bg-nexus-surface-2 text-nexus-text-muted hover:text-white border-nexus-border',
                  )}
                >
                  <DollarSign size={12} />
                  Has Stipend Listed
                </button>
              </div>

              {/* Sort Selector */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-nexus-text-dim font-medium flex items-center gap-1">
                  <ArrowUpDown size={12} />
                  Sort:
                </span>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as any)}
                  className="nexus-input text-xs py-1 px-2.5 rounded-md cursor-pointer bg-nexus-surface-2 border-nexus-border"
                >
                  <option value="score_desc">Match Score (Highest)</option>
                  <option value="score_asc">Match Score (Lowest)</option>
                  <option value="company">Company (A-Z)</option>
                  <option value="title">Role Title (A-Z)</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Results Grid */}
        {matchesLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : matches && matches.length > 0 ? (
          filteredMatches.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredMatches.map((m) => (
                <MatchCard key={m.id} match={m} onToggleSave={(id) => saveMutation.mutate(id)} />
              ))}
            </div>
          ) : (
            <div className="nexus-card text-center py-12">
              <Filter className="w-10 h-10 text-nexus-text-dim mx-auto mb-3" />
              <h3 className="text-white font-medium mb-1">No opportunities match your filters</h3>
              <p className="text-nexus-text-muted text-sm max-w-md mx-auto mb-4">
                None of your {matches.length} matches met the selected company, location, score, or stipend criteria.
              </p>
              <button
                onClick={resetFilters}
                className="nexus-btn-secondary text-xs inline-flex items-center gap-1.5"
              >
                <X size={14} /> Clear All Filters
              </button>
            </div>
          )
        ) : (
          <div className="nexus-card text-center py-12">
            <Search className="w-12 h-12 text-nexus-text-dim mx-auto mb-4" />
            <h3 className="text-white font-medium mb-1">No matches yet</h3>
            <p className="text-nexus-text-muted text-sm">
              Upload a resume and run semantic matching to discover opportunities.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
