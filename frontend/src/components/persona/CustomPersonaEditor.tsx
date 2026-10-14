import { Check, X } from 'lucide-react';
import type { CustomPersona, ForbiddenPersonaMark } from '../../types/comment';
import { MARK_OPTIONS } from '../../utils/customPersonas';

interface Props {
  value: CustomPersona;
  error: string | null;
  onChange: (next: CustomPersona) => void;
  onCancel: () => void;
  onSave: () => void;
}

function splitPhrases(value: string): string[] {
  // Keep the trailing empty line while editing, otherwise users cannot
  // press Enter to start a new phrase in a controlled textarea.
  return value.split(/\r?\n/);
}

export function CustomPersonaEditor({ value, error, onChange, onCancel, onSave }: Props) {
  const update = (partial: Partial<CustomPersona>) => onChange({ ...value, ...partial });
  const toggleMark = (mark: ForbiddenPersonaMark) => {
    update({
      forbidden_marks: value.forbidden_marks.includes(mark)
        ? value.forbidden_marks.filter((m) => m !== mark)
        : [...value.forbidden_marks, mark],
    });
  };

  return (
    <section className="persona-editor" aria-label="나만의 페르소나 편집">
      <div className="persona-editor-head">
        <div>
          <span className="persona-kicker">CUSTOM PERSONA</span>
          <h3>{value.name ? `'${value.name}' 편집` : '새 페르소나 만들기'}</h3>
          <p>입력한 표현은 말투 참고용입니다. 댓글의 사실관계와 안전 기준이 항상 우선합니다.</p>
        </div>
        <button type="button" className="persona-close" onClick={onCancel} aria-label="편집 닫기"><X size={18} /></button>
      </div>

      <div className="persona-editor-fields">
        <label className="persona-field">
          <span>페르소나 이름 <b>필수</b></span>
          <input value={value.name} onChange={(e) => update({ name: e.target.value })}
            maxLength={40} placeholder="예: 담백한 관찰자" />
        </label>
        <label className="persona-field">
          <span>주로 사용하는 말투 / 문장 끝맺음</span>
          <textarea value={value.speech_style} onChange={(e) => update({ speech_style: e.target.value })}
            maxLength={240} rows={3} placeholder="예: 반말이지만 공격적이지 않게, 짧은 문장 위주, '~인 듯', '~임' 같은 종결" />
          <small>어조·격식·문장 길이·종결형 등 최대 240자</small>
        </label>
        <label className="persona-field">
          <span>자주 쓰는 말 / 선호 표현</span>
          <textarea value={value.recurring_phrases.join('\n')}
            onChange={(e) => update({ recurring_phrases: splitPhrases(e.target.value) })}
            rows={4} placeholder={'갠적으로\n이 장면 좋다\n뭔가 신기함'} />
          <small>줄마다 한 표현, 최대 8개 · 문맥에 맞을 때만 사용하며 매번 강제하지 않습니다.</small>
        </label>
        <label className="persona-field">
          <span>사용하지 않을 단어 / 표현</span>
          <textarea value={value.prohibited_phrases.join('\n')}
            onChange={(e) => update({ prohibited_phrases: splitPhrases(e.target.value) })}
            rows={3} placeholder={'대박\n레전드\n구독 부탁'} />
          <small>줄마다 한 표현, 최대 8개 · 생성 결과에서 실제로 차단합니다.</small>
        </label>
        <fieldset className="persona-marks">
          <legend>사용하지 않을 문장부호 · 표현</legend>
          <div className="persona-mark-list">
            {MARK_OPTIONS.map(({ id, label }) => (
              <label key={id} className={value.forbidden_marks.includes(id) ? 'selected' : ''}>
                <input type="checkbox" checked={value.forbidden_marks.includes(id)}
                  onChange={() => toggleMark(id)} />
                <span>{label}</span>
              </label>
            ))}
          </div>
          <small>체크한 기호가 들어간 댓글 후보는 최종 추천에서 제외됩니다.</small>
        </fieldset>
        <label className="persona-field">
          <span>말투 예시 한 문장</span>
          <textarea value={value.sample_comment} onChange={(e) => update({ sample_comment: e.target.value })}
            maxLength={200} rows={2} placeholder="예: 음 이 부분은 진짜 좀 괜찮은듯" />
          <small>예시의 분위기만 참고하며 그대로 복사하도록 강제하지 않습니다.</small>
        </label>
      </div>
      {error && <p className="persona-editor-error" role="alert">{error}</p>}
      <div className="persona-editor-actions">
        <button type="button" className="btn secondary" onClick={onCancel}>취소</button>
        <button type="button" className="btn primary" onClick={onSave}>
          <Check size={15} /> 저장하고 선택
        </button>
      </div>
    </section>
  );
}
