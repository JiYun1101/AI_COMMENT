import type { RecommendRequest, RecommendResponse, VideoPreviewData } from '../types/comment';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function getErrorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: string };
    if (body.detail) return body.detail;
  } catch {
    // Ignore invalid/non-JSON error bodies and use the fallback below.
  }
  return `${fallback} (${res.status})`;
}

/**
 * Wired to the real backend: POST /recommend
 * (src/api/main.py::recommend_comment_candidates)
 */
export async function recommend(request: RecommendRequest): Promise<RecommendResponse> {
  const res = await fetch(`${API_BASE}/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    throw new Error(await getErrorMessage(res, '추천 요청이 실패했습니다'));
  }

  return res.json();
}

/** Fetches real YouTube metadata from the backend reference-context endpoint. */
export async function getVideoPreview(url: string): Promise<VideoPreviewData> {
  const params = new URLSearchParams({ url });
  const res = await fetch(`${API_BASE}/videos/preview?${params.toString()}`);

  if (!res.ok) {
    throw new Error(await getErrorMessage(res, '영상 정보를 불러오지 못했습니다'));
  }

  return res.json();
}
