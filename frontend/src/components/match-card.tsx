'use client';

import React from 'react';
import { Bookmark, BookmarkCheck, Calendar, DollarSign, ExternalLink, MapPin, Wifi } from 'lucide-react';
import type { MatchResponse } from '@/types/api';
import { cn, formatDate, formatMatchScore } from '@/lib/utils';

export function MatchCard({ match, onToggleSave }: { match: MatchResponse; onToggleSave: (id: string) => void }) {
  const listing = match.listing;
  if (!listing) return null;
  const { percent, color } = formatMatchScore(match.match_score);
  return <div className="nexus-card-hover animate-fade-in">
    <div className="flex items-start justify-between gap-2 mb-3"><div className="min-w-0"><h3 className="font-semibold text-white truncate">{listing.title || 'Untitled Position'}</h3><p className="text-nexus-text-muted text-sm">{listing.company || 'Unknown Company'}</p></div><div className="flex items-center gap-1 flex-shrink-0"><button onClick={() => onToggleSave(match.id)} className={cn('p-1.5 rounded-lg transition-all', match.saved ? 'text-nexus-accent bg-nexus-accent/15' : 'text-nexus-text-dim hover:text-nexus-accent hover:bg-nexus-surface-2')} title={match.saved ? 'Remove from shortlist' : 'Save to shortlist'}>{match.saved ? <BookmarkCheck size={18} /> : <Bookmark size={18} />}</button><a href={listing.source_url} target="_blank" rel="noopener noreferrer" className="p-1.5 rounded-lg text-nexus-text-dim hover:text-nexus-text hover:bg-nexus-surface-2 transition-all" title="View original listing"><ExternalLink size={18} /></a></div></div>
    <div className="flex flex-wrap gap-2 mb-3">{listing.location && <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-nexus-surface-2 text-nexus-text-muted text-xs rounded-md"><MapPin size={12} />{listing.location}</span>}{listing.remote_ok && <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-500/15 text-emerald-400 text-xs rounded-md"><Wifi size={12} />Remote</span>}{listing.stipend && <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-nexus-surface-2 text-nexus-text-muted text-xs rounded-md"><DollarSign size={12} />{listing.stipend}</span>}{listing.deadline && <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-nexus-surface-2 text-nexus-text-muted text-xs rounded-md"><Calendar size={12} />{formatDate(listing.deadline)}</span>}</div>
    <div className="mb-3"><div className="flex items-center justify-between text-sm mb-1"><span className="text-nexus-text-muted">Match Score</span><span className="font-semibold text-white">{percent}</span></div><div className="h-2 bg-nexus-surface-2 rounded-full overflow-hidden"><div className={cn('h-full rounded-full transition-all duration-500', color)} style={{ width: percent }} /></div></div>
    {match.justification && <p className="text-sm text-nexus-text-dim italic leading-relaxed">&ldquo;{match.justification}&rdquo;</p>}
  </div>;
}
