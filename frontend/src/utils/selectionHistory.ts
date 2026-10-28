import { cachedAccount } from '../api/account';

/** A copy action is an explicit candidate selection, NOT proof of publication. */
const PREFIX = 'ai-comment.selected-recommendations.v1.';
const LIMIT = 300;
function key() { return PREFIX + (cachedAccount()?.id || 'guest'); }
function read(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const data: unknown = JSON.parse(localStorage.getItem(key()) || '[]');
    return Array.isArray(data) ? data.filter((id): id is string =>
      typeof id === 'string' && /^r_[A-Za-z0-9_-]{6,80}$/.test(id)).slice(0,LIMIT) : [];
  } catch { return []; }
}
export function listSelectedRecommendationIds(): string[] { return read(); }
export function recordSelectedRecommendation(id: string): void {
  if (typeof window === 'undefined' || !/^r_[A-Za-z0-9_-]{6,80}$/.test(id)) return;
  try {
    localStorage.setItem(key(), JSON.stringify([id,...read().filter(existing=>existing!==id)].slice(0,LIMIT)));
  } catch { /* Copying succeeds even when storage is full or unavailable. */ }
}
