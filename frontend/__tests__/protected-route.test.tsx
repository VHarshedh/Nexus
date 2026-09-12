import React from 'react';
import { render, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ProtectedRoute from '@/components/protected-route';

const replace = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace }) }));
vi.mock('@/lib/auth-context', () => ({ useAuth: () => ({ user: null, isLoading: false }) }));

describe('ProtectedRoute', () => {
  it('redirects unauthenticated visitors to login', async () => {
    render(<ProtectedRoute><div>private content</div></ProtectedRoute>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/login'));
  });
});
