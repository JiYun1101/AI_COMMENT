/**
 * Restore comment IDs from Google Takeout YouTube/comments/comments.csv.
 * The parser runs only in the browser. Raw Takeout text is never uploaded.
 * Every ID must be verified by the backend against the connected YouTube OAuth account.
 */
export interface TakeoutCommentIdentity { commentId: string; videoId: string }

function parseCsv(text: string): string[][] {
  if (text.length > 8 * 1024 * 1024) throw new Error('CSV 파일은 8MB 이하만 지원합니다.');
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = '';
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
      else quoted = !quoted;
    } else if (ch === ',' && !quoted) {
      row.push(cell); cell = '';
    } else if ((ch === '\n' || ch === '\r') && !quoted) {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      row.push(cell); cell = '';
      if (row.some((v) => v.trim())) rows.push(row);
      row = [];
    } else cell += ch;
  }
  if (quoted) throw new Error('CSV 따옴표 구조가 올바르지 않습니다.');
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

function normalizeVideoId(value: string): string {
  const raw = value.trim();
  if (/^[\w-]{11}$/.test(raw)) return raw;
  try {
    const url = new URL(raw);
    const match = url.hostname === 'youtu.be'
      ? url.pathname.split('/')[1]
      : url.hostname.endsWith('youtube.com') ? url.searchParams.get('v') : null;
    return match && /^[\w-]{11}$/.test(match) ? match : '';
  } catch { return ''; }
}

export function parseTakeoutCommentsCsv(text: string): TakeoutCommentIdentity[] {
  const rows = parseCsv(text.replace(/^\uFEFF/, ''));
  if (!rows.length) return [];
  const headers = rows[0].map((v) => v.trim().toLowerCase().replace(/[^a-z0-9]/g, ''));
  const index = (...keys: string[]) => headers.findIndex((h) => keys.includes(h));
  const commentIndex = index('commentid', 'commentidentifier');
  const videoIndex = index('videoid', 'videourl', 'videolink');
  if (commentIndex < 0 || videoIndex < 0) {
    throw new Error('Google Takeout 댓글 CSV에서 Comment ID 또는 Video ID 열을 찾지 못했습니다.');
  }
  const ids = new Map<string, TakeoutCommentIdentity>();
  for (const row of rows.slice(1)) {
    const commentId = (row[commentIndex] || '').trim();
    const videoId = normalizeVideoId(row[videoIndex] || '');
    if (commentId && commentId.length <= 100 && videoId) {
      ids.set(commentId, { commentId, videoId });
    }
  }
  return [...ids.values()];
}
