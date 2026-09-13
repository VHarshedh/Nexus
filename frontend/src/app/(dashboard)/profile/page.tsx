'use client';

import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { UserCircle, Settings, Key, AlertTriangle, Loader2, Trash2, LogOut } from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import type { UserProfileResponse } from '@/types/api';
import { cn } from '@/lib/utils';
import { useRouter } from 'next/navigation';

export default function ProfilePage() {
  const { user, logout, updateUser } = useAuth();
  const queryClient = useQueryClient();
  const router = useRouter();
  
  // Section tabs
  const [activeTab, setActiveTab] = useState<'preferences' | 'security' | 'delete'>('preferences');

  // Load Profile
  const { data: profile, isLoading } = useQuery<UserProfileResponse>({
    queryKey: ['profile'],
    queryFn: async () => (await api.get('/api/auth/me')).data,
  });

  // --- PREFERENCES STATE ---
  const [targetRoles, setTargetRoles] = useState<string>('');
  const [seniority, setSeniority] = useState<string>('');
  const [locationPref, setLocationPref] = useState<'remote' | 'hybrid' | 'onsite' | ''>('');
  const [country, setCountry] = useState('');
  const [state, setState] = useState('');
  const [city, setCity] = useState('');
  const [roleCategories, setRoleCategories] = useState<string[]>([]);
  const [minStipend, setMinStipend] = useState('');

  // Prefill preferences once loaded
  useEffect(() => {
    if (profile?.preferences) {
      setTargetRoles(profile.preferences.target_roles?.join(', ') || '');
      setSeniority(profile.preferences.seniority || '');
      setLocationPref((profile.preferences.location_preference as any) || '');
      
      const loc = profile.preferences.locations?.[0];
      setCountry(loc?.country || '');
      setState(loc?.state || '');
      setCity(loc?.city || '');
      
      setRoleCategories(profile.preferences.role_preference || []);
      setMinStipend(profile.preferences.min_stipend || '');
    }
  }, [profile]);

  const updatePreferencesMutation = useMutation({
    mutationFn: async () => {
      const locations = [];
      if (locationPref !== 'remote' && (country || state || city)) {
        locations.push({ country, state, city });
      }
      return api.patch('/api/auth/preferences', {
        preferences: {
          target_roles: targetRoles.split(',').map(s => s.trim()).filter(Boolean),
          seniority,
          location_preference: locationPref,
          locations,
          min_stipend: minStipend.trim() || null,
          role_preference: roleCategories,
        }
      });
    },
    onSuccess: () => {
      toast.success('Preferences updated successfully!');
      queryClient.invalidateQueries({ queryKey: ['profile'] });
      updateUser({ onboarded: true });
    },
    onError: () => {
      toast.error('Failed to update preferences.');
    }
  });

  // --- PASSWORD STATE ---
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');

  const changePasswordMutation = useMutation({
    mutationFn: async () => {
      if (newPassword !== confirmNewPassword) {
        throw new Error('Passwords do not match');
      }
      // Password complexity check
      const hasLetter = /[a-zA-Z]/.test(newPassword);
      const hasNumber = /[0-9]/.test(newPassword);
      const hasSymbol = /[^a-zA-Z0-9]/.test(newPassword);
      if (!(hasLetter && hasNumber && hasSymbol && newPassword.length >= 8)) {
        throw new Error('Password must be at least 8 characters and include letters, numbers, and symbols.');
      }

      return api.put('/api/auth/password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
    },
    onSuccess: () => {
      toast.success('Password changed successfully!');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmNewPassword('');
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || err.message || 'Failed to change password.');
    }
  });

  // --- DELETE ACCOUNT ---
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const deleteAccountMutation = useMutation({
    mutationFn: async () => api.delete('/api/auth/me'),
    onSuccess: () => {
      toast.success('Account deleted successfully.');
      logout();
      router.push('/login');
    },
    onError: () => {
      toast.error('Failed to delete account.');
    }
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-nexus-accent" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-8 animate-in fade-in duration-300">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <UserCircle className="w-7 h-7 text-nexus-accent" />
            Account Settings
          </h1>
          <p className="text-nexus-text-muted mt-1">
            Manage your profile, preferences, and security settings.
          </p>
        </div>
        <button
          onClick={() => {
            logout();
            router.push('/login');
          }}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-nexus-text-muted hover:text-white bg-nexus-surface-2 hover:bg-nexus-surface-3 border border-nexus-border transition-all w-fit"
        >
          <LogOut size={16} />
          Sign Out
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        
        {/* Sidebar Nav */}
        <div className="md:col-span-1 space-y-2">
          <button
            onClick={() => setActiveTab('preferences')}
            className={cn(
              'w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all',
              activeTab === 'preferences'
                ? 'bg-nexus-accent/20 text-nexus-accent border border-nexus-accent/30'
                : 'text-nexus-text-muted hover:text-white hover:bg-nexus-surface-2 border border-transparent'
            )}
          >
            <Settings size={18} /> Match Preferences
          </button>
          
          <button
            onClick={() => setActiveTab('security')}
            className={cn(
              'w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all',
              activeTab === 'security'
                ? 'bg-nexus-accent/20 text-nexus-accent border border-nexus-accent/30'
                : 'text-nexus-text-muted hover:text-white hover:bg-nexus-surface-2 border border-transparent'
            )}
          >
            <Key size={18} /> Password & Security
          </button>

          <button
            onClick={() => setActiveTab('delete')}
            className={cn(
              'w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all',
              activeTab === 'delete'
                ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                : 'text-nexus-text-muted hover:text-red-400 hover:bg-nexus-surface-2 border border-transparent'
            )}
          >
            <Trash2 size={18} /> Delete Account
          </button>

          <div className="pt-2 border-t border-nexus-border">
            <button
              onClick={() => {
                logout();
                router.push('/login');
              }}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-nexus-text-muted hover:text-white hover:bg-nexus-surface-2 border border-transparent transition-all"
            >
              <LogOut size={18} /> Sign Out
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="md:col-span-3">
          
          {/* PREFERENCES TAB */}
          {activeTab === 'preferences' && (
            <div className="nexus-card space-y-6 animate-in slide-in-from-right-4 fade-in duration-300">
              <h2 className="text-lg font-semibold text-white">Job Match Preferences</h2>
              <p className="text-sm text-nexus-text-muted pb-4 border-b border-nexus-border">
                Update the parameters we use to calculate your semantic matches.
              </p>

              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-nexus-text-muted mb-1.5">
                    Target Roles (comma separated)
                  </label>
                  <input
                    type="text"
                    value={targetRoles}
                    onChange={(e) => setTargetRoles(e.target.value)}
                    className="nexus-input w-full"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-nexus-text-muted mb-2">
                    Seniority Level
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {['Intern', 'Junior', 'Mid-Level', 'Senior'].map((lvl) => (
                      <button
                        key={lvl}
                        onClick={() => setSeniority(lvl)}
                        className={cn(
                          'py-2 px-3 rounded-lg text-sm transition-all border',
                          seniority === lvl 
                            ? 'bg-nexus-accent/20 border-nexus-accent text-white shadow-sm'
                            : 'bg-nexus-surface-2 border-nexus-border text-nexus-text-muted hover:text-white'
                        )}
                      >
                        {lvl}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-nexus-text-muted mb-2">
                    Location Preference
                  </label>
                  <div className="grid grid-cols-3 gap-3">
                    {['remote', 'hybrid', 'onsite'].map((pref) => (
                      <button
                        key={pref}
                        onClick={() => setLocationPref(pref as any)}
                        className={cn(
                          'py-2 px-3 rounded-lg text-sm transition-all border capitalize',
                          locationPref === pref 
                            ? 'bg-nexus-accent/20 border-nexus-accent text-white shadow-sm'
                            : 'bg-nexus-surface-2 border-nexus-border text-nexus-text-muted hover:text-white'
                        )}
                      >
                        {pref}
                      </button>
                    ))}
                  </div>
                </div>

                {locationPref && locationPref !== 'remote' && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs text-nexus-text-muted mb-1 block">Country</label>
                      <input type="text" value={country} onChange={e => setCountry(e.target.value)} className="nexus-input w-full py-2 text-sm" />
                    </div>
                    <div>
                      <label className="text-xs text-nexus-text-muted mb-1 block">State</label>
                      <input type="text" value={state} onChange={e => setState(e.target.value)} className="nexus-input w-full py-2 text-sm" />
                    </div>
                    <div>
                      <label className="text-xs text-nexus-text-muted mb-1 block">City</label>
                      <input type="text" value={city} onChange={e => setCity(e.target.value)} className="nexus-input w-full py-2 text-sm" />
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-nexus-text-muted mb-2">
                    Role Category
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {['Software Development (SDE)', 'AI and Machine Learning', 'Data Science / Data Engineering', 'DevOps / SRE', 'Product Management', 'Other'].map((cat) => {
                      const isSelected = roleCategories.includes(cat);
                      return (
                        <button
                          key={cat}
                          onClick={() => {
                            setRoleCategories(prev => 
                              isSelected ? prev.filter(c => c !== cat) : [...prev, cat]
                            );
                          }}
                          className={cn(
                            'py-2 px-3 rounded-lg text-sm transition-all border text-left',
                            isSelected 
                              ? 'bg-nexus-accent/20 border-nexus-accent text-white shadow-sm'
                              : 'bg-nexus-surface-2 border-nexus-border text-nexus-text-muted hover:text-white'
                          )}
                        >
                          {cat}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-nexus-text-muted mb-1.5">
                    Minimum Stipend (Optional)
                  </label>
                  <input
                    type="text"
                    value={minStipend}
                    onChange={(e) => setMinStipend(e.target.value)}
                    className="nexus-input w-full"
                  />
                </div>

                <div className="pt-4 border-t border-nexus-border">
                  <button
                    onClick={() => updatePreferencesMutation.mutate()}
                    disabled={updatePreferencesMutation.isPending}
                    className="nexus-btn-primary"
                  >
                    {updatePreferencesMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    Save Preferences
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* SECURITY TAB */}
          {activeTab === 'security' && (
            <div className="nexus-card space-y-6 animate-in slide-in-from-right-4 fade-in duration-300">
              <h2 className="text-lg font-semibold text-white">Change Password</h2>
              <p className="text-sm text-nexus-text-muted pb-4 border-b border-nexus-border">
                Your password must include letters, numbers, and at least one symbol.
              </p>

              <div className="space-y-4 max-w-md">
                <div>
                  <label className="block text-sm font-medium text-nexus-text-muted mb-1.5">
                    Current Password
                  </label>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="nexus-input w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-nexus-text-muted mb-1.5">
                    New Password
                  </label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="nexus-input w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-nexus-text-muted mb-1.5">
                    Confirm New Password
                  </label>
                  <input
                    type="password"
                    value={confirmNewPassword}
                    onChange={(e) => setConfirmNewPassword(e.target.value)}
                    className="nexus-input w-full"
                  />
                </div>

                <div className="pt-4">
                  <button
                    onClick={() => changePasswordMutation.mutate()}
                    disabled={changePasswordMutation.isPending || !currentPassword || !newPassword}
                    className="nexus-btn-primary"
                  >
                    {changePasswordMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    Update Password
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* DELETE ACCOUNT TAB */}
          {activeTab === 'delete' && (
            <div className="nexus-card space-y-6 border-red-500/30 animate-in slide-in-from-right-4 fade-in duration-300">
              <h2 className="text-lg font-semibold text-red-400 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5" />
                Delete Account
              </h2>
              <p className="text-sm text-nexus-text-muted pb-4 border-b border-nexus-border">
                Permanently delete your account and all associated data. This action cannot be undone.
              </p>

              {!showDeleteConfirm ? (
                <div>
                  <button
                    onClick={() => setShowDeleteConfirm(true)}
                    className="bg-red-500/10 text-red-500 hover:bg-red-500/20 border border-red-500/30 font-medium px-4 py-2 rounded-xl transition-all"
                  >
                    Delete Account
                  </button>
                </div>
              ) : (
                <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 animate-in fade-in">
                  <p className="text-sm text-red-400 font-medium mb-4">
                    Are you absolutely sure? This will delete your resume, match history, and all preferences permanently.
                  </p>
                  <div className="flex gap-3">
                    <button
                      onClick={() => deleteAccountMutation.mutate()}
                      disabled={deleteAccountMutation.isPending}
                      className="bg-red-500 hover:bg-red-600 text-white font-medium px-4 py-2 rounded-lg transition-all text-sm"
                    >
                      {deleteAccountMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Yes, Delete My Account'}
                    </button>
                    <button
                      onClick={() => setShowDeleteConfirm(false)}
                      disabled={deleteAccountMutation.isPending}
                      className="nexus-btn-ghost text-sm"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
