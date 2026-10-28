import { cachedAccount, savePrivatePublishedReceipts, savePrivateAnalysis, listPrivateAnalyses, getPrivateAnalysis, getPrivateDashboardSummary, listPrivateComments, sendPrivateFeedback } from './account';
import type {
  AccountMode,
  AnalysisDetail,
  AudienceObservationReport,
  AudienceSnapshotSummary,
  AnalysisSummary,
  CommentsResponse,
  CreatorInboxResponse,
  CreatorReplyResponse,
  DashboardSummary,
  FeedbackValue,
  PersonaId,
  PublishedCommentsResponse,
  RecommendRequest,
  ReplyDraftsResponse,
  RecommendResponse,
  ServiceHealth,
  VideoPreviewData,
  YouTubeCommentPublishResponse,
  YouTubeDemoStatus,
  YouTubeOAuthStatus,
  OwnedVideoPerformanceResponse,
} from '../types/comment';
import { applySavedPublicMetrics, type PublicMetricResponse } from '../utils/publicMetricsBackup';
import { saveGuestBrowserAnalysis, listGuestBrowserAnalyses, getGuestBrowserAnalysis } from '../utils/browserAnalysisHistory';
import { getCustomPersona } from '../utils/customPersonas';
import { backUpPostedComment, backUpServerComments, mergePostedBackup, readPostedBackup } from '../utils/publishedLedger';

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.DEV ? 'http://localhost:8000' : 'https://ai-comment-api-lite.onrender.com');

const YOUTUBE_API_KEY_STORAGE_KEY = 'ai-comment.youtube-api-key';
const OPENAI_API_KEY_STORAGE_KEY = 'ai-comment.openai-api-key';
const OPENAI_MODEL_STORAGE_KEY = 'ai-comment.openai-model';
const YOUTUBE_OAUTH_CLIENT_ID_STORAGE_KEY = 'ai-comment.youtube-oauth-client-id';
const YOUTUBE_OAUTH_CLIENT_SECRET_STORAGE_KEY = 'ai-comment.youtube-oauth-client-secret';
const API_ACCESS_TOKEN_STORAGE_KEY = 'ai-comment.server-access-token';
const ACCOUNT_MODE_STORAGE_KEY = 'ai-comment.account-mode';
const PERSONA_STORAGE_KEY = 'ai-comment.persona';
export const DEFAULT_OPENAI_MODEL = 'gpt-6-luna';
// Google OAuth needs an absolute https redirect URI. A preview's API_BASE may
// be the relative same-origin '/api' reverse proxy path.
export const YOUTUBE_OAUTH_REDIRECT_URI = new URL(
  `${API_BASE}/youtube/oauth/callback`,
  typeof window !== 'undefined' ? window.location.origin : 'http://localhost:5173',
).toString();

function getStoredValue(key: string): string {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem(key)?.trim() ?? '';
}

function setStoredValue(key: string, value: string): void {
  if (typeof window === 'undefined') return;
  const normalized = value.trim();
  if (normalized) window.localStorage.setItem(key, normalized);
  else window.localStorage.removeItem(key);
}


export interface ServerPairingResult {
  access_token: string;
  expires_at: number;
}

export async function verifyServerConnection(token = getStoredApiAccessToken()): Promise<{ connected: boolean }> {
  return requestJson<{ connected: boolean }>(
    API_BASE + '/auth/session',
    { headers: token ? { 'X-API-Key': token } : {} },
    '서버 연결 상태를 확인하지 못했습니다',
  );
}

export async function connectServerWithCode(code: string): Promise<ServerPairingResult> {
  const result = await requestJson<ServerPairingResult>(
    API_BASE + '/auth/connect',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pairing_code: code.trim() }),
    },
    '서버 연결에 실패했습니다',
  );
  const verified = await verifyServerConnection(result.access_token);
  if (!verified.connected) throw new Error('서버 연결을 확인하지 못했습니다.');
  setStoredApiAccessToken(result.access_token);
  return result;
}

