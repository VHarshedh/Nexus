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

const EXCHANGE_RATES_TO_USD: Record<string, number> = {
  usd: 1.0,
  '$': 1.0,
  inr: 1.0 / 85.0,
  '₹': 1.0 / 85.0,
  rs: 1.0 / 85.0,
  rupee: 1.0 / 85.0,
  rupees: 1.0 / 85.0,
  eur: 1.08,
  '€': 1.08,
  gbp: 1.28,
  '£': 1.28,
  cad: 0.74,
  'c$': 0.74,
  aud: 0.66,
  'a$': 0.66,
  chf: 1.12,
  jpy: 1.0 / 150.0,
  '¥': 1.0 / 150.0,
};

export function parseStipendToUsd(text: string | null | undefined): number | null {
  if (!text) return null;
  const raw = text.trim();
  if (!raw || /^(not specified|unlisted|competitive|undisclosed)$/i.test(raw)) {
    return null;
  }

  const cleaned = raw.toLowerCase().replace(/,/g, '');

  // 1. Determine currency rate (default to USD: 1.0)
  let rate = 1.0;
  if (['inr', '₹', 'rs', 'rupee', 'rupees', 'lpa', 'lakh'].some((sym) => cleaned.includes(sym))) {
    rate = EXCHANGE_RATES_TO_USD.inr;
  } else if (['eur', '€'].some((sym) => cleaned.includes(sym))) {
    rate = EXCHANGE_RATES_TO_USD.eur;
  } else if (['gbp', '£'].some((sym) => cleaned.includes(sym))) {
    rate = EXCHANGE_RATES_TO_USD.gbp;
  } else if (['cad', 'c$'].some((sym) => cleaned.includes(sym))) {
    rate = EXCHANGE_RATES_TO_USD.cad;
  } else if (['aud', 'a$'].some((sym) => cleaned.includes(sym))) {
    rate = EXCHANGE_RATES_TO_USD.aud;
  } else if (cleaned.includes('chf')) {
    rate = EXCHANGE_RATES_TO_USD.chf;
  } else if (['jpy', '¥', 'yen'].some((sym) => cleaned.includes(sym))) {
    rate = EXCHANGE_RATES_TO_USD.jpy;
  } else if (cleaned.includes('$') || cleaned.includes('usd')) {
    rate = 1.0;
  }

  // 2. Check for Indian LPA / Lakh (e.g., "12 LPA", "8.5 Lakh")
  const lpaMatches = cleaned.match(/(\d+(?:\.\d+)?)\s*(?:lpa|lakh|lac)/g);
  if (lpaMatches) {
    const lpaVals = lpaMatches
      .map((m) => {
        const num = parseFloat(m.replace(/[^0-9.]/g, ''));
        return num * 100000 * EXCHANGE_RATES_TO_USD.inr;
      })
      .filter((v) => !isNaN(v));
    if (lpaVals.length > 0) {
      return Math.max(...lpaVals);
    }
  }

  // 3. Match numeric amounts with optional 'k' or 'm' multiplier
  const regex = /(\d+(?:\.\d+)?)\s*([km])?/gi;
  const amounts: number[] = [];
  const hasKInContext = cleaned.includes('k');
  let match: RegExpExecArray | null;

  while ((match = regex.exec(cleaned)) !== null) {
    const num = parseFloat(match[1]);
    if (isNaN(num)) continue;
    const suffix = (match[2] || '').toLowerCase();
    let val = num;
    if (suffix === 'k') {
      val *= 1000;
    } else if (suffix === 'm') {
      val *= 1000000;
    } else if (val < 1000 && hasKInContext && !cleaned.includes('/hr') && !cleaned.includes('/hour')) {
      val *= 1000;
    }

    amounts.push(val * rate);
  }

  return amounts.length > 0 ? Math.max(...amounts) : null;
}

export function matchesMinStipend(
  listingStipend: string | null | undefined,
  filterInput: string | null | undefined
): boolean {
  if (!filterInput || !filterInput.trim()) return true;
  const query = filterInput.trim();

  // Strip comparison prefixes e.g. >, >=, min, etc.
  const cleanedQuery = query.replace(/^[>\s=min]+/i, '').replace(/\+$/, '').trim();
  const minUsd = parseStipendToUsd(cleanedQuery);

  if (minUsd !== null) {
    const listingUsd = parseStipendToUsd(listingStipend);
    if (listingUsd !== null) {
      return listingUsd >= minUsd;
    }
    return false;
  }

  // Fallback: substring matching if query had no numeric amount
  return (listingStipend || '').toLowerCase().includes(query.toLowerCase());
}
