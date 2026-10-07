import {
  Check,
  Heart,
  MessageCircleQuestion,
  MessageSquareText,
  Scale,
  Sparkles,
  UserRound,
} from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getSelectedPersona, setSelectedPersona } from '../api/client';
import { Header } from '../components/layout/Header';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import type { PersonaId } from '../types/comment';

type PersonaOption = {
  id: PersonaId;
  name: string;
  tagline: string;
  description: string;
  example: string;
  icon: typeof Scale;
};

const PERSONAS: PersonaOption[] = [
  {
    id: 'balanced',
    name: '균형형',
    tagline: '가장 자연스럽고 무난하게',
    description: '공감, 관찰, 질문을 한쪽으로 치우치지 않게 섞는 기본 페르소나입니다.',
    example: '이 포인트가 제일 인상적이네요. 다음 이야기도 궁금해져요.',
    icon: Scale,
  },
  {
    id: 'observer',
    name: '담백한 관찰자',
    tagline: '짧게 보고, 정확하게 짚기',
    description: '과장된 리액션보다 영상의 디테일이나 맥락을 차분하게 포착하는 스타일입니다.',
    example: '뒤로 갈수록 처음 장면이 다르게 보이는 게 좋네요.',
    icon: MessageSquareText,
  },
  {
    id: 'empathy',
    name: '따뜻한 공감러',
    tagline: '감정과 경험에 먼저 반응',
    description: '영상 속 사람의 감정이나 상황에 공감하면서 부드럽게 말을 건네는 스타일입니다.',
    example: '보는 사람까지 마음이 편해지는 느낌이에요. 잘 봤어요.',
    icon: Heart,
  },
  {
    id: 'friendly',
    name: '친근한 친구',
    tagline: '가볍고 편하게 한마디',
    description: '친한 사람에게 말하듯 자연스럽고 캐주얼한 반응을 선호하는 스타일입니다.',
    example: '아 이 부분 진짜 좋다 ㅋㅋ 계속 보게 되네요.',
    icon: UserRound,
  },
  {
    id: 'question',
    name: '궁금한 질문러',
    tagline: '대화를 이어가는 댓글',
    description: '영상에서 궁금한 지점을 찾아 자연스러운 질문으로 대화를 여는 스타일입니다.',
    example: '이 방식으로 바꾸고 나서 가장 크게 달라진 점은 뭐였어요?',
    icon: MessageCircleQuestion,
  },
  {
    id: 'witty',
    name: '센스 한마디',
    tagline: '짧고 기억에 남게',
    description: '영상의 핵심을 가볍게 비틀거나 재치 있게 표현하는 짧은 댓글 스타일입니다.',
    example: '알고리즘이 데려왔는데 제가 눌러앉았습니다.',
    icon: Sparkles,
  },
];

export function PersonaPage() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<PersonaId>(() => getSelectedPersona());
  const [saved, setSaved] = useState(false);

  const handleNav = (key: SidebarKey) => {
    if (key === 'dashboard') navigate('/dashboard');
    if (key === 'comments') navigate('/');
    if (key === 'persona') navigate('/persona');
  };

  const choosePersona = (id: PersonaId) => {
    setSelected(id);
    setSelectedPersona(id);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1400);
  };

  const selectedPersona = PERSONAS.find((persona) => persona.id === selected) ?? PERSONAS[0];

  return (
    <div className="app">
      <Sidebar current="persona" onNav={handleNav} />
      <div className="main">
        <Header title="페르소나" subtitle="댓글을 작성할 때 사용할 기본 말투 캐릭터를 선택합니다." />

        <main className="persona-page">
          <section className="persona-intro">
            <div>
              <span className="persona-kicker">COMMENT PERSONA</span>
              <h2>어떤 사람처럼 댓글을 달까요?</h2>
              <p>
                지금은 페르소나 선택과 저장만 지원합니다. 다음 단계에서 자주 쓰는 말, 문장 길이,
                이모지와 표현 습관을 학습해 선택한 페르소나에 고정할 수 있습니다.
              </p>
            </div>
            <div className="persona-current">
              <span>현재 선택</span>
              <strong>{selectedPersona.name}</strong>
              {saved && <em><Check size={13} /> 저장됨</em>}
            </div>
          </section>

          <div className="persona-grid">
            {PERSONAS.map((persona) => {
              const Icon = persona.icon;
              const active = persona.id === selected;
              return (
                <button
                  key={persona.id}
                  type="button"
                  className={'persona-card' + (active ? ' active' : '')}
                  onClick={() => choosePersona(persona.id)}
                  aria-pressed={active}
                >
                  <div className="persona-card-top">
                    <span className="persona-icon"><Icon size={19} /></span>
                    {active && <span className="persona-selected"><Check size={13} /> 선택됨</span>}
                  </div>
                  <div>
                    <span className="persona-tagline">{persona.tagline}</span>
                    <h3>{persona.name}</h3>
                    <p>{persona.description}</p>
                  </div>
                  <div className="persona-example">
                    <span>예시</span>
                    <q>{persona.example}</q>
                  </div>
                </button>
              );
            })}
          </div>

          <section className="persona-coming">
            <Sparkles size={16} />
            <div>
              <strong>다음 단계</strong>
              <span>자주 쓰는 표현을 고르면 이 페르소나에 개인 말투를 덧입혀 댓글 생성에 직접 반영할 예정입니다.</span>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
