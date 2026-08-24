import { Search, Bell, Plus } from 'lucide-react';

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
          <span>워크스페이스</span>
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M9 6l6 6-6 6" />
          </svg>
          <span className="crumb-current">{title}</span>
        </div>
        <h1 className="hd-title">{title}</h1>
        {subtitle && <p className="hd-sub">{subtitle}</p>}
      </div>
      <div className="hd-right">
        <div className="hd-search">
          <Search size={15} />
          <input placeholder="댓글 · 브랜드 · 유튜브 URL 검색" />
          <span className="kbd">⌘K</span>
        </div>
        <button type="button" className="icon-btn" title="알림">
          <Bell size={18} strokeWidth={1.75} />
          <span className="dot-alert" />
        </button>
        {onGenerate && (
          <button type="button" className="btn primary" onClick={onGenerate}>
            <Plus size={14} />
            댓글 생성
          </button>
        )}
        <div className="avatar">JY</div>
      </div>
    </header>
  );
}
