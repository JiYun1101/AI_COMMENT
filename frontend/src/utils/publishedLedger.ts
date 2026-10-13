import type {
  AccountMode, PublishedComment, PublishedCommentsResponse,
  YouTubeCommentPublishResponse,
} from '../types/comment';

const STORAGE_KEY = 'ai-comment.published-comments-backup.v1';
const MAX_RECORDS = 500;

export type BackedUpComment = Pick<
  PublishedComment,
  'video_id' | 'comment_id' | 'comment' | 'comment_url' | 'published_at' |
  'account_mode' | 'recommendation_id'
>;

function isValidRecord(input: unknown): input is BackedUpComment {
  if (!input || typeof input !== 'object') return false;
  const row = input as Partial<BackedUpComment>;
  return (
    typeof row.comment_id === 'string' && row.comment_id.length > 0 && row.comment_id.length <= 100 &&
    typeof row.video_id === 'string' && /^[\w-]{11}$/.test(row.video_id) &&
    typeof row.comment === 'string' && row.comment.length <= 10000 &&
    typeof row.published_at === 'string' && Number.isFinite(Date.parse(row.published_at)) &&
    (row.account_mode === 'demo' || row.account_mode === 'personal')
  );
}

export function readPostedBackup(mode?: AccountMode): BackedUpComment[] {
  if (typeof window === 'undefined') return [];
  try {
    const stored: unknown = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
    if (!Array.isArray(stored)) return [];
    return stored.filter(isValidRecord).filter((row) => !mode || row.account_mode === mode).slice(0, MAX_RECORDS);
  } catch {
    return [];
  }
}

function persist(rows: BackedUpComment[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(rows.slice(0, MAX_RECORDS)));
}

export function backUpPostedComment(
  posted: YouTubeCommentPublishResponse,
  recommendationId?: string | null,
  accountMode: AccountMode = 'demo',
): boolean {
  if (!posted.posted || !posted.comment_id || !posted.video_id) return false;
  try {
    const row: BackedUpComment = {
      video_id: posted.video_id,
      comment_id: posted.comment_id,
      comment: posted.comment,
      comment_url: posted.comment_url || null,
      published_at: new Date().toISOString(),
      account_mode: accountMode,
      recommendation_id: recommendationId ?? null,
    };
    persist([row, ...readPostedBackup().filter((item) => item.comment_id !== row.comment_id)]);
    return true;
  } catch {
    return false;
  }
}

export function importPostedBackup(value: unknown): number {
  const input = value && typeof value === 'object' && !Array.isArray(value)
    ? (value as { comments?: unknown }).comments : value;
  if (!Array.isArray(input)) throw new Error('댓글 백업 JSON 배열이 아닙니다.');
  if (input.length > MAX_RECORDS) throw new Error('한 번에 500개 이하의 기록만 가져올 수 있습니다.');
  const clean = input.filter(isValidRecord);
  if (clean.length !== input.length) throw new Error('형식이 올바르지 않은 게시 기록이 있습니다.');
  const combined = new Map(readPostedBackup().map((row) => [row.comment_id, row]));
  for (const row of clean) combined.set(row.comment_id, row);
  persist([...combined.values()].sort((a, b) => b.published_at.localeCompare(a.published_at)));
  return clean.length;
}

export function exportPostedBackup(): void {
  const data = JSON.stringify({
    format: 'ai-comment-published-backup-v1',
    exported_at: new Date().toISOString(),
    comments: readPostedBackup(),
  }, null, 2);
  const url = URL.createObjectURL(new Blob([data], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'ai-comment-posted-comments-backup.json';
  link.click();
  URL.revokeObjectURL(url);
}

export function mergePostedBackup(data: PublishedCommentsResponse, mode: AccountMode): PublishedCommentsResponse {
  const serverIds = new Set(data.items.map((row) => row.comment_id));
  const now = Date.now();
  const offline: PublishedComment[] = readPostedBackup(mode)
    .filter((row) => !serverIds.has(row.comment_id))
    .map((row) => ({
      ...row,
      id: 'local:' + row.comment_id,
      hours_since_publish: Math.max(0, (now - Date.parse(row.published_at)) / 3_600_000),
      like_count: null,
      reply_count: null,
      likes_24h: null,
      replies_24h: null,
      likes_7d: null,
      replies_7d: null,
      status: 'pending',
      last_checked_at: null,
      predicted_score: null,
      comment_type: null,
      video_title: null,
      channel: null,
      local_only: true,
    }));
  return {
    ...data,
    items: [...data.items, ...offline].sort((a, b) => b.published_at.localeCompare(a.published_at)),
    summary: { ...data.summary, tracked_count: data.items.length + offline.length },
  };
}
