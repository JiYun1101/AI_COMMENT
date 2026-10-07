import { Activity, LayoutGrid, MessageSquare, UserRound } from 'lucide-react';
import type { ComponentType } from 'react';
import { useNavigate } from 'react-router-dom';

export type SidebarKey = 'dashboard' | 'comments' | 'reaction' | 'persona' | 'account';

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
  const navigate = useNavigate();

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
        <SidebarItem icon={Activity} label="영상 반응 미리보기" active={current === 'reaction'} onClick={() => navigate('/reaction-preview')} />
        <SidebarItem icon={LayoutGrid} label="대시보드" active={current === 'dashboard'} onClick={() => onNav('dashboard')} />
        <SidebarItem icon={UserRound} label="페르소나" active={current === 'persona'} onClick={() => onNav('persona')} />
      </div>

      <div className="side-footer">
        <div className="sidebar-note">
          <b>v0.5 LLM MVP</b>
          <span>맥락 분석은 코드, 댓글 생성은 LLM으로 처리합니다.</span>
        </div>
      </div>
    </aside>
  );
}