export function getStoredApiAccessToken(): string {
  return getStoredValue(API_ACCESS_TOKEN_STORAGE_KEY);
}

export function setStoredApiAccessToken(value: string): void {
  setStoredValue(API_ACCESS_TOKEN_STORAGE_KEY, value);
}

export function getAccountMode(): AccountMode {
  const value = getStoredValue(ACCOUNT_MODE_STORAGE_KEY);
  if (value === 'personal' || value === 'demo') return value;

  const hasPersonalCredentials = Boolean(
    getStoredValue(YOUTUBE_OAUTH_CLIENT_ID_STORAGE_KEY)
      || getStoredValue(YOUTUBE_OAUTH_CLIENT_SECRET_STORAGE_KEY)
      || getStoredValue(YOUTUBE_API_KEY_STORAGE_KEY)
      || getStoredValue(OPENAI_API_KEY_STORAGE_KEY)
  );
  return hasPersonalCredentials ? 'personal' : 'demo';
}

export function setAccountMode(value: AccountMode): void {
  setStoredValue(ACCOUNT_MODE_STORAGE_KEY, value);
}

export function getSelectedPersona(): PersonaId {
  const value = getStoredValue(PERSONA_STORAGE_KEY) as PersonaId;
  if (value.startsWith('custom_')) return getCustomPersona(value) ? value : 'none';
  return [
    'none', 'polite_viewer', 'friendly_viewer', 'warm_supporter',
    'calm_analyst', 'playful_casual',
  ].includes(value) ? value : 'none';
}

export function setSelectedPersona(value: PersonaId): void {
  setStoredValue(PERSONA_STORAGE_KEY, value);
}

export function getStoredYouTubeApiKey(): string {
  return getStoredValue(YOUTUBE_API_KEY_STORAGE_KEY);
}

export function setStoredYouTubeApiKey(value: string): void {
  setStoredValue(YOUTUBE_API_KEY_STORAGE_KEY, value);
}

export function getStoredOpenAIApiKey(): string {
  return getStoredValue(OPENAI_API_KEY_STORAGE_KEY);
}

export function setStoredOpenAIApiKey(value: string): void {
  setStoredValue(OPENAI_API_KEY_STORAGE_KEY, value);
}

export function getStoredOpenAIModel(): string {
  const stored = getStoredValue(OPENAI_MODEL_STORAGE_KEY);
  // The old UI default is not a documented current API model ID. Keep custom
  // selections intact, but move this exact legacy default to the current model.
  return !stored || stored === 'gpt-5.6-luna' ? DEFAULT_OPENAI_MODEL : stored;
}

export function setStoredOpenAIModel(value: string): void {
  setStoredValue(OPENAI_MODEL_STORAGE_KEY, value || DEFAULT_OPENAI_MODEL);
}

export function getStoredYouTubeOAuthClientId(): string {
  return getStoredValue(YOUTUBE_OAUTH_CLIENT_ID_STORAGE_KEY);
}

export function setStoredYouTubeOAuthClientId(value: string): void {
  setStoredValue(YOUTUBE_OAUTH_CLIENT_ID_STORAGE_KEY, value);
}

export function getStoredYouTubeOAuthClientSecret(): string {
  return getStoredValue(YOUTUBE_OAUTH_CLIENT_SECRET_STORAGE_KEY);
}

export function setStoredYouTubeOAuthClientSecret(value: string): void {
  setStoredValue(YOUTUBE_OAUTH_CLIENT_SECRET_STORAGE_KEY, value);
}

function withRuntimeKeys(headers: Record<string, string> = {}): Record<string, string> {
  const mode = getAccountMode();
  const youtubeApiKey = mode === 'personal' ? getStoredYouTubeApiKey() : '';
  const openaiApiKey = mode === 'personal' ? getStoredOpenAIApiKey() : '';
  const openaiModel = getStoredOpenAIModel();
  return {
    ...headers,
    'X-AI-Comment-Account-Mode': mode,
    ...(getStoredApiAccessToken() ? { 'X-API-Key': getStoredApiAccessToken() } : {}),
    ...(youtubeApiKey ? { 'X-YouTube-API-Key': youtubeApiKey } : {}),
    ...(openaiApiKey ? { 'X-OpenAI-API-Key': openaiApiKey, 'X-OpenAI-Model': openaiModel } : {}),
  };
}

