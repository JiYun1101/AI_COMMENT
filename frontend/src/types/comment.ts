export type CommentType = 'insight' | 'casual' | 'empathy' | 'question' | 'negative' | 'general';
export type Category = string;
export type ResolvedCategory = string;
export type FeedbackValue = 'useful' | 'not_useful' | null;
export type TranscriptStatus = 'available' | 'unavailable' | 'fetch_failed';
export type AccountMode = 'demo' | 'personal';
export type PresetPersonaId =
  | 'none'
  | 'polite_viewer'
  | 'friendly_viewer'
  | 'warm_supporter'
  | 'calm_analyst'
  | 'playful_casual';
export type PersonaId = PresetPersonaId | `custom_${string}`;

export type ForbiddenPersonaMark = 'period' | 'exclamation' | 'question' | 'comma' | 'tilde' | 'emoji' | 'laughter';

export interface CustomPersona {
  id: `custom_${string}`;
  name: string;
  speech_style: string;
  recurring_phrases: string[];
  prohibited_phrases: string[];
  forbidden_marks: ForbiddenPersonaMark[];
  sample_comment: string;
}

export const COMMENT_TYPE_LABEL: Record<CommentType, string> = {
  insight: '인사이트',
  casual: '캐주얼',
  empathy: '공감형',
  question: '질문형',
  negative: '부정',
  general: '일반',
};

export const COMMENT_TYPE_COLOR: Record<CommentType, { bg: string; fg: string; dot: string }> = {
  empathy: { bg: '#fdeef6', fg: '#9d174d', dot: '#ec4899' },
  insight: { bg: '#f3ecfd', fg: '#5b21b6', dot: '#7c3aed' },
  question: { bg: '#eef4ff', fg: '#1846a6', dot: '#2c6ef2' },
  casual: { bg: '#e6f7f4', fg: '#0f766e', dot: '#14b8a6' },
  negative: { bg: '#fdecec', fg: '#a52626', dot: '#d93b3b' },
  general: { bg: '#f1f3f5', fg: '#333b47', dot: '#6b7481' },
};

export interface RecommendRequest {
  post_text?: string;
  youtube_url?: string;
  additional_context?: string;
  category?: string;
  persona_id?: PersonaId;
  custom_persona?: CustomPersona;
  top_k: number;
}

export interface CommentRecommendation {
  id: string;
  rank: number;
  type: CommentType | string;
  comment: string;
  predicted_score: number;
  feedback?: FeedbackValue;
}

export interface YouTubeVideoContext {
  video_id: string;
  url: string;
  title: string;
  description: string;
  channel: string;
  channel_id?: string | null;
  subscriber_count: number | null;
  view_count: number | null;
  published_at: string | null;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  transcript_available: boolean;
  transcript_language: string | null;
  transcript_status?: TranscriptStatus;
  category_id?: string | null;
  category_name?: string | null;
  tags?: string[];
  default_language?: string | null;
  like_count?: number | null;
  comment_count?: number | null;
  made_for_kids?: boolean | null;
  age_restricted?: boolean;
  topic_categories?: string[];
  live_broadcast_content?: string | null;
  live_streaming_details?: Record<string, unknown> | null;
  is_short?: boolean;
}

export interface ReadinessComponent {
  ready: boolean;
  [key: string]: unknown;
}

export interface YouTubeOAuthStatus {
  configured: boolean;
  authorized: boolean;
  scope: string;
}

export interface YouTubeDemoStatus {
  configured: boolean;
  ready: boolean;
  hourly_limit: number;
  daily_limit: number;
  remaining_hourly: number;
  remaining_daily: number;
  youtube_api_configured?: boolean;
  openai_configured?: boolean;
  posting_configured?: boolean;
}

export interface YouTubeCommentPublishResponse {
  posted: boolean;
  video_id: string;
  comment_id: string | null;
  comment: string;
  comment_url: string;
  account_mode?: AccountMode;
  tracked?: boolean;
  tracking_warning?: string;
  browser_backup_saved?: boolean;
}

