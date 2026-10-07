import type { PersonaId } from '../types/comment';

export type PersonaPreset = {
  id: Exclude<PersonaId, 'none'>;
  name: string;
  formality: '합쇼체' | '해요체' | '반말';
  tone: '응원' | '차분' | '유머';
  markers: '없음' | '조금' | '풍부';
  length: '짧게' | '자동' | '길게';
  example: string;
};

export const PERSONA_PRESETS: PersonaPreset[] = [
  {
    id: 'polite_viewer',
    name: '정중한 시청자',
    formality: '합쇼체',
    tone: '차분',
    markers: '없음',
    length: '길게',
    example: '차분하게 풀어 주신 덕분에 내용이 잘 정리되었습니다. 다음 영상도 기대하겠습니다.',
  },
  {
    id: 'friendly_viewer',
    name: '친근한 시청자',
    formality: '해요체',
    tone: '응원',
    markers: '조금',
    length: '자동',
    example: '편집이 깔끔해서 끝까지 편하게 봤어요! 이 장면은 어떻게 촬영하셨는지 궁금해요 :)',
  },
  {
    id: 'warm_supporter',
    name: '따뜻한 응원형',
    formality: '해요체',
    tone: '응원',
    markers: '조금',
    length: '짧게',
    example: '오늘도 고생 많으셨어요, 늘 응원해요!',
  },
  {
    id: 'calm_analyst',
    name: '차분한 분석형',
    formality: '해요체',
    tone: '차분',
    markers: '없음',
    length: '길게',
    example: '초반에 문제를 짚고 후반에 근거를 붙인 구성이 설득력 있어요. 중간에 나온 수치의 출처가 궁금합니다.',
  },
  {
    id: 'playful_casual',
    name: '유쾌한 캐주얼',
    formality: '반말',
    tone: '유머',
    markers: '풍부',
    length: '짧게',
    example: 'ㅋㅋㅋ 이 장면 반칙임 다시 돌려봄 😂',
  },
];

export function getPersonaPreset(id: PersonaId): PersonaPreset | null {
  if (id === 'none') return null;
  return PERSONA_PRESETS.find((persona) => persona.id === id) ?? null;
}

export function getPersonaLabel(id: PersonaId): string {
  return getPersonaPreset(id)?.name ?? '페르소나 없음';
}
