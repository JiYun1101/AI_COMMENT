export type CommentType = 'insight' | 'casual' | 'empathy' | 'question' | 'negative' | 'general';
export type Category = 'auto' | 'social' | 'vlog';
export type ResolvedCategory = Exclude<Category, 'auto'>;
export type FeedbackValue = 'useful' | 'not_useful' | null;

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
  category: Category;
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
  subscriber_count: number | null;
  view_count: number | null;
  published_at: string | null;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  transcript_available: boolean;
  transcript_language: string | null;
}

export interface GenerationMeta {
  requested_count: number;
  returned_count: number;
  candidate_count: number;
  safe_candidate_count: number;
  blocked_candidate_count: number;
}

export interface RecommendResponse {
  analysis_id: string;
  post_text: string;
  resolved_category: ResolvedCategory;
  youtube_context?: YouTubeVideoContext | null;
  recommendations: CommentRecommendation[];
  generation: GenerationMeta;
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
  category: ResolvedCategory;
  created_at: string;
  recommendation_count: number;
  average_score: number;
}

export interface AnalysisDetail extends Omit<AnalysisSummary, 'recommendation_count' | 'average_score'> {
  recommendations: CommentRecommendation[];
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
  category: ResolvedCategory;
  source_type: 'youtube' | 'manual';
  video_title: string | null;
  channel: string | null;
}

export interface CommentsResponse {
  total: number;
  items: DashboardComment[];
}

export type VideoPreviewData = YouTubeVideoContext;
