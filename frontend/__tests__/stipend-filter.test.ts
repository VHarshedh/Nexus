import { describe, it, expect } from 'vitest';
import { parseStipendToUsd, matchesMinStipend } from '@/lib/utils';

describe('Currency-Aware Stipend Filtering (Greater than searched)', () => {
  it('correctly parses USD, Rupees, and other currencies to USD equivalent', () => {
    expect(parseStipendToUsd('$800')).toBeCloseTo(800, 1);
    expect(parseStipendToUsd('800$')).toBeCloseTo(800, 1);
    expect(parseStipendToUsd('$150,000')).toBeCloseTo(150000, 1);
    expect(parseStipendToUsd('80000 rupees')).toBeCloseTo(80000 / 85.0, 1);
    expect(parseStipendToUsd('₹80,000')).toBeCloseTo(80000 / 85.0, 1);
    expect(parseStipendToUsd('12 LPA')).toBeCloseTo(1200000 / 85.0, 1);
  });

  it('matches listing in Rupees when user searches > 800$ (since 80000 INR = ~$941 USD > $800)', () => {
    // 80,000 INR (~$941) >= $800 USD -> TRUE
    expect(matchesMinStipend('80000 rupees', '> 800$')).toBe(true);
    expect(matchesMinStipend('80000 rupees', '800$')).toBe(true);
    expect(matchesMinStipend('80000 rupees', '800')).toBe(true);

    // 50,000 INR (~$588) < $800 USD -> FALSE
    expect(matchesMinStipend('50000 rupees', '> 800$')).toBe(false);
  });

  it('matches listing in USD when user searches in Rupees', () => {
    // $1000 USD (~85,000 INR) >= 80,000 rupees -> TRUE
    expect(matchesMinStipend('$1,000', '80000 rupees')).toBe(true);
    // $800 USD (~68,000 INR) < 80,000 rupees -> FALSE
    expect(matchesMinStipend('$800', '80000 rupees')).toBe(false);
  });

  it('handles standard job ranges and k notation', () => {
    expect(matchesMinStipend('$150k - $200k', '100k')).toBe(true);
    expect(matchesMinStipend('$50k - $80k', '100k')).toBe(false);
  });

  it('falls back to text search if no numbers are provided', () => {
    expect(matchesMinStipend('Competitive salary + equity', 'equity')).toBe(true);
    expect(matchesMinStipend('Competitive salary + equity', 'cash only')).toBe(false);
  });
});
