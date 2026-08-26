import type {
  AnalysisDetail,
  AnalysisSummary,
  CommentsResponse,
  DashboardSummary,
  FeedbackValue,
  RecommendRequest,
  RecommendResponse,
  ServiceHealth,
  VideoPreviewData,
} from '../types/comment';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function getErrorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: string };
    if (body.detail) return body.detail;
  } catch {
    // Ignore invalid/non-JSON bodies and use the fallback.
  }
  return `${fallback} (${res.status})`;
}

async function requestJson<T>(url: string, init: RequestInit | undefined, fallback: string): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(await getErrorMessage(res, fallback));
  return res.json() as Promise<T>;
}

export async function getHealth(): Promise<ServiceHealth> {
  return requestJson<ServiceHealth>(`${API_BASE}/health`, undefined, '서비스 상태를 확인하지 못했습니다');
}

export async function recommend(request: RecommendRequest): Promise<RecommendResponse> {
  return requestJson<RecommendResponse>(
    `${API_BASE}/recommend`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    },
    '추천 요청이 실패했습니다',
  );
}

export async function getVideoPreview(url: string): Promise<VideoPreviewData> {
  const params = new URLSearchParams({ url });
  return requestJson<VideoPreviewData>(
    `${API_BASE}/videos/preview?${params.toString()}`,
    undefined,
    '영상 정보를 불러오지 못했습니다',
  );
}

export async function listAnalyses(limit = 3): Promise<AnalysisSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  const body = await requestJson<{ items: AnalysisSummary[] }>(
    `${API_BASE}/analyses?${params.toString()}`,
    undefined,
    '최근 분석 기록을 불러오지 못했습니다',
  );
  return body.items;
}

export async function getAnalysis(analysisId: string): Promise<AnalysisDetail> {
  return requestJson<AnalysisDetail>(
    `${API_BASE}/analyses/${encodeURIComponent(analysisId)}`,
    undefined,
    '분석 기록을 불러오지 못했습니다',
  );
}

export interface CommentFilters {
  query?: string;
  type?: string;
  category?: string;
  minScore?: number;
  limit?: number;
  offset?: number;
}

export async function listComments(filters: CommentFilters = {}): Promise<CommentsResponse> {
  const params = new URLSearchParams();
  if (filters.query) params.set('query', filters.query);
  if (filters.type) params.set('type', filters.type);
  if (filters.category && filters.category !== 'auto') params.set('category', filters.category);
  if (filters.minScore != null) params.set('min_score', String(filters.minScore));
  params.set('limit', String(filters.limit ?? 25));
  params.set('offset', String(filters.offset ?? 0));

  return requestJson<CommentsResponse>(
    `${API_BASE}/comments?${params.toString()}`,
    undefined,
    '댓글 목록을 불러오지 못했습니다',
  );
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return requestJson<DashboardSummary>(
    `${API_BASE}/dashboard/summary`,
    undefined,
    '대시보드 요약을 불러오지 못했습니다',
  );
}

export async function sendFeedback(recommendationId: string, useful: boolean): Promise<FeedbackValue> {
  const body = await requestJson<{ id: string; feedback: FeedbackValue }>(
    `${API_BASE}/recommendations/${encodeURIComponent(recommendationId)}/feedback`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ useful }),
    },
    '피드백 저장에 실패했습니다',
  );
  return body.feedback;
}
