import { Check, MessageSquareText, X } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import type { CustomPersona } from '../../types/comment';
import { formatPersonaRestrictions, parsePersonaRestrictions } from '../../utils/compactPersona';

interface Props {
  value: CustomPersona;
  error: string | null;
  onChange: (next: CustomPersona) => void;
  onCancel: () => void;
  onSave: (next: CustomPersona) => void;
}

/** Same footprint as a normal persona card; no full-page configuration form. */
export function CustomPersonaEditor({ value, error, onChange, onCancel, onSave }: Props) {
  const [restrictions, setRestrictions] = useState(() => formatPersonaRestrictions(value));
  const [localError, setLocalError] = useState<string | null>(null);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const parsed = parsePersonaRestrictions(restrictions);
      setLocalError(null);
      onSave({ ...value, ...parsed });
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : '제한 표현을 확인해주세요.');
    }
  };

  return (
    <form className="persona-card persona-editor-card" onSubmit={submit} aria-label="나만의 페르소나 간편 설정">
      <div className="persona-card-top">
        <span className="persona-icon"><MessageSquareText size={19} /></span>
        <button type="button" className="persona-editor-close" onClick={onCancel} aria-label="편집 취소"><X size={16} /></button>
      </div>
      <label className="persona-quick-field">
        <span>이름</span>
        <input required maxLength={40} value={value.name}
          onChange={(event) => onChange({ ...value, name: event.target.value })}
          placeholder="예: 담백한 관찰자" />
      </label>
      <label className="persona-quick-field">
        <span>말투 · 자주 쓰는 말</span>
        <textarea maxLength={240} rows={3} value={value.speech_style}
          onChange={(event) => onChange({ ...value, speech_style: event.target.value })}
          placeholder="짧은 반말, '갠적으로', '~인 듯' 자주 사용" />
      </label>
      <label className="persona-quick-field">
        <span>쓰지 않을 말 · 문장부호 <small>(선택)</small></span>
        <input value={restrictions} onChange={(event) => { setRestrictions(event.target.value); setLocalError(null); }}
          placeholder="레전드, !, ㅋㅋ, 이모지" />
      </label>
      {(error || localError) && <p className="persona-editor-error" role="alert">{error || localError}</p>}
      <button type="submit" className="persona-quick-save" disabled={!value.name.trim()}>
        <Check size={14} /> 저장하고 사용
      </button>
    </form>
  );
}