function withYouTubeOAuth(headers: Record<string, string> = {}): Record<string, string> {
  const clientId = getStoredYouTubeOAuthClientId();
  const clientSecret = getStoredYouTubeOAuthClientSecret();
  return {
    ...headers,
    ...(getStoredApiAccessToken() ? { 'X-API-Key': getStoredApiAccessToken() } : {}),
    ...(clientId ? { 'X-YouTube-OAuth-Client-ID': clientId } : {}),
    ...(clientSecret ? { 'X-YouTube-OAuth-Client-Secret': clientSecret } : {}),
    'X-YouTube-OAuth-Redirect-URI': YOUTUBE_OAUTH_REDIRECT_URI,
  };
}

async function getErrorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: string };
    if (body.detail) return body.detail;
  } catch {
    // Ignore invalid/non-JSON bodies and use the fallback.
  }
  if (res.status === 429) {
    // Render Free may rate-limit the public edge before FastAPI can return JSON.
    // This also covers non-JSON gateway responses. Never auto-retry a billable
    // LLM generation or a potentially side-effectful publishing request.
    const retryAfterHeader = res.headers.get('Retry-After');
    const seconds = retryAfterHeader === null ? NaN : Number(retryAfterHeader);
    const retryHint = Number.isFinite(seconds) && seconds > 0 && seconds <= 3600
      ? `약 ${Math.ceil(seconds / 60)}분 후`
      : '잠시 후';
    return `${fallback}: 요청이 일시적으로 제한됐습니다 (429). ${retryHint} 다시 시도해주세요. ` +
      'Render 무료 서버·프록시 또는 외부 API의 요청 제한일 수 있습니다. 중복 호출을 피해주세요.';
  }
  return `${fallback} (${res.status})`;
}

async function requestJson<T>(url: string, init: RequestInit | undefined, fallback: string): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(await getErrorMessage(res, fallback));
  return res.json() as Promise<T>;
}

export async function getHealth(): Promise<ServiceHealth> {
  const health = await requestJson<ServiceHealth>(
    `${API_BASE}/health`,
    undefined,
    '서비스 상태를 확인하지 못했습니다',
  );
  // The free Render backend reports its generic Ollama fallback as "ready"
  // even though there is no local Ollama process. Confirmed by live POST smoke.
  // Only the presentation environment opts into this stronger UI readiness gate.
  const usesUnavailableLocalModel =
    typeof window !== 'undefined'
    && window.location.hostname !== 'localhost'
    && window.location.hostname !== '127.0.0.1'
    && health.llm.provider === 'ollama_local';
  const hasPersonalLLM = getAccountMode() === 'personal' && Boolean(getStoredOpenAIApiKey());
  return {
    ...health,
    llm: hasPersonalLLM
      ? { ...health.llm, ready: true, provider: 'openai_responses_api', model: getStoredOpenAIModel(), missing: [] }
      : usesUnavailableLocalModel
        ? { ...health.llm, ready: false, missing: ['OpenAI API Key (personal account)'] }
        : health.llm,
    youtube:
      getAccountMode() === 'personal' && getStoredYouTubeApiKey()
        ? { ...health.youtube, configured: true }
        : health.youtube,
  };
}

/**
 * Warm the Render Free API using GET requests before sending a billable
 * recommendation POST. Retries are intentionally limited to read-only health;
 * a failed generation or YouTube publishing POST must not be replayed.
 */
