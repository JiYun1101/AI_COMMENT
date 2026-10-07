import {
  BarChart3,
  Check,
  Heart,
  MessageSquareText,
  RotateCcw,
  Sparkles,
  UserRound,
} from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getSelectedPersona, setSelectedPersona } from '../api/client';
import { Header } from '../components/layout/Header';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import { getPersonaLabel, getPersonaPreset, PERSONA_PRESETS } from '../data/personas';
import type { PersonaId } from '../types/comment';

const PERSONA_ICONS = {
  polite_viewer: MessageSquareText,
  friendly_viewer: UserRound,
  warm_supporter: Heart,
  calm_analyst: BarChart3,
  playful_casual: Sparkles,
} as const;

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

  const selectedPreset = getPersonaPreset(selected);

  return (
    <div className="app">
      <Sidebar current="persona" onNav={handleNav} />
      <div className="main">
        <Header title="페르소나" subtitle="추천 댓글의 말투와 분위기를 선택합니다." />

        <main className="persona-page">
          <section className="persona-intro">
            <div>
              <span className="persona-kicker">COMMENT PERSONA</span>
              <h2>같은 영상도 다른 목소리로</h2>
              <p>
                페르소나는 신원이나 역할이 아니라 댓글의 목소리를 정합니다.
                지금은 프리셋 선택과 저장만 지원하며, 댓글 유형과는 별도의 설정입니다.
              </p>
            </div>
            <div className="persona-current">
              <span>현재 선택</span>
              <strong>{getPersonaLabel(selected)}</strong>
              {selectedPreset && (
                <small>
                  {selectedPreset.formality} · {selectedPreset.tone} · {selectedPreset.markers} · {selectedPreset.length}
                </small>
              )}
              {saved && <em><Check size={13} /> 다른 페이지에도 저장됨</em>}
            </div>
          </section>

          <div className="persona-reset-row">
            <button
              type="button"
              className={'persona-none-button' + (selected === 'none' ? ' active' : '')}
              onClick={() => choosePersona('none')}
              aria-pressed={selected === 'none'}
            >
              <RotateCcw size={14} />
              페르소나 사용 안 함
              {selected === 'none' && <span><Check size={12} /> 기본값</span>}
            </button>
            <span>선택하지 않으면 기존 추천 방식 그대로 동작합니다.</span>
          </div>

          <div className="persona-grid">
            {PERSONA_PRESETS.map((persona) => {
              const Icon = PERSONA_ICONS[persona.id];
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
                    <h3>{persona.name}</h3>
                    <div className="persona-dials">
                      <span><b>말투</b>{persona.formality}</span>
                      <span><b>톤</b>{persona.tone}</span>
                      <span><b>장식</b>{persona.markers}</span>
                      <span><b>길이</b>{persona.length}</span>
                    </div>
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
              <strong>선택값은 자동 유지됩니다</strong>
              <span>
                여기서 고른 페르소나는 브라우저에 저장되어 댓글 추천·대시보드·계정 페이지를 이동해도 유지됩니다.
                다음 단계에서 자주 쓰는 말과 표현 습관을 이 프리셋에 추가할 예정입니다.
              </span>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
