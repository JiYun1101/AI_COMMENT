/**
 * Supabase GoTrue + PostgREST account client without another runtime dependency.
 * Publishable key is public by design. All account tables enforce owner-only RLS.
 * Never pass provider service_role/secret credentials to a browser.
 */
import type { AnalysisDetail, AnalysisSummary, CommentRecommendation, DashboardComment, DashboardSummary, RecommendResponse } from '../types/comment';

const base = (import.meta.env.VITE_SUPABASE_URL || 'https://tyhpdlxbnsecjbyhdzuw.supabase.co').replace(/\/$/, '');
const publicKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || 'sb_publishable_qdY183h2wysCnc5WJen_oQ_K6Nkq3M4';
const storageKey = 'ai-comment.supabase-account-session.v1';
const changedEvent = 'ai-comment:auth-changed';

export interface AuthAccount {
  id: string;
  email: string;
  user_metadata?: { nickname?: string };
  email_confirmed_at?: string | null;
}
interface Credentials extends Record<string, unknown> {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  user: AuthAccount;
}
export interface AccountProfile {
  user_id: string;
  nickname: string;
  created_at: string;
}
interface SavedRow {
  local_analysis_id: string;
  title: string;
  video_id: string | null;
  category: string | null;
  created_at: string;
  payload: SavedPayload;
}
interface SavedPayload {
  source_type: 'youtube' | 'manual';
  source_text: string;
  youtube_url: string | null;
  channel: string | null;
  thumbnail_url: string | null;
  additional_context: string | null;
  requested_count: number | null;
  context_summary: RecommendResponse['context'];
  recommendations: CommentRecommendation[];
}
let refreshPromise: Promise<Credentials | null> | null = null;

function readSession(): Credentials | null {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return null;
    const value = JSON.parse(raw) as Credentials;
    return typeof value.access_token === 'string' && typeof value.refresh_token === 'string'
      && typeof value.user?.id === 'string' && Number.isFinite(value.expires_at) ? value : null;
  } catch {
    return null;
  }
}
function writeSession(value: Credentials | null) {
  if (value) localStorage.setItem(storageKey, JSON.stringify(value));
  else localStorage.removeItem(storageKey);
  window.dispatchEvent(new Event(changedEvent));
}
export function cachedAccount(): AuthAccount | null {
  return readSession()?.user ?? null;
}
export function subscribeToAccountChange(callback: () => void): () => void {
  window.addEventListener(changedEvent, callback);
  window.addEventListener('storage', callback);
  return () => {
    window.removeEventListener(changedEvent, callback);
    window.removeEventListener('storage', callback);
  };
}