export async function waitForHealthyBackend(
  onRetry?: (attempt: number, total: number) => void,
): Promise<ServiceHealth> {
  const backoffsMs = [8_000, 15_000, 25_000, 30_000];
  let lastError: unknown;
  for (let attempt = 0; attempt <= backoffsMs.length; attempt++) {
    try {
      return await getHealth();
    } catch (error) {
      lastError = error;
      if (attempt === backoffsMs.length) break;
      onRetry?.(attempt + 1, backoffsMs.length);
      await new Promise<void>((resolve) => {
        window.setTimeout(resolve, backoffsMs[attempt]);
      });
    }
  }
  throw lastError instanceof Error
    ? lastError
    : new Error('서버 연결을 확인하지 못했습니다. 다시 시도해주세요.');
}

export async function recommend(request: RecommendRequest): Promise<RecommendResponse> {
  const signedIn = Boolean(cachedAccount());
  const response = await requestJson<RecommendResponse>(
    API_BASE + '/recommend',
    {
      method: 'POST',
      headers: withRuntimeKeys({
        'Content-Type': 'application/json',
        ...(signedIn ? { 'X-AI-Comment-Private-History': '1' } : {}),
      }),
      body: JSON.stringify({
        ...request,
        persona_id: request.persona_id ?? getSelectedPersona(),
        custom_persona: request.custom_persona ?? (
          (request.persona_id ?? getSelectedPersona()).startsWith('custom_')
            ? getCustomPersona(request.persona_id ?? getSelectedPersona())
            : undefined
        ),
      }),
    },
    '추천 요청이 실패했습니다',
  );
  if (!signedIn) {
    // Render Free's ephemeral SQLite can be lost after sleep/redeploy.
    // Guest recovery stays on this browser only and cannot masquerade as member data.
    saveGuestBrowserAnalysis(response, request);
  }
  if (signedIn) {
    try {
      await savePrivateAnalysis(response, request.post_text || request.youtube_url || '', request.additional_context);
    } catch (error) {
      // Generation has succeeded; preserve visible results and disclose failed private persistence.
      return { ...response, private_save_warning: error instanceof Error ? error.message : '계정 저장 실패' };
    }
  }
  return response;
}

export async function getVideoPreview(url: string): Promise<VideoPreviewData> {
  const params = new URLSearchParams({ url });
  return requestJson<VideoPreviewData>(
    `${API_BASE}/videos/preview?${params.toString()}`,
    { headers: withRuntimeKeys() },
    '영상 정보를 불러오지 못했습니다',
  );
}

export async function listAnalyses(limit = 3): Promise<AnalysisSummary[]> {
  if (cachedAccount()) return listPrivateAnalyses(limit);
  const local = listGuestBrowserAnalyses(limit);
  // Prefer the immediately available browser copy. It survives Render Free idle
  // restarts and avoids blocking the dashboard on a cold backend wake-up.
  if (local.length) return local;
  const params = new URLSearchParams({ limit: String(limit) });
  const body = await requestJson<{ items: AnalysisSummary[] }>(
    `${API_BASE}/analyses?${params.toString()}`,
    undefined,
    '최근 분석 기록을 불러오지 못했습니다',
  );
  return body.items;
}

export async function getAnalysis(analysisId: string): Promise<AnalysisDetail> {
  if (cachedAccount()) return getPrivateAnalysis(analysisId);
  const cached = getGuestBrowserAnalysis(analysisId);
  if (cached) return cached;
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
  if (cachedAccount()) return listPrivateComments(filters);
  const params = new URLSearchParams();
  if (filters.query) params.set('query', filters.query);
  if (filters.type) params.set('type', filters.type);
  if (filters.category && filters.category !== 'auto') params.set('category', filters.category);
  if (filters.minScore != null) params.set('min_score', String(filters.minScore));
  params.set('limit', String(filters.limit ?? 25));
  params.set('offset', String(filters.offset ?? 0));

  return requestJson<CommentsResponse>(`${API_BASE}/comments?${params.toString()}`, undefined, '댓글 목록을 불러오지 못했습니다');
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  if (cachedAccount()) return getPrivateDashboardSummary();
  return requestJson<DashboardSummary>(`${API_BASE}/dashboard/summary`, undefined, '대시보드 요약을 불러오지 못했습니다');
}

