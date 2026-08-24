import {
  LayoutGrid,
  MessageSquare,
  Video,
  Tag,
  Download,
  Users,
  Settings,
  HelpCircle,
} from 'lucide-react';
import type { ComponentType } from 'react';

export type SidebarKey = 'dashboard' | 'comments' | 'videos' | 'brands' | 'exports';

interface SidebarItemProps {
  icon: ComponentType<{ size?: number | string }>;
  label: string;
  count?: string;
  active?: boolean;
  onClick?: () => void;
}

function SidebarItem({ icon: Icon, label, count, active, onClick }: SidebarItemProps) {
  return (
    <button type="button" onClick={onClick} className={`side-item${active ? ' active' : ''}`}>
      <span className="side-ic">
        <Icon size={16} />
      </span>
      <span className="side-lbl">{label}</span>
      {count != null && <span className="side-count">{count}</span>}
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
        <div className="brand-word">
          AI<em>_</em>COMMENT
        </div>
      </div>

      <div className="side-section">
        <div className="side-h">WORKSPACE</div>
        <SidebarItem icon={LayoutGrid} label="대시보드" active={current === 'dashboard'} onClick={() => onNav('dashboard')} />
        <SidebarItem icon={MessageSquare} label="댓글" count="3,214" active={current === 'comments'} onClick={() => onNav('comments')} />
        <SidebarItem icon={Video} label="영상 분석" active={current === 'videos'} onClick={() => onNav('videos')} />
        <SidebarItem icon={Tag} label="브랜드 & 키워드" active={current === 'brands'} onClick={() => onNav('brands')} />
        <SidebarItem icon={Download} label="내보내기" active={current === 'exports'} onClick={() => onNav('exports')} />
      </div>

      <div className="side-section">
        <div className="side-h">ORGANIZATION</div>
        <SidebarItem icon={Users} label="팀 & 멤버" onClick={() => {}} />
        <SidebarItem icon={Settings} label="설정" onClick={() => {}} />
      </div>

      <div className="side-footer">
        <SidebarItem icon={HelpCircle} label="문서 & 도움말" onClick={() => {}} />
        <div className="usage">
          <div className="usage-h">
            <span>이번 달 사용량</span>
            <span className="usage-pct">80%</span>
          </div>
          <div className="usage-bar">
            <div className="usage-fill" style={{ width: '80%' }} />
          </div>
          <div className="usage-meta">80,041 / 100,000 credits</div>
        </div>
      </div>
    </aside>
  );
}
