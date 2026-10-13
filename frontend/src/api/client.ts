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
} from '../types/comment';
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
export const DEFAULT_OPENAI_MODEL = 'gpt-5.6-luna';
export const YOUTUBE_OAUTH_REDIRECT_URI = `${API_BASE}/youtube/oauth/callback`;

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
  return [
    'none',
    'polite_viewer',
    'friendly_viewer',
    'warm_supporter',
    'calm_analyst',
    'playful_casual',
  ].includes(value)
    ? value
    : 'none';
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
  return getStoredValue(OPENAI_MODEL_STORAGE_KEY) || DEFAULT_OPENAI_MODEL;
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
  };
}

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
  const health = await requestJson<ServiceHealth>(
    `${API_BASE}/health`,
    undefined,
    '서비스 상태를 확인하지 못했습니다',
  );
  return {
    ...health,
    llm:
      getAccountMode() === 'personal' && getStoredOpenAIApiKey()
        ? { ...health.llm, ready: true, provider: 'openai_responses_api', model: getStoredOpenAIModel(), missing: [] }
        : health.llm,
    youtube:
      getAccountMode() === 'personal' && getStoredYouTubeApiKey()
        ? { ...health.youtube, configured: true }
        : health.youtube,
  };
}

export async function recommend(request: RecommendRequest): Promise<RecommendResponse> {
  return requestJson<RecommendResponse>(
    `${API_BASE}/recommend`,
    {
      method: 'POST',
      headers: withRuntimeKeys({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        ...request,
        persona_id: request.persona_id ?? getSelectedPersona(),
      }),
    },
    '추천 요청이 실패했습니다',
  );
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

  return requestJson<CommentsResponse>(`${API_BASE}/comments?${params.toString()}`, undefined, '댓글 목록을 불러오지 못했습니다');
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return requestJson<DashboardSummary>(`${API_BASE}/dashboard/summary`, undefined, '대시보드 요약을 불러오지 못했습니다');
}

export async function sendFeedback(recommendationId: string, useful: boolean): Promise<FeedbackValue> {
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
  return { ...posted, browser_backup_saved: saved };
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
    return mergePostedBackup(response, mode);
  } catch (error) {
    const backup = readPostedBackup(mode);
    if (!backup.length) throw error;
    return mergePostedBackup({
      summary: {
        tracked_count: 0, measured_count: 0, missing_count: 0, average_likes: null,
        replied_rate: null, prediction_pair_count: 0, prediction_spearman: null, by_type: [],
      }, items: [], backend_unavailable: true,
    }, mode);
  }
}

export async function refreshMyComments(): Promise<PublishedCommentsResponse> {
  const response = await requestJson<PublishedCommentsResponse>(
    `${API_BASE}/my-comments/refresh`,
    { method: 'POST', headers: withYouTubeOAuth(withRuntimeKeys()) },
    '실제 반응을 새로 확인하지 못했습니다',
  );
  backUpServerComments(response.items);
  return mergePostedBackup(response, getAccountMode());
}

export async function recoverPublishedBatch(
  comments: Array<{ video_id: string; comment_id: string }>,
): Promise<{
  owner_channel_id: string;
  registered_count: number;
  failed_count: number;
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
  if (analysisId) query.set('analysis_id', analysisId);
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
  if (analysisId) query.set('analysis_id', analysisId);
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