export async function sendFeedback(recommendationId: string, useful: boolean): Promise<FeedbackValue> {
  if (cachedAccount()) return sendPrivateFeedback(recommendationId, useful);
  const body = await requestJson<{ id: string; feedback: FeedbackValue }>(
    `${API_BASE}/recommendations/${encodeURIComponent(recommendationId)}/feedback`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ useful }) },
    '피드백 저장에 실패했습니다',
  );
  return body.feedback;
}

export async function getYouTubeDemoStatus(): Promise<YouTubeDemoStatus> {
  return requestJson<YouTubeDemoStatus>(
    `${API_BASE}/youtube/demo/status`,
    undefined,
    '데모 계정 상태를 확인하지 못했습니다',
  );
}

export async function getYouTubeOAuthStatus(): Promise<YouTubeOAuthStatus> {
  return requestJson<YouTubeOAuthStatus>(
    `${API_BASE}/youtube/oauth/status`,
    { headers: withYouTubeOAuth() },
    'YouTube 계정 연결 상태를 확인하지 못했습니다',
  );
}

export async function startYouTubeOAuth(): Promise<{ authorization_url: string }> {
  return requestJson<{ authorization_url: string }>(
    `${API_BASE}/youtube/oauth/start`,
    { headers: withYouTubeOAuth() },
    'YouTube OAuth 로그인을 시작하지 못했습니다',
  );
}

export async function disconnectYouTubeOAuth(): Promise<YouTubeOAuthStatus> {
  return requestJson<YouTubeOAuthStatus>(
    `${API_BASE}/youtube/oauth/disconnect`,
    { method: 'POST', headers: withYouTubeOAuth() },
    'YouTube 계정 연결 해제에 실패했습니다',
  );
}

export async function publishYouTubeComment(request: {
  video_id: string;
  channel_id: string;
  comment: string;
  recommendation_id?: string;
}): Promise<YouTubeCommentPublishResponse> {
  const mode = getAccountMode();
  const headers =
    mode === 'personal'
      ? withYouTubeOAuth({
          'Content-Type': 'application/json',
          'X-AI-Comment-Account-Mode': mode,
        })
      : {
          'Content-Type': 'application/json',
          'X-AI-Comment-Account-Mode': mode,
        };

  const posted = await requestJson<YouTubeCommentPublishResponse>(
    `${API_BASE}/youtube/comments`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify(request),
    },
    'YouTube 댓글 게시에 실패했습니다',
  );
  // Save a second receipt outside the server's temporary SQLite database.
  // This is device-local recovery, not an account-wide durable database.
  const saved = backUpPostedComment(posted, request.recommendation_id, mode);
  let cloudSaved: boolean | undefined;
  let cloudWarning: string | undefined;
  if (mode === 'personal' && posted.posted && posted.comment_id && posted.video_id && cachedAccount()) {
    try {
      await savePrivatePublishedReceipts([{
        video_id: posted.video_id,
        comment_id: posted.comment_id,
        comment: posted.comment,
        comment_url: posted.comment_url || null,
        published_at: new Date().toISOString(),
        recommendation_id: request.recommendation_id ?? null,
      }]);
      cloudSaved = true;
    } catch (error) {
      // Never turn an already-published YouTube comment into a failed POST or
      // encourage retries. Cloud receipt and server tracking are separate.
      cloudSaved = false;
      cloudWarning = error instanceof Error ? error.message : '클라우드 백업 실패';
    }
  }
  return { ...posted, browser_backup_saved: saved,
    cloud_backup_saved: cloudSaved, cloud_backup_warning: cloudWarning };
}


export interface AuthenticatedYouTubeIdentity {
  connected: boolean;
  channel_id: string;
  channel_title: string;
}

