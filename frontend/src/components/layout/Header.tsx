import { Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getSelectedPersona } from '../../api/client';
import { getPersonaLabel } from '../../data/personas';

interface HeaderProps {
  title: string;
  subtitle?: string;
  onGenerate?: () => void;
}

export function Header({ title, subtitle, onGenerate }: HeaderProps) {
  const navigate = useNavigate();
  const selectedPersona = getSelectedPersona();
  const personaLabel = getPersonaLabel(selectedPersona);
  const personaBadge =
    selectedPersona === 'none'
      ? '기본'
      : selectedPersona === 'polite_viewer'
        ? '정중'
        : selectedPersona === 'friendly_viewer'
          ? '친근'
          : selectedPersona === 'warm_supporter'
            ? '응원'
            : selectedPersona === 'calm_analyst'
              ? '분석'
              : '캐주얼';

  return (
    <header className="app-header">
      <div className="hd-left">
        <div className="crumbs">
          <span>MVP</span>
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M9 6l6 6-6 6" />
          </svg>
          <span className="crumb-current">{title}</span>
        </div>
        <h1 className="hd-title">{title}</h1>
        {subtitle && <p className="hd-sub">{subtitle}</p>}
      </div>
      <div className="hd-right">
        {onGenerate && (
          <button type="button" className="btn primary" onClick={onGenerate}>
            <Plus size={14} /> 새 댓글 추천
          </button>
        )}
        <div className="avatar-persona-wrap">
          <button
            type="button"
            className="avatar avatar-button"
            aria-label="내 계정 설정"
            title="내 계정"
            onClick={() => navigate('/account')}
          >
            JY
          </button>
          <button
            type="button"
            className={'avatar-persona-badge' + (selectedPersona !== 'none' ? ' active' : '')}
            aria-label={`현재 페르소나: ${personaLabel}. 페르소나 선택으로 이동`}
            title={`페르소나: ${personaLabel}`}
            onClick={() => navigate('/persona')}
          >
            {personaBadge}
          </button>
        </div>
      </div>
    </header>
  );
}