export interface ServiceHealth {
  status: 'ok' | 'degraded' | string;
  message: string;
  model: ReadinessComponent;
  llm: ReadinessComponent;
  youtube: { configured: boolean; oauth?: YouTubeOAuthStatus; demo?: YouTubeDemoStatus };
  storage: { ready: boolean; persistent?: boolean; warning?: string | null };
}

export interface GenerationContextSummary {
  primary_category: string;
  official_category: string | null;
  topics: string[];
  content_styles: string[];
  format: string;
  broadcast: string;
  freshness: string;
  hype_label: string;
  hype_score: number | null;
  historical_match_count: number;
  historical_coverage: string;
}

export interface GenerationMeta {
  requested_count: number;
  returned_count: number;
  candidate_count: number;
  safe_candidate_count: number;
  blocked_candidate_count: number;
  generator?: string;
  provider?: string | null;
  model?: string | null;
  persona_id?: PersonaId;
  persona_name?: string | null;
}

export interface RecommendationTraceCandidate {
  sequence: number;
  attempt: number;
  type: CommentType | string;
  comment: string;
  safety: 'passed' | 'blocked';
  safety_reason: string | null;
  duplicate: boolean;
  ranker_score: number | null;
  selected: boolean;
  final_rank: number | null;
}

export interface RecommendationTrace {
  safety_blocked_count: number;
  duplicate_candidate_count: number;
  candidates: RecommendationTraceCandidate[];
}

export interface RecommendResponse {
  analysis_id: string;
  post_text: string;
  resolved_category: ResolvedCategory;
  youtube_context?: YouTubeVideoContext | null;
  context?: GenerationContextSummary | null;
  recommendations: CommentRecommendation[];
  generation: GenerationMeta;
  trace?: RecommendationTrace | null;
}

export interface AnalysisSummary {
  id: string;
  source_type: 'youtube' | 'manual';
  source_text: string;
  youtube_url: string | null;
  video_id: string | null;
  video_title: string | null;
  channel: string | null;
  thumbnail_url: string | null;
  category: string;
  created_at: string;
  recommendation_count: number;
  average_score: number;
  requested_count?: number | null;
  additional_context?: string | null;
}

export interface AnalysisDetail extends Omit<AnalysisSummary, 'recommendation_count' | 'average_score'> {
  recommendations: CommentRecommendation[];
  generation_context?: Record<string, unknown> | null;
  context_summary?: GenerationContextSummary | null;
}

export interface DashboardSummary {
  analysis_count: number;
  recommendation_count: number;
  average_score: number;
  feedback_count: number;
  helpful_rate: number | null;
}

export interface DashboardComment {
  id: string;
  analysis_id: string;
  rank: number;
  type: string;
  comment: string;
  predicted_score: number;
  feedback: FeedbackValue;
  created_at: string;
  category: string;
  source_type: 'youtube' | 'manual';
  video_title: string | null;
  channel: string | null;
}

export interface CommentsResponse {
  total: number;
  items: DashboardComment[];
}

export type VideoPreviewData = YouTubeVideoContext;

export interface PublishedComment {
  id: string;
  recommendation_id: string | null;
  account_mode: AccountMode;
  video_id: string;
  comment_id: string;
  comment: string;
  comment_url: string | null;
  published_at: string;
  hours_since_publish: number;
  like_count: number | null;
  reply_count: number | null;
  likes_24h: number | null;
  replies_24h: number | null;
  likes_7d: number | null;
  replies_7d: number | null;
  status: 'pending' | 'active' | 'missing';
  last_checked_at: string | null;
  local_only?: boolean;
  public_metric_status?: 'active' | 'unavailable';
  predicted_score: number | null;
  comment_type: string | null;
  video_title: string | null;
  channel: string | null;
}

export interface PublishedSummary {
  tracked_count: number;
  measured_count: number;
  missing_count: number;
  average_likes: number | null;
  replied_rate: number | null;
  prediction_pair_count: number;
  prediction_spearman: number | null;
  by_type: { type: string; count: number; average_likes: number | null }[];
}