export async function getAuthenticatedYouTubeIdentity(): Promise<AuthenticatedYouTubeIdentity> {
  return requestJson<AuthenticatedYouTubeIdentity>(
    API_BASE + '/account/youtube-identity',
    { headers: withYouTubeOAuth(withRuntimeKeys()) },
    '현재 연결된 YouTube 계정을 확인하지 못했습니다',
  );
}

export async function listMyComments(): Promise<PublishedCommentsResponse> {
  const mode = getAccountMode();
  try {
    const response = await requestJson<PublishedCommentsResponse>(
      `${API_BASE}/my-comments`,
      { headers: withYouTubeOAuth(withRuntimeKeys()) },
      '내가 단 댓글을 불러오지 못했습니다',
    );
    backUpServerComments(response.items);
    return applySavedPublicMetrics(mergePostedBackup(response, mode), mode);
  } catch (error) {
    const backup = readPostedBackup(mode);
    if (!backup.length) throw error;
    return applySavedPublicMetrics(mergePostedBackup({
      summary: {
        tracked_count: 0, measured_count: 0, missing_count: 0, average_likes: null,
        replied_rate: null, prediction_pair_count: 0, prediction_spearman: null, by_type: [],
      }, items: [], backend_unavailable: true,
    }, mode), mode);
  }
}

export async function refreshMyComments(): Promise<PublishedCommentsResponse> {
  const response = await requestJson<PublishedCommentsResponse>(
    `${API_BASE}/my-comments/refresh`,
    { method: 'POST', headers: withYouTubeOAuth(withRuntimeKeys()) },
    '실제 반응을 새로 확인하지 못했습니다',
  );
  backUpServerComments(response.items);
  return applySavedPublicMetrics(mergePostedBackup(response, getAccountMode()), getAccountMode());
}

/** Public read-only lookup for local comment receipts; no OAuth or re-posting. */
export async function lookupPublicCommentMetrics(
  comments: Array<{ video_id: string; comment_id: string }>,
): Promise<PublicMetricResponse> {
  return requestJson<PublicMetricResponse>(
    API_BASE + '/my-comments/public-metrics',
    {
      method: 'POST',
      headers: withRuntimeKeys({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ comments }),
    },
    '브라우저 백업 댓글의 공개 반응을 조회하지 못했습니다',
  );
}

/** Mutations affect the real YouTube comment, not just the local receipt. */
export async function editPublishedYouTubeComment(
  commentId: string, text: string,
): Promise<{ updated: boolean; comment_id: string; comment: string; tracking_saved: boolean }> {
  return requestJson(
    `${API_BASE}/my-comments/${encodeURIComponent(commentId)}`,
    {
      method: 'PUT',
      headers: withYouTubeOAuth(withRuntimeKeys({
        'Content-Type': 'application/json',
        'X-AI-Comment-Account-Mode': 'personal',
      })),
      body: JSON.stringify({ text }),
    },
    'YouTube 댓글 수정에 실패했습니다',
  );
}

export async function deletePublishedYouTubeComment(
  commentId: string,
): Promise<{ deleted: boolean; comment_id: string; tracking_removed: boolean }> {
  return requestJson(
    `${API_BASE}/my-comments/${encodeURIComponent(commentId)}`,
    {
      method: 'DELETE',
      headers: withYouTubeOAuth(withRuntimeKeys({
        'X-AI-Comment-Account-Mode': 'personal',
      })),
    },
    'YouTube 댓글 삭제에 실패했습니다',
  );
}

export async function recoverPublishedBatch(
  comments: Array<{ video_id: string; comment_id: string }>,
): Promise<{
  owner_channel_id: string;
  registered_count: number;
  failed_count: number;
  items: Array<{
    id: string;
    video_id: string;
    comment_id: string;
    comment: string;
    comment_url: string | null;
    published_at: string;
  }>;
  failures: Array<{ comment_id: string; reason: string }>;
  storage_persistent: boolean;
}> {
  return requestJson(
    API_BASE + '/my-comments/recover/batch',
    {
      method: 'POST',
      headers: withYouTubeOAuth({
        'Content-Type': 'application/json',
        'X-AI-Comment-Account-Mode': 'personal',
      }),
      body: JSON.stringify({ comments }),
    },
    '기존 YouTube 댓글 일괄 등록에 실패했습니다',
  );
}

