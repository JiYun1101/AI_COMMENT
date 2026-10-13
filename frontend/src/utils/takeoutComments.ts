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
  // YouTube / Google Takeout exports use localized headers. Preserve Hangul
  // while removing separators (previous ASCII-only normalization erased them).
  const headers = rows[0].map((v) => v.normalize('NFKC')
    .toLocaleLowerCase().replace(/[\s_.()\-]+/g, '').trim());
  const index = (...keys: string[]) => headers.findIndex((h) => keys.includes(h));
  const commentIndex = index('commentid', 'commentidentifier', '댓글id', '댓글아이디', '댓글식별자');
  const videoIndex = index('videoid', 'videourl', 'videolink',
    '동영상id', '동영상아이디', '동영상url', '동영상링크', '영상id', '영상아이디');
  if (commentIndex < 0 || videoIndex < 0) {
    throw new Error('댓글 ID·동영상 ID 열을 찾지 못했습니다. Google Takeout의 댓글 CSV 또는 Comment ID·Video ID 열이 있는 파일을 선택해 주세요.');
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
