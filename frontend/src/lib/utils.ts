import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

export function formatMatchScore(score: number): { percent: string; color: string } {
  const pct = Math.round(score * 100);
  let color = 'bg-nexus-danger';
  if (pct >= 80) color = 'bg-nexus-success';
  else if (pct >= 60) color = 'bg-nexus-accent';
  else if (pct >= 40) color = 'bg-nexus-warning';
  return { percent: `${pct}%`, color };
}
