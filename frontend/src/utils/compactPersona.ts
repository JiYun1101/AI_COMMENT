import type { CustomPersona, ForbiddenPersonaMark } from '../types/comment';

/** One short input is enough for both banned words and punctuation.
 *  Use "쉼표" to prohibit a comma because commas separate entries.
 */
const MARK_NAMES: Record<ForbiddenPersonaMark, string> = {
  period: '마침표', exclamation: '!', question: '?', comma: '쉼표',
  tilde: '~', emoji: '이모지', laughter: 'ㅋㅋ/ㅎㅎ',
};
const MARK_ALIASES: Record<string, ForbiddenPersonaMark> = {
  '.': 'period', '。': 'period', '마침표': 'period', '온점': 'period',
  '!': 'exclamation', '！': 'exclamation', '느낌표': 'exclamation',
  '?': 'question', '？': 'question', '물음표': 'question',
  '쉼표': 'comma', '콤마': 'comma',
  '~': 'tilde', '～': 'tilde', '물결표': 'tilde', '물결': 'tilde',
  '이모지': 'emoji', '이모티콘': 'emoji', 'emoji': 'emoji',
  'ㅋㅋ': 'laughter', 'ㅎㅎ': 'laughter', '웃음': 'laughter', '웃음표현': 'laughter',
  'ㅋㅋ/ㅎㅎ': 'laughter', 'ㅋㅋ ㅎㅎ': 'laughter',
};

export function formatPersonaRestrictions(persona: CustomPersona): string {
  return [
    ...persona.forbidden_marks.map((mark) => MARK_NAMES[mark]),
    ...persona.prohibited_phrases,
  ].join(', ');
}

export function parsePersonaRestrictions(input: string): Pick<CustomPersona, 'forbidden_marks' | 'prohibited_phrases'> {
  const pieces = input.split(/[,，;；\n]+/).map((part) => part.trim()).filter(Boolean);
  const forbidden_marks: ForbiddenPersonaMark[] = [];
  const prohibited_phrases: string[] = [];
  for (const piece of pieces) {
    // "느낌표 금지" and "ㅋㅋ 금지" are treated as punctuation settings.
    const normalized = piece.replace(/\s*(?:금지|사용\s*안\s*함|쓰지\s*않기)\s*$/u, '').trim();
    const mark = MARK_ALIASES[normalized.toLowerCase()];
    if (mark) {
      if (!forbidden_marks.includes(mark)) forbidden_marks.push(mark);
    } else if (!prohibited_phrases.includes(piece)) {
      if (piece.length > 60) throw new Error('제한할 표현은 60자 이내로 입력해주세요.');
      prohibited_phrases.push(piece);
    }
  }
  if (prohibited_phrases.length > 8) throw new Error('금지 표현은 최대 8개까지 설정할 수 있습니다.');
  return { forbidden_marks, prohibited_phrases };
}
