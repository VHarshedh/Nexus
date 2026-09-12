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

/** Mirrors backend TokenResponse */
export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
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
}

/** Mirrors backend MatchResponse */
export interface MatchResponse {
  id: string;
  listing_id: string;
  match_score: number;
  justification: string | null;
  saved: boolean;
  status: string;
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
}
