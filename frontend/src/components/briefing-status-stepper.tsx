'use client';

import React from 'react';
import { AudioWaveform, CheckCircle2, Clock, PenTool, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

const STEPS = [
  { key: 'queued', label: 'Queued', icon: Clock },
  { key: 'generating_script', label: 'Generating Script', icon: PenTool },
  { key: 'synthesizing_media', label: 'Synthesizing Avatar Video', icon: AudioWaveform },
  { key: 'done', label: 'Ready', icon: CheckCircle2 },
];

export function BriefingStatusStepper({ status }: { status: string }) {
  const activeIdx = status === 'queued' ? 0
    : status === 'generating_script' ? 1
      : status === 'synthesizing_media' ? 2
        : status === 'done' ? STEPS.length : -1;

  if (status === 'failed') {
    return <div className="flex items-center gap-2 text-nexus-danger"><XCircle className="w-5 h-5" /><span className="font-medium">Generation Failed</span></div>;
  }

  return <div className="flex items-center gap-2">
    {STEPS.map((step, index) => {
      const isDone = index < activeIdx || status === 'done';
      const isActive = index === activeIdx && status !== 'done';
      return <React.Fragment key={step.key}>
        <div className="flex items-center gap-1.5">
          <div className={cn('w-8 h-8 rounded-full flex items-center justify-center transition-all', isDone ? 'bg-nexus-success/20 text-nexus-success' : isActive ? 'bg-nexus-accent/20 text-nexus-accent animate-pulse-slow' : 'bg-nexus-surface-2 text-nexus-text-dim')}><step.icon size={16} /></div>
          <span className={cn('text-xs font-medium hidden sm:inline', isDone ? 'text-nexus-success' : isActive ? 'text-nexus-accent' : 'text-nexus-text-dim')}>{step.label}</span>
        </div>
        {index < STEPS.length - 1 && <div className={cn('flex-1 h-0.5 min-w-[20px] rounded-full', isDone ? 'bg-nexus-success/40' : 'bg-nexus-border')} />}
      </React.Fragment>;
    })}
  </div>;
}
