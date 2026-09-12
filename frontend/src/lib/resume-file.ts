export const MAX_RESUME_FILE_BYTES = 10 * 1024 * 1024;

/** Returns a user-facing validation error, or null when the PDF is acceptable. */
export function validateResumeFile(file: File): string | null {
  const hasPdfExtension = file.name.toLowerCase().endsWith('.pdf');
  const hasPdfMimeType = !file.type || file.type === 'application/pdf';
  if (!hasPdfExtension || !hasPdfMimeType) return 'Only PDF files are accepted.';
  if (file.size > MAX_RESUME_FILE_BYTES) return 'PDF must be 10 MB or smaller.';
  return null;
}
