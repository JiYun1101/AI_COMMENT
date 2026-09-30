import { Check, Eye, EyeOff, KeyRound, ShieldCheck, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  DEFAULT_OPENAI_MODEL,
  getStoredOpenAIApiKey,
  getStoredOpenAIModel,
  getStoredYouTubeApiKey,
  setStoredOpenAIApiKey,
  setStoredOpenAIModel,
  setStoredYouTubeApiKey,
} from '../api/client';
import { Header } from '../components/layout/Header';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';

export function AccountPage() {
  const navigate = useNavigate();
  const [youtubeKey, setYoutubeKey] = useState(() => getStoredYouTubeApiKey());
  const [openaiKey, setOpenaiKey] = useState(() => getStoredOpenAIApiKey());
  const [openaiModel, setOpenaiModel] = useState(() => getStoredOpenAIModel());
  const [showYouTubeKey, setShowYouTubeKey] = useState(false);
  const [showOpenAIKey, setShowOpenAIKey] = useState(false);
  const [saved, setSaved] = useState<'youtube' | 'openai' | null>(null);

  const handleNav = (key: SidebarKey) => {
    if (key === 'dashboard') navigate('/dashboard');
    if (key === 'comments') navigate('/');
  };

  const saveYouTube = () => {
    setStoredYouTubeApiKey(youtubeKey);
    setYoutubeKey(getStoredYouTubeApiKey());
    setSaved('youtube');
    window.setTimeout(() => setSaved((current) => (current === 'youtube' ? null : current)), 1800);
  };

  const clearYouTube = () => {
    setYoutubeKey('');
    setStoredYouTubeApiKey('');
    setSaved(null);
  };

  const saveOpenAI = () => {
    setStoredOpenAIApiKey(openaiKey);
    setStoredOpenAIModel(openaiModel || DEFAULT_OPENAI_MODEL);
    setOpenaiKey(getStoredOpenAIApiKey());
    setOpenaiModel(getStoredOpenAIModel());
    setSaved('openai');
    window.setTimeout(() => setSaved((current) => (current === 'openai' ? null : current)), 1800);
  };

  const clearOpenAI = () => {
    setOpenaiKey('');
    setStoredOpenAIApiKey('');
    setSaved(null);
  };

  return (
    <div className="app">
      <Sidebar current="account" onNav={handleNav} />
      <div className="main">
        <Header title="내 계정" subtitle="API 연결과 개인 실행 설정을 관리합니다." />

        <main className="account-page">
          <section className="account-intro">
            <div className="account-intro-icon"><ShieldCheck size={20} /></div>
            <div>
              <h2>API 연결</h2>
              <p>
                입력한 키는 이 브라우저의 localStorage에만 저장됩니다. GitHub 저장소나 서비스 DB에는 기록하지 않고,
                필요한 API 요청에만 HTTPS 헤더로 전달합니다.
              </p>
            </div>
          </section>

          <div className="account-grid">
            <section className="credential-card">
              <div className="credential-head">
                <div>
                  <span className="credential-kicker">YOUTUBE</span>
                  <h3>YouTube Data API Key</h3>
                  <p>영상 제목, 카테고리, 조회수 등 YouTube 공식 메타데이터를 불러올 때 사용합니다.</p>
                </div>
                <KeyRound size={20} />
              </div>

              <label className="account-label" htmlFor="youtube-api-key">API Key</label>
              <div className="secret-input">
                <input
                  id="youtube-api-key"
                  type={showYouTubeKey ? 'text' : 'password'}
                  autoComplete="off"
                  placeholder="AIza..."
                  value={youtubeKey}
                  onChange={(event) => setYoutubeKey(event.target.value)}
                />
                <button type="button" aria-label="YouTube API Key 표시 전환" onClick={() => setShowYouTubeKey((value) => !value)}>
                  {showYouTubeKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>

              <div className="credential-actions">
                <button type="button" className="btn primary" onClick={saveYouTube}>
                  {saved === 'youtube' ? <Check size={14} /> : null}
                  {saved === 'youtube' ? '저장됨' : '저장'}
                </button>
                <button type="button" className="btn ghost danger" onClick={clearYouTube} disabled={!youtubeKey}>
                  <Trash2 size={14} /> 삭제
                </button>
              </div>
            </section>

            <section className="credential-card">
              <div className="credential-head">
                <div>
                  <span className="credential-kicker">OPENAI</span>
                  <h3>OpenAI API Key</h3>
                  <p>영상 맥락을 기반으로 실제 댓글 후보를 생성할 때 사용합니다.</p>
                </div>
                <KeyRound size={20} />
              </div>

              <label className="account-label" htmlFor="openai-api-key">API Key</label>
              <div className="secret-input">
                <input
                  id="openai-api-key"
                  type={showOpenAIKey ? 'text' : 'password'}
                  autoComplete="off"
                  placeholder="sk-..."
                  value={openaiKey}
                  onChange={(event) => setOpenaiKey(event.target.value)}
                />
                <button type="button" aria-label="OpenAI API Key 표시 전환" onClick={() => setShowOpenAIKey((value) => !value)}>
                  {showOpenAIKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>

              <label className="account-label account-model-label" htmlFor="openai-model">모델</label>
              <input
                id="openai-model"
                className="account-text-input"
                type="text"
                value={openaiModel}
                onChange={(event) => setOpenaiModel(event.target.value)}
                placeholder={DEFAULT_OPENAI_MODEL}
              />
              <p className="account-field-note">기본값: {DEFAULT_OPENAI_MODEL}. 다른 Responses API 호환 모델 ID로 변경할 수 있습니다.</p>

              <div className="credential-actions">
                <button type="button" className="btn primary" onClick={saveOpenAI}>
                  {saved === 'openai' ? <Check size={14} /> : null}
                  {saved === 'openai' ? '저장됨' : '저장'}
                </button>
                <button type="button" className="btn ghost danger" onClick={clearOpenAI} disabled={!openaiKey}>
                  <Trash2 size={14} /> 삭제
                </button>
              </div>
            </section>
          </div>

          <section className="account-note">
            <strong>사용 방법</strong>
            <span>키를 저장한 뒤 상단 JY 아이콘 또는 왼쪽 메뉴로 댓글 추천 화면으로 돌아가면 바로 적용됩니다.</span>
          </section>
        </main>
      </div>
    </div>
  );
}
