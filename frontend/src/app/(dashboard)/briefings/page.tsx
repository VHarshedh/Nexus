'use client';

import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { BriefingJobResponse, BriefingCreateResponse } from '@/types/api';
import { cn, formatDate } from '@/lib/utils';
import { BriefingStatusStepper as StatusStepper } from '@/components/briefing-status-stepper';
import toast from 'react-hot-toast';
import {
  Video,
  Loader2,
  Clock,
  PenTool,
  AudioWaveform,
  CheckCircle2,
  XCircle,
  Play,
  ChevronDown,
  ChevronUp,
  Sparkles,
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Status Step Indicator
// ---------------------------------------------------------------------------
const STEPS = [
  { key: 'queued', label: 'Queued', icon: Clock },
  { key: 'generating_script', label: 'Generating Script', icon: PenTool },
  { key: 'synthesizing_media', label: 'Synthesizing Avatar Video', icon: AudioWaveform },
  { key: 'done', label: 'Ready', icon: CheckCircle2 },
];

// Kept locally for now to avoid a visual behavior change while consumers use
// the extracted component. It is not part of the route's runtime tree.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function LegacyStatusStepper({ status }: { status: string }) {
  let activeIdx = 0;
  if (status === 'queued') activeIdx = 0;
  else if (status === 'generating_script') activeIdx = 1;
  else if (status === 'synthesizing_media') activeIdx = 2;
  else if (status === 'done') activeIdx = STEPS.length; // past all steps
  else if (status === 'failed') activeIdx = -1;

  if (status === 'failed') {
    return (
      <div className="flex items-center gap-2 text-nexus-danger">
        <XCircle className="w-5 h-5" />
        <span className="font-medium">Generation Failed</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {STEPS.map((step, i) => {
        const isDone = i < activeIdx || status === 'done';
        const isActive = i === activeIdx && status !== 'done';

        return (
          <React.Fragment key={step.key}>
            <div className="flex items-center gap-1.5">
              <div
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center transition-all',
                  isDone
                    ? 'bg-nexus-success/20 text-nexus-success'
                    : isActive
                      ? 'bg-nexus-accent/20 text-nexus-accent animate-pulse-slow'
                      : 'bg-nexus-surface-2 text-nexus-text-dim',
                )}
              >
                <step.icon size={16} />
              </div>
              <span
                className={cn(
                  'text-xs font-medium hidden sm:inline',
                  isDone ? 'text-nexus-success' : isActive ? 'text-nexus-accent' : 'text-nexus-text-dim',
                )}
              >
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={cn(
                  'flex-1 h-0.5 min-w-[20px] rounded-full',
                  isDone ? 'bg-nexus-success/40' : 'bg-nexus-border',
                )}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Media Player
// ---------------------------------------------------------------------------
function MediaPlayer({ mediaUrl, script }: { mediaUrl: string; script: string | null }) {
  const [showScript, setShowScript] = useState(false);
  const fullUrl = `${API_BASE}${mediaUrl}`;
  const isVideo = mediaUrl.includes('video') || mediaUrl.endsWith('.mp4') || mediaUrl.endsWith('.webm');

  return (
    <div className="space-y-4">
      <div className="rounded-xl overflow-hidden bg-black">
        {isVideo ? (
          <video controls className="w-full max-h-[400px]" preload="metadata">
            <source src={fullUrl} />
            Your browser does not support the video element.
          </video>
        ) : (
          <div className="p-6">
            <audio controls className="w-full" preload="metadata">
              <source src={fullUrl} />
              Your browser does not support the audio element.
            </audio>
          </div>
        )}
      </div>

      {script && (
        <div className="nexus-card">
          <button
            onClick={() => setShowScript(!showScript)}
            className="flex items-center justify-between w-full text-left"
          >
            <span className="text-sm font-medium text-nexus-text-muted">Briefing Script</span>
            {showScript ? (
              <ChevronUp size={16} className="text-nexus-text-dim" />
            ) : (
              <ChevronDown size={16} className="text-nexus-text-dim" />
            )}
          </button>
          {showScript && (
            <p className="text-sm text-nexus-text-muted leading-relaxed mt-3 whitespace-pre-wrap">
              {script}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Briefing Card (archive)
// ---------------------------------------------------------------------------
function BriefingCard({ briefing }: { briefing: BriefingJobResponse }) {
  const [expanded, setExpanded] = useState(false);

  const statusColor: Record<string, string> = {
    queued: 'bg-nexus-text-dim/20 text-nexus-text-dim',
    generating_script: 'bg-nexus-warning/20 text-nexus-warning',
    synthesizing_media: 'bg-nexus-warning/20 text-nexus-warning',
    done: 'bg-nexus-success/20 text-nexus-success',
    failed: 'bg-nexus-danger/20 text-nexus-danger',
  };

  return (
    <div className="nexus-card-hover cursor-pointer" onClick={() => setExpanded(!expanded)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span
            className={cn(
              'px-2 py-0.5 rounded-md text-xs font-medium capitalize',
              statusColor[briefing.status] || statusColor.queued,
            )}
          >
            {briefing.status}
          </span>
          <span className="text-sm text-nexus-text-muted">{formatDate(briefing.created_at)}</span>
          {briefing.completed_at && (
            <span className="text-xs text-nexus-text-dim">
              Completed {formatDate(briefing.completed_at)}
            </span>
          )}
        </div>
        {expanded ? <ChevronUp size={16} className="text-nexus-text-dim" /> : <ChevronDown size={16} className="text-nexus-text-dim" />}
      </div>

      {expanded && (
        <div className="mt-4 animate-slide-up" onClick={(e) => e.stopPropagation()}>
          {briefing.status === 'failed' && briefing.error_message && (
            <p className="text-sm text-nexus-danger mb-3">{briefing.error_message}</p>
          )}
          {briefing.status === 'done' && briefing.media_url && (
            <MediaPlayer mediaUrl={briefing.media_url} script={briefing.script} />
          )}
          {briefing.status === 'done' && !briefing.media_url && briefing.script && (
            <p className="text-sm text-nexus-text-muted whitespace-pre-wrap">{briefing.script}</p>
          )}
          {(briefing.status === 'queued' || briefing.status === 'generating_script' || briefing.status === 'synthesizing_media') && (
            <StatusStepper status={briefing.status} />
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------
export default function BriefingsPage() {
  const queryClient = useQueryClient();
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  // Fetch all briefings
  const { data: briefings, isLoading: listLoading } = useQuery<BriefingJobResponse[]>({
    queryKey: ['briefings'],
    queryFn: async () => (await api.get('/api/briefings/')).data,
  });

  // Poll active job
  const { data: activeJob } = useQuery<BriefingJobResponse>({
    queryKey: ['briefing', activeJobId],
    queryFn: async () => (await api.get(`/api/briefings/${activeJobId}`)).data,
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'done' || status === 'failed') return false;
      return 3000;
    },
  });

  // Stop polling and refresh list when done/failed
  useEffect(() => {
    if (activeJob && (activeJob.status === 'done' || activeJob.status === 'failed')) {
      if (activeJob.status === 'done') toast.success('Briefing ready!');
      if (activeJob.status === 'failed') toast.error('Briefing generation failed.');
      queryClient.invalidateQueries({ queryKey: ['briefings'] });
    }
  }, [activeJob, queryClient]);

  const generateMutation = useMutation<BriefingCreateResponse>({
    mutationFn: async () => (await api.post('/api/briefings/generate')).data,
    onSuccess: (data) => {
      setActiveJobId(data.job_id);
      toast.success('Briefing queued!');
      queryClient.invalidateQueries({ queryKey: ['briefings'] });
    },
    onError: () => toast.error('Failed to start briefing generation.'),
  });

  const isGenerating =
    generateMutation.isPending ||
    (activeJob && activeJob.status !== 'done' && activeJob.status !== 'failed');

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Video className="w-7 h-7 text-nexus-accent" />
            Video Briefings
          </h1>
          <p className="text-nexus-text-muted mt-1">
            Generate AI-powered career briefing summaries
          </p>
        </div>
        <button
          onClick={() => generateMutation.mutate()}
          disabled={!!isGenerating}
          className="nexus-btn-primary"
        >
          {isGenerating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Generating…
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              Generate My Briefing
            </>
          )}
        </button>
      </div>

      {/* Active Job Status */}
      {activeJob && activeJob.status !== 'done' && activeJob.status !== 'failed' && (
        <div className="nexus-card">
          <h2 className="text-sm font-medium text-nexus-text-muted mb-4">Generation Progress</h2>
          <StatusStepper status={activeJob.status} />
        </div>
      )}

      {/* Active Job Result */}
      {activeJob && activeJob.status === 'done' && activeJob.media_url && (
        <div className="nexus-card">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-nexus-accent" />
            Latest Briefing
          </h2>
          <MediaPlayer mediaUrl={activeJob.media_url} script={activeJob.script} />
        </div>
      )}

      {/* Active Job Error */}
      {activeJob && activeJob.status === 'failed' && (
        <div className="nexus-card border-nexus-danger/30">
          <div className="flex items-center gap-2 text-nexus-danger mb-2">
            <XCircle size={18} />
            <span className="font-medium">Generation Failed</span>
          </div>
          {activeJob.error_message && (
            <p className="text-sm text-nexus-text-muted">{activeJob.error_message}</p>
          )}
        </div>
      )}

      {/* Archive */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Past Briefings</h2>

        {listLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="nexus-card animate-pulse">
                <div className="flex gap-3">
                  <div className="h-5 bg-nexus-surface-2 rounded w-20" />
                  <div className="h-5 bg-nexus-surface-2 rounded w-32" />
                </div>
              </div>
            ))}
          </div>
        ) : briefings && briefings.length > 0 ? (
          <div className="space-y-3">
            {briefings.map((b) => (
              <BriefingCard key={b.id} briefing={b} />
            ))}
          </div>
        ) : (
          <div className="nexus-card text-center py-12">
            <Video className="w-12 h-12 text-nexus-text-dim mx-auto mb-4" />
            <h3 className="text-white font-medium mb-1">No briefings yet</h3>
            <p className="text-nexus-text-muted text-sm">
              Click &ldquo;Generate My Briefing&rdquo; to create your first career summary.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
