import { Plus } from 'lucide-react';

interface HeaderProps {
  title: string;
  subtitle?: string;
  onGenerate?: () => void;
}

export function Header({ title, subtitle, onGenerate }: HeaderProps) {
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
        <div className="avatar" aria-label="사용자">JY</div>
      </div>
    </header>
  );
}
