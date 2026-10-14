/** Browser-owned custom writing styles. Never includes account credentials. */
import type { CustomPersona, ForbiddenPersonaMark } from '../types/comment';

const KEY = 'ai-comment.custom-personas.v1';
export const MAX_CUSTOM_PERSONAS = 12;
export const MARK_OPTIONS: { id: ForbiddenPersonaMark; label: string }[] = [
  { id: 'period', label: '마침표 .' },
  { id: 'exclamation', label: '느낌표 !' },
  { id: 'question', label: '물음표 ?' },
  { id: 'comma', label: '쉼표 ,' },
  { id: 'tilde', label: '물결표 ~' },
  { id: 'emoji', label: '이모지' },
  { id: 'laughter', label: 'ㅋㅋ·ㅎㅎ' },
];
const MARKS = new Set(MARK_OPTIONS.map((item) => item.id));
const ID = /^custom_[a-zA-Z0-9-]{8,64}$/;

function cleanedLines(value: unknown): string[] {
  return Array.isArray(value)
    ? [...new Set(value.filter((item): item is string => typeof item === 'string')
      .map((item) => item.trim()).filter((item) => item.length > 0 && item.length <= 60))].slice(0, 8)
    : [];
}

export function validateCustomPersona(value: unknown): CustomPersona | null {
  if (!value || typeof value !== 'object') return null;
  const row = value as Partial<CustomPersona>;
  if (typeof row.id !== 'string' || !ID.test(row.id)) return null;
  if (typeof row.name !== 'string' || !row.name.trim() || row.name.trim().length > 40) return null;
  if (typeof row.speech_style !== 'string' || row.speech_style.length > 240) return null;
  if (typeof row.sample_comment !== 'string' || row.sample_comment.length > 200) return null;
  if (!Array.isArray(row.recurring_phrases) ||
      row.recurring_phrases.some((value) => typeof value !== 'string' || value.length > 60) ||
      row.recurring_phrases.filter((value) => value.trim()).length > 8) return null;
  if (!Array.isArray(row.prohibited_phrases) ||
      row.prohibited_phrases.some((value) => typeof value !== 'string' || value.length > 60) ||
      row.prohibited_phrases.filter((value) => value.trim()).length > 8) return null;
  if (!Array.isArray(row.forbidden_marks) || row.forbidden_marks.length > MARKS.size ||
      row.forbidden_marks.some((value) => !MARKS.has(value))) return null;
  return {
    id: row.id as CustomPersona['id'],
    name: row.name.trim(),
    speech_style: row.speech_style.trim(),
    recurring_phrases: cleanedLines(row.recurring_phrases),
    prohibited_phrases: cleanedLines(row.prohibited_phrases),
    forbidden_marks: [...new Set(row.forbidden_marks)],
    sample_comment: row.sample_comment.trim(),
  };
}

export function readCustomPersonas(): CustomPersona[] {
  if (typeof window === 'undefined') return [];
  try {
    const decoded: unknown = JSON.parse(window.localStorage.getItem(KEY) || '[]');
    return Array.isArray(decoded) ? decoded.map(validateCustomPersona)
      .filter((row): row is CustomPersona => row !== null).slice(0, MAX_CUSTOM_PERSONAS) : [];
  } catch {
    return [];
  }
}

export function getCustomPersona(id: string): CustomPersona | null {
  return readCustomPersonas().find((p) => p.id === id) ?? null;
}

export function saveCustomPersona(value: CustomPersona): CustomPersona {
  const safe = validateCustomPersona(value);
  if (!safe) throw new Error('이름·문체·표현 제한을 다시 확인해주세요.');
  const existing = readCustomPersonas();
  if (!existing.some((p) => p.id === safe.id) && existing.length >= MAX_CUSTOM_PERSONAS) {
    throw new Error(`사용자 페르소나는 최대 ${MAX_CUSTOM_PERSONAS}개까지 만들 수 있습니다.`);
  }
  const next = [...existing.filter((p) => p.id !== safe.id), safe];
  window.localStorage.setItem(KEY, JSON.stringify(next));
  return safe;
}

export function removeCustomPersona(id: string): void {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(KEY, JSON.stringify(readCustomPersonas().filter((row) => row.id !== id)));
  }
}

export function newCustomPersona(): CustomPersona {
  return {
    id: `custom_${crypto.randomUUID()}`, name: '', speech_style: '',
    recurring_phrases: [], prohibited_phrases: [], forbidden_marks: [],
    sample_comment: '',
  };
}
