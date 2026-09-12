import { describe, expect, it } from 'vitest';
import { MAX_RESUME_FILE_BYTES, validateResumeFile } from '@/lib/resume-file';

describe('resume drag-and-drop validation', () => {
  it('accepts a PDF below the size limit', () => {
    expect(validateResumeFile(new File(['pdf'], 'resume.pdf', { type: 'application/pdf' }))).toBeNull();
  });

  it('rejects non-PDF files and oversized PDFs before upload', () => {
    expect(validateResumeFile(new File(['text'], 'resume.txt', { type: 'text/plain' }))).toBe('Only PDF files are accepted.');
    expect(validateResumeFile(new File([new Uint8Array(MAX_RESUME_FILE_BYTES + 1)], 'resume.pdf', { type: 'application/pdf' }))).toBe('PDF must be 10 MB or smaller.');
  });
});
