/** Mirrors backend RegisterRequest */
export interface RegisterRequest {
  email: string;
  password: string;
}

/** Mirrors backend LoginRequest */
export interface LoginRequest {
  email: string;
  password: string;
}

/** Mirrors backend GoogleAuthRequest */
export interface GoogleAuthRequest {
  credential: string;
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: any) => void;
          renderButton: (parent: HTMLElement | null, options: any) => void;
          prompt: () => void;
        };
      };
    };
  }
}

/** Mirrors backend TokenResponse */
export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  is_verified?: boolean;
  onboarded: boolean;
}

/** Mirrors backend ResumeResponse */
export interface ResumeResponse {
  id: string;
  raw_text: string;
  file_path: string | null;
  uploaded_at: string;
}

/** Mirrors backend MatchListingDetail */
export interface MatchListingDetail {
  id: string;
  title: string | null;
  company: string | null;
  location: string | null;
  remote_ok: boolean;
  stipend: string | null;
  required_skills: string[] | null;
  experience_level: string | null;
  deadline: string | null;
  source_url: string;
  is_active?: boolean;
  taken_down_at?: string | null;
}

/** Mirrors backend MatchResponse */
export interface MatchResponse {
  id: string;
  listing_id: string;
  match_score: number;
  justification: string | null;
  saved: boolean;
  status: string;
  change_alert?: string | null;
  change_alert_at?: string | null;
  created_at: string;
  listing: MatchListingDetail | null;
}

/** Mirrors backend MatchComputeResponse */
export interface MatchComputeResponse {
  computed: number;
  matches: MatchResponse[];
}

/** Mirrors backend BriefingJobResponse */
export interface BriefingJobResponse {
  id: string;
  status: string;
  script: string | null;
  media_url: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

/** Mirrors backend BriefingCreateResponse */
export interface BriefingCreateResponse {
  job_id: string;
  status: string;
  message: string;
}

/** Mirrors backend ChatMessage */
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

/** Mirrors backend AgentChatRequest */
export interface AgentChatRequest {
  messages: ChatMessage[];
  message: string;
}

/** Mirrors backend AgentChatResponse */
export interface AgentChatResponse {
  reply: string;
  tool_calls_made: string[];
}

/** Auth state stored in the app */
export interface AuthState {
  accessToken: string;
  userId: string;
  email: string;
  onboarded: boolean;
}

export interface UserPreferencesSchema {
  target_roles: string[];
  seniority: string | null;
  location_preference: string | null;
  locations: Array<{ country: string; state: string; city: string }>;
  min_stipend: string | null;
  role_preference: string[];
}

export interface UserProfileResponse {
  user_id: string;
  email: string;
  is_verified: boolean;
  onboarded: boolean;
  preferences: UserPreferencesSchema | null;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface FeatureCostItem {
  feature: string;
  label: string;
  tokens: number;
  cost_inr: number;
  cost_usd: number;
  call_count: number;
  percentage: number;
}

export interface DailySpendItem {
  date: string;
  tokens: number;
  cost_inr: number;
  cost_usd: number;
}

export interface TokenUsageRecord {
  id: string;
  feature: string;
  label: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_inr: number;
  cost_usd: number;
  created_at: string;
}

export interface CostSummaryResponse {
  total_tokens: number;
  total_cost_inr: number;
  total_cost_usd: number;
  total_calls: number;
  today_tokens: number;
  today_cost_inr: number;
  this_week_tokens: number;
  this_week_cost_inr: number;
  feature_breakdown: FeatureCostItem[];
  daily_trends: DailySpendItem[];
  recent_logs: TokenUsageRecord[];
}
