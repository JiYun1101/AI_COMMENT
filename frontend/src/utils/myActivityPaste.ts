/** Parse pasted Google My Activity "내 YouTube 댓글" page text locally.
 * Contains comment text followed by "<video title> 에 남긴 댓글".
 * Text alone is unverified; only server-side OAuth verification adds tracking.
 */
export interface PastedActivityComment { video_title: string; comment_text: string }

export function parsePastedMyActivity(source: string): PastedActivityComment[] {
  if (source.length > 160_000) throw new Error('활동 기록은 한 번에 16만 자 이하만 붙여넣어 주세요.');
  const rows = source.split(/\r?\n/).map((raw) => raw.replace(/\*\*/g, '').trim()).filter(Boolean);
  const collected: PastedActivityComment[] = [];
  const unique = new Set<string>();
  for (let i = 0; i < rows.length; i++) {
    const match = rows[i].match(/^(.{2,240})\s+에 남긴 댓글$/);
    if (!match || i < 1) continue;
    const title = match[1].trim();
    const comment = rows[i - 1]?.trim() ?? '';
    if (!comment || comment.length < 2 || comment.length > 1000) continue;
    if (/^(YouTube|YouTube 로고|오늘|세부정보|내 YouTube 댓글)$/.test(comment)) continue;
    const id = title + '\u0000' + comment;
    if (unique.has(id)) continue;
    unique.add(id);
    collected.push({ video_title: title, comment_text: comment });
  }
  return collected;
}
