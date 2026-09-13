'use client';

import React, { useState } from 'react';
import { useAuth } from '@/lib/auth-context';
import api from '@/lib/api';
import toast from 'react-hot-toast';
import { ArrowRight, ArrowLeft, Check, Sparkles, Building2, MapPin, DollarSign, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export function OnboardingWizard() {
  const { updateUser } = useAuth();
  
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);

  // State
  const [targetRoles, setTargetRoles] = useState<string>('');
  const [seniority, setSeniority] = useState<string>('');
  const [locationPref, setLocationPref] = useState<'remote' | 'hybrid' | 'onsite' | ''>('');
  const [country, setCountry] = useState('');
  const [state, setState] = useState('');
  const [city, setCity] = useState('');
  const [roleCategories, setRoleCategories] = useState<string[]>([]);
  const [minStipend, setMinStipend] = useState('');

  const handleNext = () => {
    if (step === 1 && (!targetRoles.trim() || !seniority)) {
      toast.error('Please fill out roles and seniority.');
      return;
    }
    if (step === 2 && !locationPref) {
      toast.error('Please select a location preference.');
      return;
    }
    setStep((s) => s + 1);
  };

  const handleBack = () => setStep((s) => Math.max(1, s - 1));

  const handleComplete = async () => {
    if (roleCategories.length === 0) {
      toast.error('Please select at least one role category.');
      return;
    }
    setLoading(true);
    
    // Process target roles from comma separated string
    const rolesArray = targetRoles.split(',').map(s => s.trim()).filter(Boolean);
    
    const locations = [];
    if (locationPref !== 'remote' && (country || state || city)) {
      locations.push({ country, state, city });
    }

    const payload = {
      preferences: {
        target_roles: rolesArray,
        seniority: seniority,
        location_preference: locationPref,
        locations: locations,
        min_stipend: minStipend.trim() || null,
        role_preference: roleCategories,
      }
    };

    try {
      await api.patch('/api/auth/preferences', payload);
      toast.success('Preferences saved!');
      updateUser({ onboarded: true });
    } catch (err) {
      toast.error('Failed to save preferences.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] bg-nexus-bg flex items-center justify-center p-6 animate-in fade-in zoom-in-95 duration-300">
      {/* Background Glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-nexus-accent/5 rounded-full blur-3xl pointer-events-none" />
      
      <div className="relative w-full max-w-xl bg-nexus-surface/90 border border-nexus-border rounded-2xl p-8 shadow-2xl overflow-hidden backdrop-blur-md">
        
        {/* Progress Bar */}
        <div className="absolute top-0 left-0 w-full h-1 bg-nexus-surface-2">
          <div 
            className="h-full bg-nexus-accent transition-all duration-300"
            style={{ width: `${(step / 4) * 100}%` }}
          />
        </div>

        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-nexus-accent/20 mb-4">
            <Sparkles className="text-nexus-accent w-6 h-6" />
          </div>
          <h2 className="text-2xl font-bold text-white">Let's tailor your experience</h2>
          <p className="text-sm text-nexus-text-muted mt-1">
            We use these preferences to dramatically improve your semantic matches.
          </p>
        </div>

        {/* Swipe Container */}
        <div className="relative min-h-[250px]">
          
          {/* STEP 1 */}
          {step === 1 && (
            <div className="animate-in slide-in-from-right-4 fade-in duration-300 space-y-5">
              <div>
                <label className="block text-sm font-medium text-nexus-text-muted mb-1.5">
                  Target Roles (comma separated)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Backend Engineer, Full Stack Developer"
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
            </div>
          )}

          {/* STEP 2 */}
          {step === 2 && (
            <div className="animate-in slide-in-from-right-4 fade-in duration-300 space-y-5">
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
                <div className="space-y-4 pt-2 border-t border-nexus-border/50 animate-in fade-in">
                  <p className="text-xs text-nexus-text-dim">Where are you looking to work?</p>
                  
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs text-nexus-text-muted mb-1 block">Country</label>
                      <input type="text" placeholder="e.g. India" value={country} onChange={e => setCountry(e.target.value)} className="nexus-input w-full py-2 text-sm" />
                    </div>
                    <div>
                      <label className="text-xs text-nexus-text-muted mb-1 block">State (Optional)</label>
                      <input type="text" placeholder="e.g. Telangana" value={state} onChange={e => setState(e.target.value)} className="nexus-input w-full py-2 text-sm" />
                    </div>
                    <div>
                      <label className="text-xs text-nexus-text-muted mb-1 block">City</label>
                      <input type="text" placeholder="e.g. Hyderabad" value={city} onChange={e => setCity(e.target.value)} className="nexus-input w-full py-2 text-sm" />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP 3 */}
          {step === 3 && (
            <div className="animate-in slide-in-from-right-4 fade-in duration-300 space-y-5">
              <div>
                <label className="block text-sm font-medium text-nexus-text-muted mb-2">
                  Role Category
                </label>
                <div className="grid grid-cols-2 gap-3">
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
            </div>
          )}

          {/* STEP 4 */}
          {step === 4 && (
            <div className="animate-in slide-in-from-right-4 fade-in duration-300 space-y-5 text-center">
              <div className="w-16 h-16 bg-amber-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
                <DollarSign className="text-amber-400 w-8 h-8" />
              </div>
              <h3 className="text-lg font-semibold text-white">Minimum Stipend / Salary</h3>
              <p className="text-sm text-nexus-text-muted">
                (Optional) We'll use this to prioritize higher-paying opportunities.
              </p>
              
              <div className="max-w-xs mx-auto mt-4">
                <input
                  type="text"
                  placeholder="e.g. > 100000 rupees, $100k, 500 EUR"
                  value={minStipend}
                  onChange={(e) => setMinStipend(e.target.value)}
                  className="nexus-input w-full text-center"
                />
              </div>
            </div>
          )}

        </div>

        {/* Footer Actions */}
        <div className="mt-8 flex items-center justify-between pt-4 border-t border-nexus-border">
          <button
            onClick={handleBack}
            disabled={step === 1 || loading}
            className="nexus-btn-ghost text-sm disabled:opacity-0"
          >
            <ArrowLeft size={16} /> Back
          </button>
          
          {step < 4 ? (
            <button onClick={handleNext} className="nexus-btn-primary text-sm px-6">
              Next <ArrowRight size={16} />
            </button>
          ) : (
            <button onClick={handleComplete} disabled={loading} className="nexus-btn-primary text-sm px-6">
              {loading ? <Loader2 className="animate-spin w-4 h-4" /> : <Check className="w-4 h-4" />}
              Complete
            </button>
          )}
        </div>

      </div>
    </div>
  );
}
