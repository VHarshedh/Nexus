import React, { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MatchCard } from '@/components/match-card';
import { BriefingStatusStepper } from '@/components/briefing-status-stepper';
import type { MatchResponse } from '@/types/api';

vi.mock('@/lib/api', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));

const match: MatchResponse = {
  id: 'match-1', listing_id: 'listing-1', match_score: 0.9, justification: null,
  saved: false, status: 'pending', created_at: '2026-01-01T00:00:00Z',
  listing: { id: 'listing-1', title: 'Engineer', company: 'Nexus', location: null, remote_ok: true, stipend: null, required_skills: [], experience_level: null, deadline: null, source_url: 'https://example.test' },
};

function ToggleHarness() {
  const [current, setCurrent] = useState(match);
  return <MatchCard match={current} onToggleSave={() => setCurrent((value) => ({ ...value, saved: !value.saved }))} />;
}

describe('dashboard interactions', () => {
  it('updates shortlist button state after a toggle', () => {
    render(<ToggleHarness />);
    fireEvent.click(screen.getByTitle('Save to shortlist'));
    expect(screen.getByTitle('Remove from shortlist')).toBeInTheDocument();
  });

  it.each([
    ['queued', 'Queued'],
    ['generating_script', 'Generating Script'],
    ['synthesizing_media', 'Synthesizing Avatar Video'],
    ['done', 'Ready'],
  ])('renders briefing lifecycle stage %s', (status, label) => {
    render(<BriefingStatusStepper status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
