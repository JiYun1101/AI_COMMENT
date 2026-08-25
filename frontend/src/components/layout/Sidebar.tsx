import { LayoutGrid, MessageSquare } from 'lucide-react';
import type { ComponentType } from 'react';

export type SidebarKey = 'dashboard' | 'comments';

interface SidebarItemProps {
  icon: ComponentType<{ size?: number | string }>;
  label: string;
  active?: boolean;
  onClick?: () => void;
}

function SidebarItem({ icon: Icon, label, active, onClick }: SidebarItemProps) {
  return (
    <button type="button" onClick={onClick} className={`side-item${active ? ' active' : ''}`}>
      <span className="side-ic"><Icon size={16} /></span>
      <span className="side-lbl">{label}</span>
    </button>
  );
}

interface SidebarProps {
  current: SidebarKey;
  onNav: (key: SidebarKey) => void;
}

export function Sidebar({ current, onNav }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#fff" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 6h11a4 4 0 010 8H8l-4 4V6z" />
            <circle cx="18" cy="6" r="2.5" fill="#fff" stroke="none" />
          </svg>
        </span>
        <div className="brand-word">AI<em>_</em>COMMENT</div>
      </div>

      <div className="side-section">
        <div className="side-h">MVP WORKSPACE</div>
        <SidebarItem icon={MessageSquare} label="댓글 추천" active={current === 'comments'} onClick={() => onNav('comments')} />
        <SidebarItem icon={LayoutGrid} label="대시보드" active={current === 'dashboard'} onClick={() => onNav('dashboard')} />
      </div>

      <div className="side-footer">
        <div className="sidebar-note">
          <b>v0.4 MVP</b>
          <span>실제 연결된 기능만 표시합니다.</span>
        </div>
      </div>
    </aside>
  );
}
