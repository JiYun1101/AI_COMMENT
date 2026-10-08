import {
  Activity,
  Cable,
  ChevronUp,
  LayoutGrid,
  MessageSquare,
  Settings2,
  Sparkles,
  UserRound,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { ComponentType } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAccountMode, getSelectedPersona } from '../../api/client';
import { getPersonaLabel } from '../../data/personas';

export type SidebarKey = 'dashboard' | 'comments' | 'reaction' | 'seed' | 'persona' | 'account';

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
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [accountOpen, setAccountOpen] = useState(false);
  const accountMode = getAccountMode();
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

  useEffect(() => {
    if (!accountOpen) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setAccountOpen(false);
    };
    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [accountOpen]);

  const go = (path: string) => {
    setAccountOpen(false);
    navigate(path);
  };

  return (
    <aside className="sidebar">
      <button type="button" className="brand brand-button" onClick={() => navigate('/about')} aria-label="AI_COMMENT 소개 페이지로 이동">
        <span className="brand-mark">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#fff" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 6h11a4 4 0 010 8H8l-4 4V6z" />
            <circle cx="18" cy="6" r="2.5" fill="#fff" stroke="none" />
          </svg>
        </span>
        <div className="brand-word">AI<em>_</em>COMMENT</div>
      </button>

      <div className="side-section">
        <div className="side-h">시청자 도구</div>
        <SidebarItem icon={MessageSquare} label="댓글 추천" active={current === 'comments'} onClick={() => onNav('comments')} />
        <SidebarItem icon={LayoutGrid} label="대시보드" active={current === 'dashboard'} onClick={() => onNav('dashboard')} />
        <SidebarItem icon={UserRound} label="페르소나" active={current === 'persona'} onClick={() => onNav('persona')} />

        <div className="side-divider" aria-hidden="true" />

        <div className="side-h side-h-creator">작성자 도구</div>
        <SidebarItem icon={Activity} label="영상 반응 미리보기" active={current === 'reaction'} onClick={() => navigate('/reaction-preview')} />
        <SidebarItem icon={Sparkles} label="맛있는 댓글 미리 달기" active={current === 'seed'} onClick={() => navigate('/creator-comment')} />
      </div>

      <div className="side-footer" ref={menuRef}>
        <div className="sidebar-note">
          <b>v0.5 LLM MVP</b>
          <span>시청자 댓글과 작성자용 커뮤니티 도구를 분리해 제공합니다.</span>
        </div>

        {accountOpen && (
          <div className="account-hub" role="menu" aria-label="계정 메뉴">
            <div className="account-hub-head">
              <span className="account-hub-avatar">JY</span>
              <div>
                <strong>JY workspace</strong>
                <span>{accountMode === 'personal' ? '개인 계정 사용 중' : '데모 계정 사용 중'}</span>
              </div>
              <span className="account-hub-status">{personaBadge}</span>
            </div>

            <div className="account-hub-grid">
              <button type="button" role="menuitem" onClick={() => go('/account')}>
                <span className="account-hub-icon"><Settings2 size={15} /></span>
                <span><strong>내 계정</strong><small>계정 모드 선택</small></span>
              </button>
              <button type="button" role="menuitem" onClick={() => go('/account/connect')}>
                <span className="account-hub-icon"><Cable size={15} /></span>
                <span><strong>연결 설정</strong><small>API · YouTube</small></span>
              </button>
              <button type="button" role="menuitem" onClick={() => go('/persona')}>
                <span className="account-hub-icon"><UserRound size={15} /></span>
                <span><strong>페르소나</strong><small>{personaLabel}</small></span>
              </button>
            </div>
          </div>
        )}

        <button
          type="button"
          className={`side-account${accountOpen ? ' open' : ''}${current === 'account' ? ' active' : ''}`}
          onClick={() => setAccountOpen((value) => !value)}
          aria-expanded={accountOpen}
          aria-haspopup="menu"
          aria-label="계정 메뉴 열기"
        >
          <span className="side-account-avatar-wrap">
            <span className="side-account-avatar">JY</span>
            <span className={`side-account-persona${selectedPersona !== 'none' ? ' active' : ''}`}>
              {personaBadge}
            </span>
          </span>
          <span className="side-account-copy">
            <strong>JY</strong>
            <span>{accountMode === 'personal' ? '개인 계정' : '데모 계정'} · {personaLabel}</span>
          </span>
          <ChevronUp className="side-account-chevron" size={16} />
        </button>
      </div>
    </aside>
  );
}
