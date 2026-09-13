'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import ProtectedRoute from '@/components/protected-route';
import {
  Brain,
  LayoutDashboard,
  Bookmark,
  FileText,
  MessageSquareText,
  Video,
  Coins,
  LogOut,
  ChevronLeft,
  ChevronRight,
  UserCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Explore Matches', icon: LayoutDashboard },
  { href: '/shortlist', label: 'My Shortlist', icon: Bookmark },
  { href: '/resume', label: 'My Resume', icon: FileText },
  { href: '/agent', label: 'AI Career Agent', icon: MessageSquareText },
  { href: '/briefings', label: 'Video Briefings', icon: Video },
  { href: '/costs', label: 'Cost Intelligence', icon: Coins },
  { href: '/profile', label: 'Account Settings', icon: UserCircle },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <ProtectedRoute>
      <div className="flex h-screen bg-nexus-bg">
        {/* Sidebar */}
        <aside
          className={cn(
            'flex flex-col border-r border-nexus-border bg-nexus-surface transition-all duration-300',
            collapsed ? 'w-[68px]' : 'w-64',
          )}
        >
          {/* Logo */}
          <div className="flex items-center gap-3 px-4 h-16 border-b border-nexus-border">
            <div className="flex-shrink-0 w-9 h-9 bg-nexus-accent/20 rounded-lg flex items-center justify-center">
              <Brain className="w-5 h-5 text-nexus-accent" />
            </div>
            {!collapsed && (
              <span className="text-lg font-bold text-white tracking-tight">NEXUS</span>
            )}
          </div>

          {/* Navigation */}
          <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 group',
                    isActive
                      ? 'bg-nexus-accent/15 text-nexus-accent'
                      : 'text-nexus-text-muted hover:text-nexus-text hover:bg-nexus-surface-2',
                  )}
                  title={collapsed ? item.label : undefined}
                >
                  <item.icon
                    className={cn(
                      'w-5 h-5 flex-shrink-0',
                      isActive
                        ? 'text-nexus-accent'
                        : 'text-nexus-text-dim group-hover:text-nexus-text-muted',
                    )}
                  />
                  {!collapsed && <span className="text-sm font-medium truncate">{item.label}</span>}
                </Link>
              );
            })}
          </nav>

          {/* Bottom controls */}
          <div className="border-t border-nexus-border p-2 space-y-1">
            <button onClick={() => setCollapsed(!collapsed)} className="nexus-btn-ghost w-full justify-center">
              {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
              {!collapsed && <span className="text-sm">Collapse</span>}
            </button>

            <button onClick={logout} className="nexus-btn-ghost w-full" title={collapsed ? 'Sign Out' : undefined}>
              <LogOut size={18} className="flex-shrink-0" />
              {!collapsed && (
                <div className="flex flex-col items-start min-w-0">
                  <span className="text-xs text-nexus-text-muted truncate w-full">{user?.email}</span>
                  <span className="text-xs text-nexus-text-dim">Sign Out</span>
                </div>
              )}
            </button>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-7xl mx-auto px-6 py-8">{children}</div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
