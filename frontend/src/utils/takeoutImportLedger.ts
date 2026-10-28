/**
 * Browser-local index of successfully verified Google Takeout comment imports.
 * Never trust arbitrary raw CSV IDs as published comments: the server verifies
 * each comment belongs to the OAuth-connected YouTube channel first.
 */
import { cachedAccount } from '../api/account';

export interface VerifiedTakeoutRow {
  video_id: string;
  comment_id: string;
  comment: string;
  comment_url: string | null;
  published_at: string;
}
export interface StoredTakeoutRow extends VerifiedTakeoutRow {
  verified_channel_id: string;
  imported_at: string;
}

const PREFIX = 'ai-comment.verified-takeout.v1.';
const LIMIT = 500;
const key = () => PREFIX + (cachedAccount()?.id || 'local-personal');
const validVideo = (v: unknown): v is string => typeof v === 'string' && /^[A-Za-z0-9_-]{11}$/.test(v);
const validCommentId = (v: unknown): v is string => typeof v === 'string' && v.length > 0 && v.length <= 100;
function validRow(v: unknown): v is StoredTakeoutRow {
  if (!v || typeof v !== 'object') return false;
  const a = v as Partial<StoredTakeoutRow>;
  return validVideo(a.video_id) && validCommentId(a.comment_id)
    && typeof a.comment === 'string' && a.comment.length <= 10000
    && (a.comment_url == null || typeof a.comment_url === 'string')
    && typeof a.verified_channel_id === 'string' && a.verified_channel_id.length > 0
    && typeof a.published_at === 'string' && Number.isFinite(Date.parse(a.published_at))
    && typeof a.imported_at === 'string' && Number.isFinite(Date.parse(a.imported_at));
}
export function listVerifiedTakeoutImports(): StoredTakeoutRow[] {
  if (typeof window === 'undefined') return [];
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(key()) || '[]');
    return Array.isArray(parsed) ? parsed.filter(validRow).slice(0, LIMIT) : [];
  } catch { return []; }
}
export function saveVerifiedTakeoutImports(
  verifiedRows: VerifiedTakeoutRow[],
  channelId: string,
): { added: number; total: number } {
  if (typeof window === 'undefined' || !channelId || !verifiedRows.length) {
    return { added: 0, total: listVerifiedTakeoutImports().length };
  }
  const existing = listVerifiedTakeoutImports();
  const merged = new Map(existing.map(row => [row.video_id + ':' + row.comment_id, row]));
  let added = 0;
  for (const row of verifiedRows) {
    if (!validVideo(row.video_id) || !validCommentId(row.comment_id)
      || typeof row.comment !== 'string' || row.comment.length > 10000
      || (row.comment_url != null && typeof row.comment_url !== 'string')
      || !Number.isFinite(Date.parse(row.published_at))) continue;
    const id = row.video_id + ':' + row.comment_id;
    if (!merged.has(id)) added++;
    merged.set(id, {
      ...row,
      verified_channel_id: channelId,
      imported_at: new Date().toISOString(),
    });
  }
  const ordered = [...merged.values()].sort((a,b) => b.published_at.localeCompare(a.published_at)).slice(0,LIMIT);
  try {
    localStorage.setItem(key(), JSON.stringify(ordered));
    return { added, total: ordered.length };
  } catch {
    throw new Error('브라우저 저장 공간이 부족해 CSV 복구 기록을 보관하지 못했습니다. 저장 공간을 확인해주세요.');
  }
}

/** Remove a verified import after YouTube confirms deletion. */
export function removeVerifiedTakeoutImport(commentId: string): void {
  if (typeof window === 'undefined') return;
  try {
    const remaining = listVerifiedTakeoutImports().filter(row => row.comment_id !== commentId);
    localStorage.setItem(key(), JSON.stringify(remaining));
  } catch { /* Deletion on YouTube already succeeded. */ }
}