export async function claimLegacyPublishedHistory(): Promise<{ checked: number; restored: number; remaining: number }> {
  return requestJson(
    API_BASE + '/my-comments/claim-legacy',
    { method: 'POST', headers: withYouTubeOAuth(withRuntimeKeys()) },
    '이전 서버 댓글 기록 연결에 실패했습니다',
  );
}

export async function recoverPublishedComment(
  videoId: string, commentId: string,
): Promise<{ tracked: true; id: string; video_id: string; comment_id: string }> {
  return requestJson(
    `${API_BASE}/my-comments/recover`,
    {
      method: 'POST',
      headers: withYouTubeOAuth({ 'Content-Type': 'application/json', 'X-AI-Comment-Account-Mode': 'personal' }),
      body: JSON.stringify({ video_id: videoId, comment_id: commentId }),
    },
    'YouTube 댓글을 추적 대상으로 복구하지 못했습니다',
  );
}

/** Read publicly available top-level comments; works without an LLM. */
export async function getAudienceObserved(
  videoId: string,
  analysisId?: string | null,
): Promise<AudienceObservationReport> {
  const query = new URLSearchParams({ video_id: videoId });
  if (analysisId && !cachedAccount()) query.set('analysis_id', analysisId);
  return requestJson<AudienceObservationReport>(
    `${API_BASE}/audience/observed?${query.toString()}`,
    { headers: withRuntimeKeys() },
    '실제 댓글 반응을 읽어오지 못했습니다',
  );
}

/** Protected persistence; API always re-fetches live comments from YouTube. */
export async function saveAudienceSnapshot(
  videoId: string,
  analysisId?: string | null,
): Promise<{ snapshot: AudienceSnapshotSummary; report: AudienceObservationReport }> {
  const query = new URLSearchParams({ video_id: videoId });
  // Supabase-private analyses are not present in the server's shared SQLite store.
  // Store public observations without leaking or referencing private analysis IDs.
  if (analysisId && !cachedAccount()) query.set('analysis_id', analysisId);
  return requestJson(
    `${API_BASE}/audience/observations?${query.toString()}`,
    { method: 'POST', headers: withRuntimeKeys() },
    '실제 댓글 스냅샷을 저장하지 못했습니다',
  );
}

export async function listAudienceSnapshots(videoId: string): Promise<{ items: AudienceSnapshotSummary[] }> {
  return requestJson(
    `${API_BASE}/audience/observations/${encodeURIComponent(videoId)}`,
    { headers: withRuntimeKeys() },
    '저장된 실측 기록을 조회하지 못했습니다',
  );
}

export async function getCreatorInbox(url: string, order: 'relevance' | 'time' = 'relevance'): Promise<CreatorInboxResponse> {
  const params = new URLSearchParams({ url, order });
  return requestJson<CreatorInboxResponse>(
    `${API_BASE}/creator/inbox?${params.toString()}`,
    { headers: withRuntimeKeys() },
    '받은 댓글을 불러오지 못했습니다',
  );
}