export interface PublishedCommentsResponse {
  summary: PublishedSummary;
  items: PublishedComment[];
  checked_count?: number;
  backend_unavailable?: boolean;
}

export type InboxCategory = 'question' | 'complaint' | 'risk' | 'praise' | 'other';

export interface InboxItem {
  id: string;
  author: string;
  text: string;
  like_count: number;
  reply_count: number;
  published_at: string | null;
  can_reply: boolean;
  category: InboxCategory;
  category_label: string;
  risk_reason: string | null;
  creator_replied: boolean;
  needs_reply: boolean;
  priority: number;
}

export interface CreatorInboxResponse {
  video: {
    video_id: string;
    url: string;
    title: string;
    channel: string;
    channel_id: string | null;
    thumbnail_url: string | null;
    comment_count: number | null;
  };
  order: 'relevance' | 'time';
  items: InboxItem[];
  summary: {
    total: number;
    needs_reply: number;
    creator_replied: number;
    own_comments: number;
    by_category: Record<InboxCategory, number>;
  };
}

export interface ReplyDraftsResponse {
  source: 'llm' | 'template';
  drafts: string[];
}

export interface CreatorReplyResponse {
  posted: boolean;
  parent_id: string;
  reply_id: string | null;
  video_id: string | null;
  text: string;
  comment_url: string | null;
}


/** Observed YouTube comment sample, not a probability estimate. */
export interface AudienceIntentDistribution {
  key: string;
  label: string;
  count: number;
  percentage: number;
}

export interface AudienceObservationReport {
  video_id: string;
  analysis_id: string | null;
  order: 'relevance';
  observed: { total: number; distribution: AudienceIntentDistribution[] };
  expected: { total: number; distribution: AudienceIntentDistribution[] } | null;
  comparison: {
    method: string;
    warning: string;
    sample_difference_points: number;
    distribution: Array<{
      key: string;
      label: string;
      expected_percentage: number;
      observed_percentage: number;
      delta_percentage_points: number;
    }>;
  } | null;
  caveat: string;
  examples: Array<{
    id: string;
    text: string;
    intent: string;
    like_count: number;
    reply_count: number;
    published_at: string | null;
  }>;
  comments: Array<{ id: string; text: string; intent: string; like_count: number; reply_count: number; published_at: string | null }>;
}

export interface AudienceSnapshotSummary {
  id: string;
  video_id: string;
  analysis_id: string | null;
  observed_at: string;
  sample_count: number;
}


/** Cumulative video counters, fetched from YouTube Data API v3. */
export interface OwnedVideoMetric {
  owner_channel_id: string;
  video_id: string;
  title: string;
  thumbnail_url: string | null;
  published_at: string | null;
  privacy_status: string;
  views: number | null;
  likes: number | null;
  comments: number | null;
  last_checked_at: string;
  views_since_previous: number | null;
  views_24h: number | null;
  views_7d: number | null;
  local_only?: boolean;
}
export interface OwnedVideoPerformanceResponse {
  channel_id: string;
  channel_title: string;
  last_sync_at: string | null;
  storage_persistent: boolean;
  storage_warning?: string | null;
  summary: {
    tracked_count: number;
    measured_count: number;
    total_views: number;
    total_likes: number;
    total_comments: number;
    average_views: number | null;
  };
  items: OwnedVideoMetric[];
  checked_count?: number;
  cached?: boolean;
  limit_reached?: boolean;
  added_video_id?: string;
}

/** Actual accumulated inputs and analysis records; not model retraining history. */
export interface ModelDataProgress {
  reference: { usable_comments: number; sources: { name: string; count: number }[]; meaning: string };
  observations: {
    analyses: number;
    unique_videos: number;
    stored_contexts: number;
    recommendations: number;
    feedback: number;
    historical_matched_analyses: number;
    average_matches: number | null;
  };
  daily: { date: string; new_analyses: number; cumulative_analyses: number }[];
  note: string;
}
