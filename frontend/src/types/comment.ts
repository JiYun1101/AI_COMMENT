export type CommentType = 'insight' | 'casual' | 'empathy' | 'question' | 'negative' | 'general';

export const COMMENT_TYPE_LABEL: Record<CommentType, string> = {
  insight: '인사이트',
  casual: '캐주얼',
  empathy: '공감형',
  question: '질문형',
  negative: '부정',
  general: '일반',
};

// Matches --tag-* tokens in styles/tokens.css
export const COMMENT_TYPE_COLOR: Record<CommentType, { bg: string; fg: string; dot: string }> = {
  empathy: { bg: '#fdeef6', fg: '#9d174d', dot: '#ec4899' },
  insight: { bg: '#f3ecfd', fg: '#5b21b6', dot: '#7c3aed' },
  question: { bg: '#eef4ff', fg: '#1846a6', dot: '#2c6ef2' },
  casual: { bg: '#e6f7f4', fg: '#0f766e', dot: '#14b8a6' },
  negative: { bg: '#fdecec', fg: '#a52626', dot: '#d93b3b' },
  general: { bg: '#f1f3f5', fg: '#333b47', dot: '#6b7481' },
};

// Mirrors src/api/schemas.py::RecommendRequest
export interface RecommendRequest {
  post_text?: string;
  youtube_url?: string;
  top_k: number;
}

// Mirrors the dict shape returned by src/recommender/ranker.py::recommend_comments
export interface CommentRecommendation {
  rank: number;
  type: CommentType | string;
  comment: string;
  predicted_score: number;
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
}

export interface RecommendResponse {
  post_text: string;
  youtube_context?: YouTubeVideoContext | null;
  recommendations: CommentRecommendation[];
}

export type Category = 'auto' | 'social' | 'vlog';

export type VideoPreviewData = YouTubeVideoContext;
