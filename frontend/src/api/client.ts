import type { RecommendRequest, RecommendResponse, VideoPreviewData } from '../types/comment';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

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
    throw new Error(`추천 요청이 실패했습니다 (${res.status})`);
  }

  return res.json();
}

/**
 * NOT wired to a real endpoint yet — the backend has no /videos/preview route.
 * Returns a fixed mock so the composer's preview card can be demoed end to end.
 * Replace with a real call once the backend exposes YouTube metadata lookup.
 */
export async function getVideoPreview(_url: string): Promise<VideoPreviewData> {
  await new Promise((resolve) => setTimeout(resolve, 250));
  return {
    title: 'AI 시대에 개발자는 어떻게 살아남아야 할까? — 실무자 인터뷰',
    channel: '테크살롱',
    subs: '38.2만',
    views: '284,120회',
    age: '3일 전',
    duration: '14:22',
  };
}
