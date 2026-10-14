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
  MAX_CUSTOM_PERSONAS, newCustomPersona,
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

  const handleSave = (next: CustomPersona) => {
    setError(null);
    try {
      const result = saveCustomPersona(next);
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
        <Header title="페르소나" subtitle="카드를 선택하거나, 나만의 말투를 만들어 바로 사용하세요." />

        <main className="persona-page">
          <section className="persona-intro">
            <div>
              <span className="persona-kicker">COMMENT PERSONA</span>
              <h2>같은 영상도 다른 목소리로</h2>
              <p>
                페르소나는 신원이나 역할이 아니라 댓글의 목소리를 정합니다.
                카드를 고르거나 직접 말투를 적고 바로 사용할 수 있어요.
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

            {custom.map((item) => (
              draft?.id === item.id ? (
                <CustomPersonaEditor key={item.id} value={draft} error={error}
                  onChange={(next) => { setDraft(next); setError(null); }}
                  onCancel={() => { setDraft(null); setError(null); }} onSave={handleSave} />
              ) : (
                <div key={item.id} className={'persona-card persona-user-card' + (selected === item.id ? ' active' : '')}>
                  <button type="button" className="persona-user-select" onClick={() => choosePersona(item.id)}
                    aria-pressed={selected === item.id} aria-label={`${item.name} 페르소나 사용`}>
                    <div className="persona-card-top">
                      <span className="persona-icon"><MessageSquareText size={19} /></span>
                      {selected === item.id && <span className="persona-selected"><Check size={13} /> 선택됨</span>}
                    </div>
                    <h3>{item.name}</h3>
                    <p className="persona-user-description">{item.speech_style || item.recurring_phrases.join(', ') || '나만의 댓글 말투'}</p>
                    <div className="persona-example">
                      <span>금지 표현</span>
                      <p>{[...item.prohibited_phrases, ...item.forbidden_marks.map((mark) => ({
                        period: '.', exclamation: '!', question: '?', comma: '쉼표',
                        tilde: '~', emoji: '이모지', laughter: 'ㅋㅋ·ㅎㅎ',
                      })[mark])].join(' · ') || '제한 없음'}</p>
                    </div>
                  </button>
                  <div className="persona-user-actions">
                    <button type="button" aria-label={`${item.name} 수정`}
                      onClick={() => { setDraft({ ...item }); setError(null); setDeletingId(null); }}>
                      <Pencil size={13} /> 수정
                    </button>
                    <button type="button" aria-label={`${item.name} 삭제`}
                      onClick={() => { setDeletingId(item.id); setDraft(null); }}>
                      <Trash2 size={13} /> 삭제
                    </button>
                  </div>
                  {deletingId === item.id && (
                    <div className="persona-delete-confirm" role="group" aria-label="페르소나 삭제 확인">
                      <span>이 페르소나를 삭제할까요?</span>
                      <button type="button" onClick={() => setDeletingId(null)}>취소</button>
                      <button type="button" onClick={() => handleDelete(item.id)}>삭제</button>
                    </div>
                  )}
                </div>
              )
            ))}
            {draft && !custom.some((item) => item.id === draft.id) ? (
              <CustomPersonaEditor key={draft.id} value={draft} error={error}
                onChange={(next) => { setDraft(next); setError(null); }}
                onCancel={() => { setDraft(null); setError(null); }} onSave={handleSave} />
            ) : custom.length < MAX_CUSTOM_PERSONAS ? (
              <button type="button" className="persona-card persona-add-card"
                onClick={() => { setDraft(newCustomPersona()); setError(null); setDeletingId(null); }}>
                <span className="persona-icon"><Plus size={21} /></span>
                <strong>+ 나만의 페르소나</strong>
                <span>말투와 사용하지 않을 표현을 적고 바로 사용</span>
              </button>
            ) : null}
          </div>
        </main>
      </div>
    </div>
  );
}