export async function getReplyDrafts(request: {
  comment: string;
  category: string;
  video_title?: string;
}): Promise<ReplyDraftsResponse> {
  return requestJson<ReplyDraftsResponse>(
    `${API_BASE}/creator/inbox/reply-drafts`,
    {
      method: 'POST',
      headers: withRuntimeKeys({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(request),
    },
    '답글 초안을 만들지 못했습니다',
  );
}

export async function postCreatorReply(request: { parent_id: string; text: string }): Promise<CreatorReplyResponse> {
  return requestJson<CreatorReplyResponse>(
    `${API_BASE}/creator/inbox/replies`,
    {
      method: 'POST',
      headers: withYouTubeOAuth({
        'Content-Type': 'application/json',
        'X-AI-Comment-Account-Mode': getAccountMode(),
      }),
      body: JSON.stringify(request),
    },
    'YouTube 답글 게시에 실패했습니다',
  );
}

/** OAuth-verified owned video inventory; never fetched for another channel. */
export async function getMyVideos(): Promise<OwnedVideoPerformanceResponse> {
  return requestJson<OwnedVideoPerformanceResponse>(
    API_BASE + '/my-videos',
    { headers: withYouTubeOAuth({ 'X-AI-Comment-Account-Mode': getAccountMode() }) },
    '내 영상 성과를 불러오지 못했습니다',
  );
}

/** Read-only Google API sync; POST protects rate limits and records snapshots. */
export async function refreshMyVideos(): Promise<OwnedVideoPerformanceResponse> {
  return requestJson<OwnedVideoPerformanceResponse>(
    API_BASE + '/my-videos/refresh',
    { method: 'POST', headers: withYouTubeOAuth({ 'X-AI-Comment-Account-Mode': getAccountMode() }) },
    '영상 성과를 새로 확인하지 못했습니다',
  );
}

/** Older video must be owned by the connected OAuth channel. */
export async function trackMyVideo(videoId: string): Promise<OwnedVideoPerformanceResponse> {
  return requestJson<OwnedVideoPerformanceResponse>(
    API_BASE + '/my-videos/track',
    {
      method: 'POST',
      headers: withYouTubeOAuth({
        'Content-Type': 'application/json',
        'X-AI-Comment-Account-Mode': getAccountMode(),
      }),
      body: JSON.stringify({ video_id: videoId }),
    },
    '영상을 추적 목록에 추가하지 못했습니다',
  );
}

/** Post a direct reply to a YouTube top-level comment using the connected viewer account. */
export async function postViewerReply(request: { parent_id: string; text: string }): Promise<CreatorReplyResponse> {
  return requestJson<CreatorReplyResponse>(
    `${API_BASE}/viewer/replies`,
    { method: 'POST', headers: withYouTubeOAuth({ 'Content-Type': 'application/json', 'X-AI-Comment-Account-Mode': getAccountMode() }), body: JSON.stringify(request) },
    '대댓글 게시에 실패했습니다',
  );
}

export interface AutoReplyCandidate {
  parent_id: string;
  author: string;
  comment: string;
  category: string;
  match_score: number;
  like_count: number;
}
export interface AutoReplyCandidatesResponse {
  video: { video_id: string; title: string; channel: string };
  items: AutoReplyCandidate[];
  scanned_count: number;
}

/** YouTube-verified reply targets, not client-authored comment text. */
export async function getAutoReplyCandidates(url: string): Promise<AutoReplyCandidatesResponse> {
  const params = new URLSearchParams({ url });
  return requestJson<AutoReplyCandidatesResponse>(
    `${API_BASE}/viewer/auto-replies/candidates?${params.toString()}`,
    { headers: withYouTubeOAuth(withRuntimeKeys()) },
    '대댓글을 달 댓글 후보를 찾지 못했습니다',
  );
}

export async function suggestAutoReply(request: {
  video_id: string;
  parent_id: string;
}): Promise<{ video_id: string; parent_id: string; drafts: string[] }> {
  return requestJson(
    `${API_BASE}/viewer/auto-replies/suggest`,
    {
      method: 'POST',
      headers: withYouTubeOAuth(withRuntimeKeys({ 'Content-Type': 'application/json' })),
      body: JSON.stringify(request),
    },
    'AI 대댓글 추천에 실패했습니다',
  );
}

/** Protected aggregated record of inputs used before LLM generation. */
export async function getModelDataProgress(): Promise<import("../types/comment").ModelDataProgress> {
  return requestJson<import("../types/comment").ModelDataProgress>(
    API_BASE + "/model/data-progress",
    { headers: withRuntimeKeys() },
    "데이터 모델 현황을 불러오지 못했습니다",
  );
}
