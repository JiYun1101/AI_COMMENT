import {
  BarChart3,
  Check,
  Heart,
  MessageSquareText,
  Plus,
  Pencil,
  Trash2,
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
import { CustomPersonaEditor } from '../components/persona/CustomPersonaEditor';
import {
  getCustomPersona, MAX_CUSTOM_PERSONAS, newCustomPersona,
  readCustomPersonas, removeCustomPersona, saveCustomPersona,
} from '../utils/customPersonas';
import type { CustomPersona, PersonaId } from '../types/comment';

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
  const [custom, setCustom] = useState<CustomPersona[]>(() => readCustomPersonas());
  const [draft, setDraft] = useState<CustomPersona | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

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

  const handleSave = () => {
    if (!draft) return;
    setError(null);
    try {
      const result = saveCustomPersona(draft);
      setCustom(readCustomPersonas());
      setDraft(null);
      choosePersona(result.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : '페르소나를 저장하지 못했습니다.');
    }
  };

  const handleDelete = (id: string) => {
    removeCustomPersona(id);
    setCustom(readCustomPersonas());
    setDeletingId(null);
    setDraft((current) => current?.id === id ? null : current);
    if (selected === id) choosePersona('none');
  };

  const selectedCustom = custom.find((entry) => entry.id === selected);
  const selectedPreset = getPersonaPreset(selected);

  return (
    <div className="app">
      <Sidebar current="persona" onNav={handleNav} />
      <div className="main">
        <Header title="페르소나" subtitle="페르소나를 만들고 말투·자주 쓰는 표현·금지 문장부호를 설정합니다." />

        <main className="persona-page">
          <section className="persona-intro">
            <div>
              <span className="persona-kicker">COMMENT PERSONA</span>
              <h2>같은 영상도 다른 목소리로</h2>
              <p>
                페르소나는 신원이나 역할이 아니라 댓글의 목소리를 정합니다.
                기본 프리셋을 선택하거나 나만의 말투를 추가할 수 있습니다. 자주 쓰는 표현과 금지할 표현·문장부호까지 설정해 댓글 추천에 적용하세요.
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
              {selectedCustom && <small>{selectedCustom.speech_style || '사용자 설정 말투'} · 금지 기호 {selectedCustom.forbidden_marks.length}개</small>}
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

          <section className="persona-custom-section">
            <div className="persona-custom-heading">
              <div>
                <span className="persona-kicker">MY PERSONAS</span>
                <h2>내가 만든 페르소나</h2>
                <p>페르소나는 이 브라우저에 저장됩니다. 계정 간 자동 동기화는 아직 지원하지 않습니다.</p>
              </div>
              <button type="button" className="btn primary" disabled={custom.length >= MAX_CUSTOM_PERSONAS}
                onClick={() => { setDraft(newCustomPersona()); setError(null); setDeletingId(null); }}>
                <Plus size={15} /> 새 페르소나
              </button>
            </div>
            {custom.length === 0 && !draft && (
              <div className="persona-custom-empty">
                자주 쓰는 말, 말투, 피하고 싶은 표현을 기록해 나만의 페르소나를 만들어보세요.
              </div>
            )}
            <div className="persona-custom-list">
              {custom.map((item) => (
                <div key={item.id} className={'persona-custom-card' + (selected === item.id ? ' active' : '')}>
                  <div className="persona-custom-card-main">
                    <strong>{item.name}</strong>
                    <p>{item.speech_style || '말투를 자유롭게 설정한 페르소나'}</p>
                    <small>
                      선호 표현 {item.recurring_phrases.length}개 · 금지 표현 {item.prohibited_phrases.length}개 · 금지 기호 {item.forbidden_marks.length}개
                    </small>
                  </div>
                  <div className="persona-custom-card-actions">
                    <button type="button" className="btn secondary" onClick={() => choosePersona(item.id)}
                      aria-pressed={selected === item.id}>{selected === item.id ? '선택됨' : '사용하기'}</button>
                    <button type="button" className="persona-custom-icon-btn"
                      aria-label={`${item.name} 편집`}
                      onClick={() => { setDraft({ ...item }); setError(null); setDeletingId(null); }}>
                      <Pencil size={16} />
                    </button>
                    <button type="button" className="persona-custom-icon-btn danger"
                      aria-label={`${item.name} 삭제`}
                      onClick={() => { setDeletingId(item.id); setDraft(null); }}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                  {deletingId === item.id && (
                    <div className="persona-delete-confirm" role="group" aria-label="페르소나 삭제 확인">
                      <span>이 페르소나를 삭제할까요? 저장한 말투 설정이 사라집니다.</span>
                      <button type="button" className="btn secondary" onClick={() => setDeletingId(null)}>취소</button>
                      <button type="button" className="btn primary" onClick={() => handleDelete(item.id)}>삭제</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
            {draft && (
              <CustomPersonaEditor
                value={draft}
                error={error}
                onChange={(next) => { setDraft(next); setError(null); }}
                onCancel={() => { setDraft(null); setError(null); }}
                onSave={handleSave}
              />
            )}
          </section>

          <section className="persona-coming">
            <Sparkles size={16} />
            <div>
              <strong>말투 설정은 다음 댓글 생성부터 적용됩니다</strong>
              <span>
                자주 쓰는 표현과 예시는 참고용이며, 금지 표현과 문장부호는 최종 후보에서 검사합니다.
                지나치게 엄격한 제한으로 후보가 부족하면 생성 오류가 표시될 수 있습니다.
              </span>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
