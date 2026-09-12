'use client';

import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { ResumeResponse, MatchResponse, MatchComputeResponse } from '@/types/api';
import { cn, formatDate, formatMatchScore } from '@/lib/utils';
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

      if (!file.name.toLowerCase().endsWith('.pdf')) {
        toast.error('Only PDF files are accepted.');
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
function MatchCard({ match, onToggleSave }: { match: MatchResponse; onToggleSave: (id: string) => void }) {
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
  const queryClient = useQueryClient();

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

      {/* Matches Grid */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Your Matches</h2>

        {matchesLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : matches && matches.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {matches.map((m) => (
              <MatchCard key={m.id} match={m} onToggleSave={(id) => saveMutation.mutate(id)} />
            ))}
          </div>
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