async function parse<T>(response: Response): Promise<T> {
  if (response.ok) return await response.json() as T;
  const error = await response.json().catch(() => ({})) as { msg?: string; message?: string; error_description?: string; error?: string; code?: string };
  if (response.status === 429) throw new Error('요청이 너무 많습니다. 잠시 후 다시 시도해주세요.');
  const raw = error.msg || error.message || error.error_description || error.error || '계정 요청에 실패했습니다.';
  const translated: Record<string, string> = {
    'Invalid login credentials': '이메일 또는 비밀번호가 올바르지 않습니다.',
    'Email not confirmed': '이메일 인증을 완료한 뒤 로그인해주세요.',
    'User already registered': '이미 가입된 이메일입니다.',
    'Password should be at least 6 characters': '비밀번호 길이를 확인해주세요.',
    'Email rate limit exceeded': '이메일 요청 제한에 도달했습니다. 잠시 후 다시 시도해주세요.',
  };
  throw new Error(translated[raw] ?? raw);
}
async function authFetch<T>(path: string, method = 'GET', body?: unknown, token?: string): Promise<T> {
  const result = await fetch(base + '/auth/v1' + path, {
    method,
    headers: {
      apikey: publicKey,
      ...(token ? { Authorization: 'Bearer ' + token } : {}),
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  return parse<T>(result);
}
function fromAuthResponse(response: Record<string, unknown>) {
  if (!response.access_token || !response.refresh_token) return false;
  const token = response as unknown as { access_token: string; refresh_token: string; expires_in?: number; user: AuthAccount };
  writeSession({
    access_token: token.access_token,
    refresh_token: token.refresh_token,
    expires_at: Math.floor(Date.now() / 1000) + (token.expires_in ?? 3600),
    user: token.user,
  });
  return true;
}
async function token(): Promise<string> {
  const session = readSession();
  if (!session) throw new Error('로그인이 필요합니다.');
  if (session.expires_at > Date.now() / 1000 + 90) return session.access_token;
  if (!refreshPromise) {
    refreshPromise = authFetch<Record<string, unknown>>('/token?grant_type=refresh_token', 'POST', { refresh_token: session.refresh_token })
      .then((result) => {
        if (!fromAuthResponse(result)) throw new Error('로그인 세션 갱신에 실패했습니다.');
        return readSession();
      }).catch(() => {
        writeSession(null);
        throw new Error('로그인이 만료됐습니다. 다시 로그인해주세요.');
      }).finally(() => { refreshPromise = null; });
  }
  const updated = await refreshPromise;
  if (!updated) throw new Error('로그인이 필요합니다.');
  return updated.access_token;
}
async function table<T>(tableName: 'ai_comment_profiles' | 'ai_comment_saved_analyses', suffix: string, method = 'GET', body?: unknown): Promise<T> {
  const access = await token();
  const result = await fetch(base + '/rest/v1/' + tableName + suffix, {
    method,
    headers: {
      apikey: publicKey,
      Authorization: 'Bearer ' + access,
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      Prefer: method === 'POST' ? 'resolution=merge-duplicates,return=representation' : 'return=representation',
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (result.status === 204) return [] as T;
  return parse<T>(result);
}

export async function getAccount(): Promise<AuthAccount | null> {
  if (!readSession()) return null;
  try {
    const user = await authFetch<AuthAccount>('/user', 'GET', undefined, await token());
    const session = readSession();
    if (session) writeSession({ ...session, user });
    return user;
  } catch {
    writeSession(null);
    return null;
  }
}
export async function signUpAccount(email: string, password: string, nickname: string): Promise<'confirmed' | 'verify'> {
  const cleanNick = nickname.trim();
  if (cleanNick.length < 2 || cleanNick.length > 32) throw new Error('닉네임은 2~32자로 입력해주세요.');
  if (password.length < 8) throw new Error('비밀번호는 최소 8자 이상이어야 합니다.');
  const response = await authFetch<Record<string, unknown>>('/signup?redirect_to=' + encodeURIComponent(window.location.origin + '/account/auth'), 'POST', {
    email: email.trim().toLowerCase(), password,
    data: { nickname: cleanNick },
  });
  if (fromAuthResponse(response)) {
    await ensureAccountProfile();
    return 'confirmed';
  }
  return 'verify';
}
export async function signInAccount(email: string, password: string): Promise<void> {
  const previousUser = cachedAccount()?.id;
  const result = await authFetch<Record<string, unknown>>('/token?grant_type=password', 'POST', {
    email: email.trim().toLowerCase(), password,
  });
  if (!fromAuthResponse(result)) throw new Error('로그인 세션을 받지 못했습니다.');
  if (previousUser && previousUser !== cachedAccount()?.id) {
    for (const key of ['ai-comment.youtube-api-key','ai-comment.openai-api-key','ai-comment.youtube-oauth-client-id','ai-comment.youtube-oauth-client-secret','ai-comment.server-access-token','ai-comment.custom-personas.v1']) localStorage.removeItem(key);
    localStorage.setItem('ai-comment.account-mode','demo');
  }
  await ensureAccountProfile();
}
export async function signOutAccount(): Promise<void> {
  const session = readSession();
  writeSession(null);
  // Credentials and server pairing sessions are browser-scoped; never keep them across accounts.
  for (const key of [
    'ai-comment.custom-personas.v1', 'ai-comment.persona',
    'ai-comment.youtube-api-key', 'ai-comment.openai-api-key',
    'ai-comment.youtube-oauth-client-id', 'ai-comment.youtube-oauth-client-secret',
    'ai-comment.server-access-token',
  ]) localStorage.removeItem(key);
  localStorage.setItem('ai-comment.account-mode', 'demo');
  if (session) await authFetch<Record<string, unknown>>('/logout', 'POST', {}, session.access_token).catch(() => undefined);
}
export async function recoverAccount(email: string): Promise<void> {
  const redirect = encodeURIComponent(window.location.origin + '/account/reset');
  await authFetch<Record<string, unknown>>('/recover?redirect_to=' + redirect, 'POST', { email: email.trim().toLowerCase() });
}
export async function acceptAuthRedirect(): Promise<'recovery' | 'signup' | null> {
  const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const accessToken = fragment.get('access_token');
  const refreshToken = fragment.get('refresh_token');
  const kind = fragment.get('type');
  if (!accessToken || !refreshToken || (kind !== 'recovery' && kind !== 'signup' && kind !== 'email')) return null;
  const user = await authFetch<AuthAccount>('/user', 'GET', undefined, accessToken);
  writeSession({
    access_token: accessToken,
    refresh_token: refreshToken,
    expires_at: Math.floor(Date.now() / 1000) + Number(fragment.get('expires_in') || 3600),
    user,
  });
  window.history.replaceState(window.history.state, '', window.location.pathname);
  return kind === 'recovery' ? 'recovery' : 'signup';
}
export async function changeAccountPassword(password: string): Promise<void> {
  if (password.length < 8) throw new Error('비밀번호는 8자 이상이어야 합니다.');
  await authFetch<unknown>('/user', 'PUT', { password }, await token());
}
export async function ensureAccountProfile(): Promise<AccountProfile | null> {
  const session = readSession();
  if (!session) return null;
  const id = encodeURIComponent(session.user.id);
  const current = await table<AccountProfile[]>('ai_comment_profiles', '?user_id=eq.' + id + '&select=user_id,nickname,created_at');
  if (current[0]) return current[0];
  const nickname = (session.user.user_metadata?.nickname || session.user.email.split('@')[0]).slice(0, 32);
  const inserted = await table<AccountProfile[]>('ai_comment_profiles', '?on_conflict=user_id', 'POST', {
    user_id: session.user.id, nickname: nickname.length >= 2 ? nickname : '회원',
  });
  return inserted[0] ?? null;
}
export async function updateAccountNickname(nickname: string): Promise<AccountProfile> {
  const session = readSession();
  if (!session) throw new Error('로그인이 필요합니다.');
  const clean = nickname.trim();
  if (clean.length < 2 || clean.length > 32) throw new Error('닉네임은 2~32자여야 합니다.');
  const result = await table<AccountProfile[]>('ai_comment_profiles', '?user_id=eq.' + encodeURIComponent(session.user.id),
    'PATCH', { nickname: clean, updated_at: new Date().toISOString() });
  if (!result[0]) throw new Error('프로필을 수정하지 못했습니다.');
  return result[0];
}
export async function savePrivateAnalysis(response: RecommendResponse, requestText: string, additionalContext?: string): Promise<void> {
  const session = readSession();
  if (!session) return;
  const video = response.youtube_context;
  const data: SavedPayload = {
    source_type: video ? 'youtube' : 'manual',
    source_text: video?.title || requestText.slice(0, 400),
    youtube_url: video?.url ?? null, channel: video?.channel ?? null,
    thumbnail_url: video?.thumbnail_url ?? null,
    requested_count: response.generation.requested_count,
    additional_context: additionalContext || null,
    context_summary: response.context,
    recommendations: response.recommendations,
  };
  await table<SavedRow[]>('ai_comment_saved_analyses', '?on_conflict=user_id,local_analysis_id', 'POST', {
    user_id: session.user.id,
    local_analysis_id: response.analysis_id,
    title: video?.title || requestText.slice(0, 150),
    video_id: video?.video_id ?? null,
    category: response.resolved_category,
    payload: data,
  });
}
async function accountAnalyses(limit = 500): Promise<SavedRow[]> {
  const id = cachedAccount()?.id;
  if (!id) throw new Error('로그인이 필요합니다.');
  return table<SavedRow[]>('ai_comment_saved_analyses', '?user_id=eq.' + encodeURIComponent(id) +
    '&select=local_analysis_id,title,video_id,category,created_at,payload&order=created_at.desc&limit=' + Math.min(500,limit));
}
function toSummary(row: SavedRow): AnalysisSummary {
  const recs = row.payload.recommendations;
  const scores = recs.map(x => x.predicted_score);
  return {
    id: row.local_analysis_id, source_type: row.payload.source_type,
    source_text: row.payload.source_text, youtube_url: row.payload.youtube_url,
    video_id: row.video_id, video_title: row.payload.source_type === 'youtube' ? row.title : null,
    channel: row.payload.channel, thumbnail_url: row.payload.thumbnail_url,
    category: row.category || '', created_at: row.created_at,
    recommendation_count: recs.length,
    average_score: scores.length ? scores.reduce((a,b)=>a+b,0)/scores.length : 0,
    requested_count: row.payload.requested_count,
    additional_context: row.payload.additional_context,
  };
}
export async function listPrivateAnalyses(limit: number): Promise<AnalysisSummary[]> {
  return (await accountAnalyses(limit)).map(toSummary);
}
export async function getPrivateAnalysis(id: string): Promise<AnalysisDetail> {
  const current = (await accountAnalyses()).find(x=>x.local_analysis_id===id);
  if (!current) throw new Error('내 계정에서 분석 기록을 찾지 못했습니다.');
  const summary = toSummary(current);
  return {
    id: summary.id, source_type: summary.source_type, source_text: summary.source_text,
    youtube_url: summary.youtube_url, video_id: summary.video_id,
    video_title: summary.video_title, channel: summary.channel,
    thumbnail_url: summary.thumbnail_url, category: summary.category, created_at: summary.created_at,
    requested_count: summary.requested_count, additional_context: summary.additional_context,
    recommendations: current.payload.recommendations, context_summary: current.payload.context_summary,
  };
}
export async function getPrivateDashboardSummary(): Promise<DashboardSummary> {
  const rows = await accountAnalyses();
  const all = rows.flatMap(x=>x.payload.recommendations);
  const feedback = all.filter(x=>x.feedback != null);
  const useful = feedback.filter(x=>x.feedback==='useful').length;
  const scores = all.map(x=>x.predicted_score);
  return {
    analysis_count: rows.length,
    recommendation_count: all.length,
    average_score: scores.length ? scores.reduce((a,b)=>a+b,0)/scores.length : 0,
    feedback_count: feedback.length,
    helpful_rate: feedback.length ? 100*useful/feedback.length : null,
  };
}
export async function listPrivateComments(filters: {
  query?:string;type?:string;category?:string;minScore?:number;limit?:number;offset?:number;
}): Promise<{total:number;items:DashboardComment[]}> {
  const rows = await accountAnalyses();
  const query = (filters.query || '').toLocaleLowerCase();
  const flat = rows.flatMap(row=>row.payload.recommendations.map(rec=>({
    id: rec.id, analysis_id: row.local_analysis_id, rank: rec.rank, type: rec.type,
    comment: rec.comment, predicted_score: rec.predicted_score, feedback: rec.feedback || null,
    created_at: row.created_at, category: row.category || '', source_type: row.payload.source_type,
    video_title: row.payload.source_type === 'youtube' ? row.title : null, channel: row.payload.channel,
  } satisfies DashboardComment)));
  const selected = flat.filter(x=>
    (!query || x.comment.toLocaleLowerCase().includes(query)) &&
    (!filters.type || x.type===filters.type) &&
    (!filters.category || filters.category==='auto' || x.category===filters.category) &&
    (filters.minScore == null || x.predicted_score >= filters.minScore));
  return { total: selected.length, items: selected.slice(filters.offset||0,(filters.offset||0)+(filters.limit||25)) };
}
export async function sendPrivateFeedback(recommendationId: string, useful: boolean): Promise<'useful'|'not_useful'> {
  const rows = await accountAnalyses();
  const row = rows.find(x=>x.payload.recommendations.some(rec=>rec.id===recommendationId));
  if (!row) throw new Error('내 계정에서 추천 기록을 찾지 못했습니다.');
  const updated = {
    ...row.payload,
    recommendations: row.payload.recommendations.map(rec=>rec.id===recommendationId
      ? {...rec,feedback:useful ? 'useful' as const : 'not_useful' as const} : rec),
  };
  await table<SavedRow[]>('ai_comment_saved_analyses',
    '?local_analysis_id=eq.'+encodeURIComponent(row.local_analysis_id), 'PATCH',{payload:updated});
  return useful?'useful':'not_useful';
}
