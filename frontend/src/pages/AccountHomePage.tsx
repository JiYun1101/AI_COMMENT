import { AlertCircle, ArrowRight, Gauge, ShieldCheck, UserPlus, Users } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getAccountMode,
  getYouTubeDemoStatus,
  setAccountMode,
} from '../api/client';
import { Header } from '../components/layout/Header';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import type { YouTubeDemoStatus } from '../types/comment';

export function AccountHomePage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState(() => getAccountMode());
  const [demoStatus, setDemoStatus] = useState<YouTubeDemoStatus | null>(null);
  const [demoError, setDemoError] = useState<string | null>(null);

  useEffect(() => {
    getYouTubeDemoStatus()
      .then((status) => {
        setDemoStatus(status);
        setDemoError(null);
      })
      .catch((error) => {
        setDemoStatus(null);
        setDemoError(error instanceof Error ? error.message : '데모 계정 상태를 확인하지 못했습니다.');
      });
  }, []);

  const handleNav = (key: SidebarKey) => {
    if (key === 'dashboard') navigate('/dashboard');
    if (key === 'comments') navigate('/');
    if (key === 'persona') navigate('/persona');
  };

  const useDemo = () => {
    setAccountMode('demo');
    setMode('demo');
    navigate('/');
  };

  return (
    <div className="app">
      <Sidebar current="account" onNav={handleNav} />
      <div className="main">
        <Header title="계정" subtitle="외부 테스트용 데모 계정 또는 개인 YouTube 계정을 선택합니다." />

        <main className="account-page account-home">
          <section className="account-intro">
            <div className="account-intro-icon"><ShieldCheck size={20} /></div>
            <div>
              <h2>게시 계정 선택</h2>
              <p>
                댓글 추천은 누구나 사용할 수 있습니다. 실제 YouTube 댓글 게시는 기본적으로 공용 데모 채널을 사용하며,
                개인 계정이 필요한 경우에만 별도 연결할 수 있습니다.
              </p>
            </div>
          </section>

          <div className="account-choice-grid">
            <section className="account-choice-card featured">
              <div className="account-choice-icon"><Users size={22} /></div>
              <div className="account-choice-copy">
                <div className="account-choice-title-row">
                  <span className="credential-kicker">PUBLIC DEMO</span>
                  {mode === 'demo' && <span className="account-mode-badge">현재 사용 중</span>}
                </div>
                <h3>데모 계정</h3>
                <p>
                  별도 Google 로그인 없이 테스트 채널로 실제 댓글 게시 흐름을 체험합니다.
                  외부 테스트를 위한 게시 횟수 제한이 적용됩니다.
                </p>

                <div className="demo-limit-box">
                  <Gauge size={16} />
                  {demoStatus ? (
                    <div>
                      <strong>방문자당 1시간 {demoStatus.hourly_limit}회 · 전체 24시간 {demoStatus.daily_limit}회</strong>
                      <span>
                        현재 남은 횟수: 내 브라우저 {demoStatus.remaining_hourly}회 · 전체 {demoStatus.remaining_daily}회
                      </span>
                    </div>
                  ) : (
                    <div>
                      <strong>게시 제한 적용</strong>
                      <span>상태 정보를 불러오는 중입니다.</span>
                    </div>
                  )}
                </div>

                {demoError && <div className="oauth-error">{demoError}</div>}
                {demoStatus && !demoStatus.ready && (
                  <div className="demo-setup-notice">
                    <AlertCircle size={15} />
                    <span>데모 채널 연결이 아직 완료되지 않았습니다. 테스트 채널 OAuth 설정 후 바로 활성화됩니다.</span>
                  </div>
                )}

                <button type="button" className="btn primary account-choice-action" onClick={useDemo}>
                  데모 계정 사용
                  <ArrowRight size={15} />
                </button>
              </div>
            </section>

            <section className="account-choice-card">
              <div className="account-choice-icon personal"><UserPlus size={22} /></div>
              <div className="account-choice-copy">
                <div className="account-choice-title-row">
                  <span className="credential-kicker">PERSONAL</span>
                  {mode === 'personal' && <span className="account-mode-badge">현재 사용 중</span>}
                </div>
                <h3>내 계정 추가하기</h3>
                <p>
                  내 API Key와 Google OAuth 자격증명을 연결해서 개인 YouTube 계정으로 댓글을 게시합니다.
                  개인 설정은 데모 계정과 분리됩니다.
                </p>

                <button
                  type="button"
                  className="btn secondary account-choice-action"
                  onClick={() => navigate('/account/connect')}
                >
                  내 계정 추가하기
                  <ArrowRight size={15} />
                </button>
              </div>
            </section>
          </div>

          <section className="account-note">
            <strong>외부 테스트 권장</strong>
            <span>공유 링크를 받은 사용자는 데모 계정을 그대로 사용하고, 개인 계정 연결은 필요한 사용자만 진행하면 됩니다.</span>
          </section>
        </main>
      </div>
    </div>
  );
}
