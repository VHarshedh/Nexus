'use client';

import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import type { ResumeResponse } from '@/types/api';
import { cn, formatDate } from '@/lib/utils';
import { MAX_RESUME_FILE_BYTES, validateResumeFile } from '@/lib/resume-file';
import toast from 'react-hot-toast';
import {
  FileText,
  Upload,
  User,
  ChevronDown,
  ChevronUp,
  Hash,
  Calendar,
  Mail,
} from 'lucide-react';

export default function ResumePage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: resumes, isLoading } = useQuery<ResumeResponse[]>({
    queryKey: ['resumes'],
    queryFn: async () => (await api.get('/api/resume/')).data,
  });

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;
      const validationError = validateResumeFile(file);
      if (validationError) {
        toast.error(validationError);
        return;
      }

      setUploading(true);
      setUploadProgress(0);
      const formData = new FormData();
      formData.append('file', file);

      try {
        await api.post('/api/resume/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (e) => {
            if (e.total) setUploadProgress(Math.round((e.loaded / e.total) * 100));
          },
        });
        toast.success('Resume uploaded successfully!');
        queryClient.invalidateQueries({ queryKey: ['resumes'] });
      } catch {
        toast.error('Failed to upload resume.');
      } finally {
        setUploading(false);
        setUploadProgress(0);
      }
    },
    [queryClient],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    maxSize: MAX_RESUME_FILE_BYTES,
    disabled: uploading,
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <FileText className="w-7 h-7 text-nexus-accent" />
          Resume & Profile
        </h1>
        <p className="text-nexus-text-muted mt-1">Manage your profile and uploaded resumes</p>
      </div>

      {/* Profile Card */}
      <div className="nexus-card">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <User className="w-5 h-5 text-nexus-accent" />
          Account Info
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex items-center gap-3 p-3 bg-nexus-surface-2 rounded-lg">
            <Mail className="w-4 h-4 text-nexus-text-dim flex-shrink-0" />
            <div>
              <p className="text-xs text-nexus-text-dim">Email</p>
              <p className="text-sm text-nexus-text">{user?.email || '—'}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 bg-nexus-surface-2 rounded-lg">
            <Hash className="w-4 h-4 text-nexus-text-dim flex-shrink-0" />
            <div>
              <p className="text-xs text-nexus-text-dim">User ID</p>
              <p className="text-sm text-nexus-text font-mono text-xs truncate">{user?.userId || '—'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Upload Zone */}
      <div className="nexus-card">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Upload className="w-5 h-5 text-nexus-accent" />
          Upload Resume
        </h2>

        <div
          {...getRootProps()}
          className={cn(
            'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all duration-200',
            isDragActive
              ? 'border-nexus-accent bg-nexus-accent/10'
              : 'border-nexus-border hover:border-nexus-accent/50 hover:bg-nexus-surface-2',
            uploading && 'opacity-50 cursor-not-allowed',
          )}
        >
          <input {...getInputProps()} />
          <Upload className="w-10 h-10 text-nexus-text-dim mx-auto mb-3" />
          {isDragActive ? (
            <p className="text-nexus-accent font-medium">Drop your PDF here…</p>
          ) : (
            <>
              <p className="text-nexus-text-muted">Drag & drop your resume PDF, or click to browse</p>
              <p className="text-nexus-text-dim text-sm mt-1">PDF files only, up to 10 MB</p>
            </>
          )}
        </div>

        {uploading && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-sm text-nexus-text-muted mb-1">
              <span>Uploading…</span>
              <span>{uploadProgress}%</span>
            </div>
            <div className="h-2 bg-nexus-surface-2 rounded-full overflow-hidden">
              <div
                className="h-full bg-nexus-accent rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Resumes List */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Your Resumes</h2>

        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="nexus-card animate-pulse">
                <div className="h-5 bg-nexus-surface-2 rounded w-1/3 mb-2" />
                <div className="h-4 bg-nexus-surface-2 rounded w-full" />
              </div>
            ))}
          </div>
        ) : resumes && resumes.length > 0 ? (
          <div className="space-y-3">
            {resumes.map((resume) => {
              const isExpanded = expandedId === resume.id;
              return (
                <div key={resume.id} className="nexus-card-hover">
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : resume.id)}
                    className="w-full text-left"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <FileText className="w-5 h-5 text-nexus-accent flex-shrink-0" />
                        <div>
                          <div className="flex items-center gap-2">
                            <Calendar size={12} className="text-nexus-text-dim" />
                            <span className="text-sm text-nexus-text-muted">
                              {formatDate(resume.uploaded_at)}
                            </span>
                          </div>
                          <p className="text-xs text-nexus-text-dim font-mono mt-0.5">
                            ID: {resume.id.slice(0, 8)}…
                          </p>
                        </div>
                      </div>
                      {isExpanded ? (
                        <ChevronUp size={16} className="text-nexus-text-dim" />
                      ) : (
                        <ChevronDown size={16} className="text-nexus-text-dim" />
                      )}
                    </div>

                    {!isExpanded && (
                      <p className="text-sm text-nexus-text-dim mt-2 line-clamp-2">
                        {resume.raw_text.slice(0, 300)}…
                      </p>
                    )}
                  </button>

                  {isExpanded && (
                    <div className="mt-4 p-4 bg-nexus-surface-2 rounded-lg max-h-[400px] overflow-y-auto animate-slide-up">
                      <p className="text-sm text-nexus-text-muted whitespace-pre-wrap leading-relaxed">
                        {resume.raw_text}
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="nexus-card text-center py-12">
            <FileText className="w-12 h-12 text-nexus-text-dim mx-auto mb-4" />
            <h3 className="text-white font-medium mb-1">No resumes uploaded</h3>
            <p className="text-nexus-text-muted text-sm">
              Upload your first resume to start matching with job listings.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
