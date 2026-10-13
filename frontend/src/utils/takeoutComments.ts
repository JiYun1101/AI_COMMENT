/**
 * Restore comment IDs from Google Takeout YouTube/comments/comments.csv.
 * The parser runs only in the browser. Raw Takeout text is never uploaded.
 * Every ID must be verified by the backend against the connected YouTube OAuth account.
 */
export interface TakeoutCommentIdentity { commentId: string; videoId: string }

function parseCsv(text: string): string[][] {
  // Google Takeout and spreadsheet exports can use comma, semicolon or tab.
  const firstLine = text.split(/\r?\n/, 1)[0] || '';
  const delimiter = ['\t', ';', ','].sort((a, b) =>
    firstLine.split(b).length - firstLine.split(a).length)[0];
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
    } else if (ch === delimiter && !quoted) {
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
    .toLocaleLowerCase().replace(/[\s_.()\-\u200b-\u200d\ufeff]+/g, '').trim());
  const index = (...keys: string[]) => headers.findIndex((h) => keys.includes(h));
  const commentIndex = index('commentid', 'commentidentifier', '댓글id', '댓글아이디', '댓글식별자', '댓글고유id', 'commenturl', '댓글url');
  const videoIndex = index('videoid', 'videourl', 'videolink',
    '동영상id', '동영상아이디', '동영상url', '동영상링크', '영상id', '영상아이디', '영상url', '영상링크', 'youtubevideoid');
  if (commentIndex < 0 || videoIndex < 0) {
    throw new Error('댓글 ID·동영상 ID 열을 찾지 못했습니다. 감지된 열: ' + rows[0].slice(0, 8).join(', ') + '. ID가 없는 Takeout 내보내기 형식은 자동 추적할 수 없습니다.');
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
