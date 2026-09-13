'use client';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { BriefingJobResponse, MatchResponse } from '@/types/api';
import { cn, formatDate, formatMatchScore } from '@/lib/utils';
import toast from 'react-hot-toast';
import {
  Bookmark,
  BookmarkX,
  Search,
  MapPin,
  Wifi,
  DollarSign,
  Calendar,
  ExternalLink,
  BarChart3,
  Filter,
  SortAsc,
  Video,
  Play,
  Sparkles,
  AlertTriangle,
  Bell,
  Check,
} from 'lucide-react';

type SortKey = 'score' | 'company' | 'deadline';
type FilterMode = 'all' | 'alerts' | 'remote' | 'deadline';

export default function ShortlistPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [filterMode, setFilterMode] = useState<FilterMode>('all');
  const [sortBy, setSortBy] = useState<SortKey>('score');

  const { data: allMatches, isLoading } = useQuery<MatchResponse[]>({
    queryKey: ['matches'],
    queryFn: async () => (await api.get('/api/matches/')).data,
  });

  const { data: briefings } = useQuery<BriefingJobResponse[]>({
    queryKey: ['briefings'],
    queryFn: async () => (await api.get('/api/briefings/')).data,
  });

  const unsaveMutation = useMutation({
    mutationFn: async (matchId: string) => (await api.patch(`/api/matches/${matchId}/save`)).data,
    onSuccess: () => {
      toast.success('Removed from shortlist');
      queryClient.invalidateQueries({ queryKey: ['matches'] });
    },
    onError: () => toast.error('Failed to update shortlist.'),
  });

  const dismissMutation = useMutation({
    mutationFn: async (matchId: string) => (await api.patch(`/api/matches/${matchId}/dismiss-alert`)).data,
    onSuccess: () => {
      toast.success('Alert dismissed');
      queryClient.invalidateQueries({ queryKey: ['matches'] });
    },
    onError: () => toast.error('Failed to dismiss alert.'),
  });

  // Count active alerts across all saved matches
  const alertCount = useMemo(() => {
    return (allMatches || []).filter(
      (m) => m.saved && (m.change_alert || m.listing?.is_active === false),
    ).length;
  }, [allMatches]);

  // Filter to saved only, then apply search + filter + sort
  const savedMatches = useMemo(() => {
    let items = (allMatches || []).filter((m) => m.saved);

    // Text search
    if (search.trim()) {
      const q = search.toLowerCase();
      items = items.filter(
        (m) =>
          m.listing?.title?.toLowerCase().includes(q) ||
          m.listing?.company?.toLowerCase().includes(q) ||
          m.change_alert?.toLowerCase().includes(q),
      );
    }

    // Filter mode
    if (filterMode === 'alerts') {
      items = items.filter((m) => m.change_alert || m.listing?.is_active === false);
    } else if (filterMode === 'remote') {
      items = items.filter((m) => m.listing?.remote_ok);
    } else if (filterMode === 'deadline') {
      items = items.filter((m) => m.listing?.deadline);
    }

    // Sort
    items = [...items].sort((a, b) => {
      if (sortBy === 'score') return b.match_score - a.match_score;
      if (sortBy === 'company')
        return (a.listing?.company || '').localeCompare(b.listing?.company || '');
      if (sortBy === 'deadline') {
        const da = a.listing?.deadline || '9999';
        const db = b.listing?.deadline || '9999';
        return da.localeCompare(db);
      }
      return 0;
    });

    return items;
  }, [allMatches, search, filterMode, sortBy]);

  // Skills aggregation across saved listings
  const skillsData = useMemo(() => {
    const counter: Record<string, number> = {};
    (allMatches || [])
      .filter((m) => m.saved && m.listing?.required_skills)
      .forEach((m) => {
        for (const skill of m.listing!.required_skills!) {
          const key = skill.trim().toLowerCase();
          if (key) counter[key] = (counter[key] || 0) + 1;
        }
      });
    return Object.entries(counter)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 10);
  }, [allMatches]);

  const maxSkillCount = skillsData.length > 0 ? skillsData[0][1] : 1;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Bookmark className="w-7 h-7 text-nexus-accent" />
          My Shortlist
        </h1>
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="nexus-card animate-pulse">
              <div className="h-5 bg-nexus-surface-2 rounded w-2/3 mb-2" />
              <div className="h-4 bg-nexus-surface-2 rounded w-1/3" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Bookmark className="w-7 h-7 text-nexus-accent" />
          My Shortlist
        </h1>
        <p className="text-nexus-text-muted mt-1">
          {savedMatches.length} saved position{savedMatches.length !== 1 ? 's' : ''}
          {alertCount > 0 && (
            <span className="ml-2 inline-flex items-center gap-1 text-amber-400 font-medium">
              • {alertCount} change alert{alertCount !== 1 ? 's' : ''} active
            </span>
          )}
        </p>
      </div>

      {/* Skills Aggregation Panel */}
      {skillsData.length > 0 && (
        <div className="nexus-card">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-nexus-accent" />
            Top Required Skills Across Shortlist
          </h2>
          <div className="space-y-2.5">
            {skillsData.map(([skill, count]) => (
              <div key={skill} className="flex items-center gap-3">
                <span className="text-sm text-nexus-text-muted w-32 text-right truncate capitalize">
                  {skill}
                </span>
                <div className="flex-1 h-6 bg-nexus-surface-2 rounded-md overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-nexus-accent-muted to-nexus-accent rounded-md flex items-center px-2 transition-all duration-500"
                    style={{ width: `${Math.max((count / maxSkillCount) * 100, 12)}%` }}
                  >
                    <span className="text-xs text-white font-medium">{count}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-nexus-text-dim" />
          <input
            type="text"
            placeholder="Search by title, company, or alert…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="nexus-input pl-10"
          />
        </div>

        <div className="flex items-center gap-1 bg-nexus-surface rounded-lg border border-nexus-border p-0.5">
          <Filter className="w-4 h-4 text-nexus-text-dim ml-2" />
          {(['all', 'alerts', 'remote', 'deadline'] as FilterMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setFilterMode(mode)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1.5',
                filterMode === mode
                  ? 'bg-nexus-accent text-white'
                  : 'text-nexus-text-muted hover:text-nexus-text',
              )}
            >
              {mode === 'all' ? (
                'All'
              ) : mode === 'alerts' ? (
                <>
                  <Bell size={12} className={alertCount > 0 ? 'text-amber-400' : ''} />
                  <span>Alerts</span>
                  {alertCount > 0 && (
                    <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30">
                      {alertCount}
                    </span>
                  )}
                </>
              ) : mode === 'remote' ? (
                'Remote Only'
              ) : (
                'Has Deadline'
              )}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1 bg-nexus-surface rounded-lg border border-nexus-border p-0.5">
          <SortAsc className="w-4 h-4 text-nexus-text-dim ml-2" />
          {[
            { key: 'score' as SortKey, label: 'Score' },
            { key: 'company' as SortKey, label: 'Company' },
            { key: 'deadline' as SortKey, label: 'Deadline' },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setSortBy(key)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
                sortBy === key
                  ? 'bg-nexus-accent text-white'
                  : 'text-nexus-text-muted hover:text-nexus-text',
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Listings */}
      {savedMatches.length > 0 ? (
        <div className="space-y-3">
          {savedMatches.map((match) => {
            const listing = match.listing;
            if (!listing) return null;
            const { percent, color } = formatMatchScore(match.match_score);
            const isInactive = listing.is_active === false;
            const hasAlert = Boolean(match.change_alert) || isInactive;

            return (
              <div
                key={match.id}
                className={cn(
                  'nexus-card transition-all duration-200',
                  hasAlert
                    ? isInactive
                      ? 'border-red-500/40 bg-red-950/10 hover:border-red-500/60'
                      : 'border-amber-500/40 bg-amber-950/10 hover:border-amber-500/60'
                    : 'hover:border-nexus-border-hover',
                )}
              >
                <div className="flex items-center gap-4">
                  {/* Score */}
                  <div className="flex-shrink-0 w-16 text-center">
                    <span className="text-lg font-bold text-white">{percent}</span>
                    <div className="h-1.5 bg-nexus-surface-2 rounded-full mt-1 overflow-hidden">
                      <div className={cn('h-full rounded-full', color)} style={{ width: percent }} />
                    </div>
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-white truncate">
                        {listing.title || 'Untitled Position'}
                      </h3>
                      {isInactive && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-red-500/20 text-red-400 border border-red-500/30">
                          Inactive / Taken Down
                        </span>
                      )}
                      {!isInactive && match.change_alert && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center gap-1">
                          <Bell size={10} /> Updated
                        </span>
                      )}
                    </div>
                    <p className="text-nexus-text-muted text-sm">{listing.company || 'Unknown Company'}</p>
                    <div className="flex flex-wrap gap-2 mt-1.5">
                      {listing.location && (
                        <span className="inline-flex items-center gap-1 text-xs text-nexus-text-dim">
                          <MapPin size={11} /> {listing.location}
                        </span>
                      )}
                      {listing.remote_ok && (
                        <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
                          <Wifi size={11} /> Remote
                        </span>
                      )}
                      {listing.stipend && (
                        <span className="inline-flex items-center gap-1 text-xs text-nexus-text-dim">
                          <DollarSign size={11} /> {listing.stipend}
                        </span>
                      )}
                      {listing.deadline && (
                        <span className="inline-flex items-center gap-1 text-xs text-nexus-text-dim">
                          <Calendar size={11} /> {formatDate(listing.deadline)}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <a
                      href={listing.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="nexus-btn-ghost"
                      title="View listing"
                    >
                      <ExternalLink size={16} />
                    </a>
                    <button
                      onClick={() => unsaveMutation.mutate(match.id)}
                      className="nexus-btn-ghost text-nexus-danger hover:bg-red-500/10"
                      title="Remove from shortlist"
                    >
                      <BookmarkX size={16} />
                    </button>
                  </div>
                </div>

                {/* Change Detection & Takedown Alert Banner */}
                {hasAlert && (
                  <div
                    className={cn(
                      'mt-3 p-3 rounded-lg border flex items-start justify-between gap-3 text-xs transition-all',
                      isInactive
                        ? 'bg-red-950/30 border-red-500/30 text-red-200'
                        : 'bg-amber-950/30 border-amber-500/30 text-amber-200',
                    )}
                  >
                    <div className="flex items-start gap-2.5 min-w-0">
                      <AlertTriangle
                        className={cn(
                          'w-4 h-4 mt-0.5 flex-shrink-0',
                          isInactive ? 'text-red-400' : 'text-amber-400',
                        )}
                      />
                      <div>
                        <span className="font-semibold uppercase tracking-wider text-[10px] block mb-0.5">
                          {isInactive ? 'Listing Taken Down or Expired' : 'Listing Updates Detected'}
                        </span>
                        <p className="opacity-90 leading-relaxed break-words">
                          {match.change_alert ||
                            'This position appears to have been removed or closed on the source board.'}
                        </p>
                        {match.change_alert_at && (
                          <span className="text-[10px] opacity-70 block mt-1">
                            Detected {formatDate(match.change_alert_at)}
                          </span>
                        )}
                      </div>
                    </div>
                    {match.change_alert && (
                      <button
                        onClick={() => dismissMutation.mutate(match.id)}
                        disabled={dismissMutation.isPending}
                        className="flex-shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded bg-nexus-surface-2 hover:bg-nexus-surface text-nexus-text text-[11px] border border-nexus-border transition-colors disabled:opacity-50"
                        title="Acknowledge and dismiss this alert"
                      >
                        <Check size={12} />
                        <span>Dismiss</span>
                      </button>
                    )}
                  </div>
                )}

                {match.justification && (
                  <p className="text-sm text-nexus-text-dim italic mt-3 pl-20">
                    &ldquo;{match.justification}&rdquo;
                  </p>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="nexus-card text-center py-12">
          <Bookmark className="w-12 h-12 text-nexus-text-dim mx-auto mb-4" />
          <h3 className="text-white font-medium mb-1">No saved listings found</h3>
          <p className="text-nexus-text-muted text-sm">
            {filterMode === 'alerts'
              ? 'None of your saved listings currently have change or takedown alerts.'
              : 'Save matches from the Explore Matches page to build your shortlist.'}
          </p>
        </div>
      )}

      {/* Past Briefings Section */}
      <div className="space-y-4 pt-6 border-t border-nexus-border">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Video className="w-5 h-5 text-nexus-accent" />
              Past Career Briefings
            </h2>
            <p className="text-nexus-text-muted text-sm mt-0.5">
              Audio and video briefings generated from your top matches
            </p>
          </div>
          <Link
            href="/briefings"
            className="nexus-btn-secondary text-xs flex items-center gap-1.5"
          >
            <Sparkles size={14} className="text-nexus-accent" />
            Generate New Briefing
          </Link>
        </div>

        {briefings && briefings.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {briefings.slice(0, 4).map((b) => (
              <div key={b.id} className="nexus-card space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-nexus-text-dim">
                    {formatDate(b.created_at)}
                  </span>
                  <span
                    className={cn(
                      'px-2 py-0.5 text-xs rounded-full font-medium',
                      b.status === 'done'
                        ? 'bg-nexus-success/15 text-nexus-success'
                        : b.status === 'failed'
                        ? 'bg-nexus-danger/15 text-nexus-danger'
                        : 'bg-nexus-accent/15 text-nexus-accent animate-pulse-slow',
                    )}
                  >
                    {b.status === 'done' ? 'Ready' : b.status}
                  </span>
                </div>

                {b.script && (
                  <p className="text-xs text-nexus-text-muted line-clamp-2 italic">
                    &ldquo;{b.script}&rdquo;
                  </p>
                )}

                {b.media_url && (
                  <div className="pt-2">
                    {b.media_url.endsWith('.mp3') ? (
                      <audio
                        controls
                        className="w-full h-8"
                        preload="none"
                        src={
                          b.media_url.startsWith('http')
                            ? b.media_url
                            : `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${b.media_url}`
                        }
                      />
                    ) : (
                      <Link
                        href="/briefings"
                        className="nexus-btn-ghost w-full justify-center text-xs flex items-center gap-1.5"
                      >
                        <Play size={14} className="text-nexus-accent" /> Play Avatar Video
                      </Link>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="nexus-card text-center py-6">
            <p className="text-xs text-nexus-text-dim">No briefings generated yet.</p>
          </div>
        )}
      </div>
    </div>
  );
}
