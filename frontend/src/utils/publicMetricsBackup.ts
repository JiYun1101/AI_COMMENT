/** Read-only YouTube counters retained next to local posting receipts.
 * These do not prove authorship and are not promoted into the server account DB.
 */
import type { AccountMode, PublishedComment, PublishedCommentsResponse } from '../types/comment';

export interface PublicMetricRow {
  video_id: string;
  comment_id: string;
  status: 'active' | 'unavailable';
  like_count: number | null;
  reply_count: number | null;
}
export interface PublicMetricResponse {
  checked_count: number;
  observed_count: number;
  checked_at: string;
  items: PublicMetricRow[];
  storage: 'browser_only';
}
type SavedMetric = PublicMetricRow & { account_mode: AccountMode; checked_at: string };

const KEY = 'ai-comment.public-comment-metrics.v1';
const CAP = 500;
const validId = (x: unknown) => typeof x === 'string' && /^[A-Za-z0-9_.-]{5,100}$/.test(x);
const validVideo = (x: unknown) => typeof x === 'string' && /^[A-Za-z0-9_-]{11}$/.test(x);

function validMetric(x: unknown): x is SavedMetric {
  if (!x || typeof x !== 'object') return false;
  const r = x as Partial<SavedMetric>;
  return validId(r.comment_id) && validVideo(r.video_id)
    && (r.account_mode === 'personal' || r.account_mode === 'demo')
    && (r.status === 'active' || r.status === 'unavailable')
    && typeof r.checked_at === 'string' && Number.isFinite(Date.parse(r.checked_at))
    && (r.like_count == null || (Number.isSafeInteger(r.like_count) && r.like_count >= 0))
    && (r.reply_count == null || (Number.isSafeInteger(r.reply_count) && r.reply_count >= 0));
}

function read(): SavedMetric[] {
  if (typeof window === 'undefined') return [];
  try {
    const data: unknown = JSON.parse(window.localStorage.getItem(KEY) || '[]');
    return Array.isArray(data) ? data.filter(validMetric).slice(0, CAP) : [];
  } catch { return []; }
}

const identity = (mode: AccountMode, videoId: string, commentId: string) =>
  mode + ':' + videoId + ':' + commentId;

export function storePublicMetricResponse(value: PublicMetricResponse, mode: AccountMode): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const existing = new Map(read().map(x => [identity(x.account_mode, x.video_id, x.comment_id), x]));
    for (const row of value.items) {
      if (!validVideo(row.video_id) || !validId(row.comment_id)
        || (row.status !== 'active' && row.status !== 'unavailable')) continue;
      const key = identity(mode, row.video_id, row.comment_id);
      const previous = existing.get(key);
      existing.set(key, {
        ...row,
        account_mode: mode,
        checked_at: value.checked_at,
        // A temporarily hidden comment should not erase the last known reading.
        like_count: row.status === 'unavailable' ? previous?.like_count ?? null : row.like_count,
        reply_count: row.status === 'unavailable' ? previous?.reply_count ?? null : row.reply_count,
      });
    }
    window.localStorage.setItem(KEY, JSON.stringify(
      [...existing.values()].sort((a,b) => b.checked_at.localeCompare(a.checked_at)).slice(0, CAP),
    ));
    return true;
  } catch { return false; }
}

export function applySavedPublicMetrics(
  data: PublishedCommentsResponse, mode: AccountMode,
): PublishedCommentsResponse {
  const metrics = new Map(read()
    .filter(x => x.account_mode === mode)
    .map(x => [identity(mode, x.video_id, x.comment_id), x]));
  const items: PublishedComment[] = data.items.map((row) => {
    const cached = metrics.get(identity(mode, row.video_id, row.comment_id));
    if (!cached) return row;
    // Never overwrite newer authenticated server measurements with older
    // unauthenticated public lookups.
    if (!row.local_only && row.last_checked_at
      && Date.parse(row.last_checked_at) >= Date.parse(cached.checked_at)) return row;
    return {
      ...row,
      like_count: cached.like_count,
      reply_count: cached.reply_count,
      last_checked_at: cached.checked_at,
      public_metric_status: cached.status,
    };
  });
  const measured = items.filter(item => item.like_count !== null);
  const replied = measured.filter(item => (item.reply_count ?? 0) > 0);
  return {
    ...data,
    items,
    summary: {
      ...data.summary,
      tracked_count: items.length,
      measured_count: measured.length,
      average_likes: measured.length
        ? measured.reduce((sum, item) => sum + (item.like_count ?? 0), 0) / measured.length
        : null,
      replied_rate: measured.length ? replied.length / measured.length * 100 : null,
    },
  };
}
