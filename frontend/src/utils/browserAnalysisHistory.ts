import type { AnalysisDetail, AnalysisSummary, RecommendResponse } from '../types/comment';

/** Guest-only browser recovery; not shared between browsers or accounts. */
const STORAGE_KEY = 'ai-comment.guest-analysis-history.v1';
const MAX_ITEMS = 40;

function read(): AnalysisDetail[] {
  if (typeof window === 'undefined') return [];
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((row): row is AnalysisDetail =>
      Boolean(row && typeof row === 'object'
        && typeof row.id === 'string' && /^a_[A-Za-z0-9_-]{6,80}$/.test(row.id)
        && typeof row.created_at === 'string' && Number.isFinite(Date.parse(row.created_at))
        && typeof row.source_text === 'string' && Array.isArray(row.recommendations))
    ).slice(0, MAX_ITEMS);
  } catch { return []; }
}

function summary(row: AnalysisDetail): AnalysisSummary {
  const scores = row.recommendations.map(x => x.predicted_score).filter(x => Number.isFinite(x));
  return {
    id: row.id,
    source_type: row.source_type,
    source_text: row.source_text,
    youtube_url: row.youtube_url,
    video_id: row.video_id,
    video_title: row.video_title,
    channel: row.channel,
    thumbnail_url: row.thumbnail_url,
    category: row.category,
    created_at: row.created_at,
    recommendation_count: row.recommendations.length,
    average_score: scores.length ? scores.reduce((sum, x)=>sum+x,0)/scores.length : 0,
    requested_count: row.requested_count,
    additional_context: row.additional_context,
  };
}

export function saveGuestBrowserAnalysis(
  response: RecommendResponse,
  request: { post_text?: string; youtube_url?: string; additional_context?: string },
): boolean {
  if (typeof window === 'undefined' || !response.analysis_id || !response.recommendations.length) return false;
  const youtube = response.youtube_context;
  const item: AnalysisDetail = {
    id: response.analysis_id,
    source_type: youtube ? 'youtube' : 'manual',
    source_text: youtube?.title || request.post_text || request.youtube_url || '',
    youtube_url: youtube?.url || null,
    video_id: youtube?.video_id || null,
    video_title: youtube?.title || null,
    channel: youtube?.channel || null,
    thumbnail_url: youtube?.thumbnail_url || null,
    category: response.resolved_category || '',
    created_at: new Date().toISOString(),
    requested_count: response.generation.requested_count,
    additional_context: request.additional_context || null,
    recommendations: response.recommendations,
    context_summary: response.context || null,
  };
  try {
    const other = read().filter(row => row.id !== item.id);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([item, ...other].slice(0, MAX_ITEMS)));
    return true;
  } catch {
    // Never hide successfully generated recommendations because browser storage is full.
    return false;
  }
}
export function listGuestBrowserAnalyses(limit = 40): AnalysisSummary[] {
  return read().map(summary).slice(0, Math.max(0, limit));
}
export function getGuestBrowserAnalysis(id: string): AnalysisDetail | null {
  return read().find(row => row.id === id) ?? null;
}
