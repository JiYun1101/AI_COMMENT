/** Browser-side auxiliary snapshot backup, keyed by OAuth-verified channel ID.
 * No cross-channel fallback is permitted when backend authentication fails.
 */
import type { OwnedVideoMetric, OwnedVideoPerformanceResponse } from '../types/comment';

const PREFIX = 'ai-comment.owned-videos.v1:';
const MAX_VIDEOS = 300;

function isMetric(row: unknown): row is OwnedVideoMetric {
  if (!row || typeof row !== 'object') return false;
  const item = row as Partial<OwnedVideoMetric>;
  return typeof item.owner_channel_id === 'string'
    && typeof item.video_id === 'string'
    && /^[A-Za-z0-9_-]{11}$/.test(item.video_id)
    && typeof item.title === 'string'
    && typeof item.last_checked_at === 'string';
}

export function readVideoBackup(channelId: string): OwnedVideoMetric[] {
  if (!channelId || typeof window === 'undefined') return [];
  try {
    const data: unknown = JSON.parse(window.localStorage.getItem(PREFIX + channelId) || '[]');
    return Array.isArray(data)
      ? data.filter(isMetric).filter((x) => x.owner_channel_id === channelId).slice(0, MAX_VIDEOS)
      : [];
  } catch {
    return [];
  }
}

export function mergeVideoBackup(data: OwnedVideoPerformanceResponse): OwnedVideoPerformanceResponse {
  const remote = new Set(data.items.map((item) => item.video_id));
  const stale = readVideoBackup(data.channel_id)
    .filter((item) => !remote.has(item.video_id))
    .map((item) => ({ ...item, local_only: true }));
  return { ...data, items: [...data.items, ...stale] };
}

export function saveVideoBackup(data: OwnedVideoPerformanceResponse): boolean {
  if (!data.channel_id || typeof window === 'undefined') return false;
  try {
    const existing = readVideoBackup(data.channel_id);
    const next = new Map(existing.map((row) => [row.video_id, row]));
    for (const row of data.items) {
      if (row.owner_channel_id === data.channel_id && isMetric(row)) {
        next.set(row.video_id, { ...row, local_only: false });
      }
    }
    window.localStorage.setItem(PREFIX + data.channel_id,
      JSON.stringify([...next.values()].slice(0, MAX_VIDEOS)));
    return true;
  } catch {
    return false;
  }
}

export function exportVideoBackup(channelId: string): void {
  const rows = readVideoBackup(channelId);
  const payload = JSON.stringify({ version: 1, channel_id: channelId, exported_at: new Date().toISOString(), videos: rows }, null, 2);
  const url = URL.createObjectURL(new Blob([payload], { type: 'application/json' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'my-video-performance-' + new Date().toISOString().slice(0, 10) + '.json';
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
