import { Check, Copy, ExternalLink, Eye, EyeOff, KeyRound, Link2, LoaderCircle, ShieldCheck, Trash2, Unlink } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  DEFAULT_OPENAI_MODEL,
  connectServerWithCode,
  waitForHealthyBackend,
  verifyServerConnection,
  YOUTUBE_OAUTH_REDIRECT_URI,
  disconnectYouTubeOAuth,
  getStoredApiAccessToken,
  setStoredApiAccessToken,
  getStoredOpenAIApiKey,
  getStoredOpenAIModel,
  getStoredYouTubeApiKey,
  getStoredYouTubeOAuthClientId,
  getStoredYouTubeOAuthClientSecret,
  getYouTubeOAuthStatus,
  setAccountMode,
  setStoredOpenAIApiKey,
  setStoredOpenAIModel,
  setStoredYouTubeApiKey,
  setStoredYouTubeOAuthClientId,
  setStoredYouTubeOAuthClientSecret,
  startYouTubeOAuth,
} from '../api/client';
import { Header } from '../components/layout/Header';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import type { YouTubeOAuthStatus } from '../types/comment';

export function AccountPage() {
  const navigate = useNavigate();
  const [serverToken, setServerToken] = useState(() => getStoredApiAccessToken());
  const [pairingCode, setPairingCode] = useState('');
  const [serverStatus, setServerStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [apiRetryAttempt, setApiRetryAttempt] = useState(0);
  const [apiRetryKey, setApiRetryKey] = useState(0);
  const [pairingAvailable, setPairingAvailable] = useState<boolean | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [serverBusy, setServerBusy] = useState(false);
  const [youtubeKey, setYoutubeKey] = useState(() => getStoredYouTubeApiKey());
  const [openaiKey, setOpenaiKey] = useState(() => getStoredOpenAIApiKey());
  const [openaiModel, setOpenaiModel] = useState(() => getStoredOpenAIModel());
  const [oauthClientId, setOauthClientId] = useState(() => getStoredYouTubeOAuthClientId());
  const [oauthClientSecret, setOauthClientSecret] = useState(() => getStoredYouTubeOAuthClientSecret());
  const [showYouTubeKey, setShowYouTubeKey] = useState(false);
  const [showOpenAIKey, setShowOpenAIKey] = useState(false);
  const [showOAuthSecret, setShowOAuthSecret] = useState(false);
  const [saved, setSaved] = useState<'youtube' | 'openai' | 'oauth' | 'server' | null>(null);
  const [oauthStatus, setOauthStatus] = useState<YouTubeOAuthStatus | null>(null);
  const [oauthBusy, setOauthBusy] = useState(false);
  const [oauthError, setOauthError] = useState<string | null>(null);
  const [redirectCopied, setRedirectCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // The invitation lives in the fragment (never transmitted over HTTP).
    // Remove it from the address bar immediately after reading.
    const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const invite = fragment.get('pair');
    if (invite) {
      setPairingCode(invite);
      window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search);
    }
    setApiStatus('checking');
    setApiRetryAttempt(0);
    setPairingAvailable(null);
    setServerStatus('checking');

    const checkConnection = async () => {
      // Render Free's sleeping backend must wake before protected auth checks.
      // Retried calls here are read-only GET /health; never repeat pairing POST.
      try {
        const health = await waitForHealthyBackend((attempt) => {
          if (!cancelled) setApiRetryAttempt(attempt);
        });
        if (cancelled) return;
        setApiStatus('online');
        setApiRetryAttempt(0);
        setPairingAvailable(health.auth?.pairing_available ?? null);
      } catch {
        if (!cancelled) {
          setApiStatus('offline');
          setServerStatus('disconnected');
          setOauthStatus(null);
        }
        return;
      }

      // A missing admin token means not paired, NOT that the API is offline.
      const token = getStoredApiAccessToken();
      if (!token) {
        if (!cancelled) {
          setServerStatus('disconnected');
          setOauthStatus(null);
        }
        return;
      }
      try {
        const verified = await verifyServerConnection(token);
        if (cancelled) return;
        setServerStatus(verified.connected ? 'connected' : 'disconnected');
        if (verified.connected) {
          try {
            const oauth = await getYouTubeOAuthStatus();
            if (!cancelled) setOauthStatus(oauth);
          } catch {
            if (!cancelled) setOauthStatus(null);
          }
        }
      } catch {
        if (!cancelled) {
          setServerStatus('disconnected');
          setOauthStatus(null);
        }
      }
    };

    void checkConnection();
    return () => { cancelled = true; };
  }, [apiRetryKey]);

  const pairServer = async () => {
    setServerBusy(true);
    setServerError(null);
    try {
      await waitForHealthyBackend();
      const response = await connectServerWithCode(pairingCode);
      setServerToken(response.access_token);
      setPairingCode('');
      setServerStatus('connected');
      void getYouTubeOAuthStatus().then(setOauthStatus).catch(() => setOauthStatus(null));
    } catch (error) {
      setServerStatus('disconnected');
      setServerError(error instanceof Error ? error.message : '서버 연결에 실패했습니다.');
    } finally {
      setServerBusy(false);
    }
  };

  const saveServerToken = async () => {
    setServerBusy(true);
    setServerError(null);
    try {
      await waitForHealthyBackend();
      const verified = await verifyServerConnection(serverToken);
      if (!verified.connected) throw new Error('유효하지 않은 관리자 인증 토큰입니다.');
      setStoredApiAccessToken(serverToken);
      setServerStatus('connected');
      markSaved('server');
      void getYouTubeOAuthStatus().then(setOauthStatus).catch(() => setOauthStatus(null));
    } catch (error) {
      setServerStatus('disconnected');
      setServerError(error instanceof Error ? error.message : '서버 인증에 실패했습니다.');
    } finally {
      setServerBusy(false);
    }
  };

  const handleNav = (key: SidebarKey) => {
    if (key === 'dashboard') navigate('/dashboard');
    if (key === 'comments') navigate('/');
    if (key === 'persona') navigate('/persona');
  };

  const markSaved = (target: 'youtube' | 'openai' | 'oauth' | 'server') => {
    setSaved(target);
    window.setTimeout(() => setSaved((current) => (current === target ? null : current)), 1800);
  };

  const saveYouTube = () => {
    setStoredYouTubeApiKey(youtubeKey);
    setYoutubeKey(getStoredYouTubeApiKey());
    markSaved('youtube');
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
    markSaved('openai');
  };

  const clearOpenAI = () => {
    setOpenaiKey('');
    setStoredOpenAIApiKey('');
    setSaved(null);
  };

  const saveOAuth = () => {
    setStoredYouTubeOAuthClientId(oauthClientId);
    setStoredYouTubeOAuthClientSecret(oauthClientSecret);
    setOauthClientId(getStoredYouTubeOAuthClientId());
    setOauthClientSecret(getStoredYouTubeOAuthClientSecret());
    setOauthError(null);
    markSaved('oauth');
  };

  const clearOAuth = async () => {
    try {
      if (oauthStatus?.authorized) {
        const status = await disconnectYouTubeOAuth();
        setOauthStatus(status);
      }
    } catch {
      // Local credential removal should still work if the server is unavailable.
    }
    setOauthClientId('');
    setOauthClientSecret('');
    setStoredYouTubeOAuthClientId('');
    setStoredYouTubeOAuthClientSecret('');
    setOauthStatus(null);
    setOauthError(null);
    setSaved(null);
  };

  const copyRedirectUri = async () => {
    try {
      await navigator.clipboard.writeText(YOUTUBE_OAUTH_REDIRECT_URI);
      setRedirectCopied(true);
      window.setTimeout(() => setRedirectCopied(false), 1500);
    } catch {
      setOauthError('Redirect URI를 복사하지 못했습니다. 직접 선택해 복사해주세요.');
    }
  };

  const connectYouTube = async () => {
    setOauthError(null);
    if (serverStatus !== 'connected') {
      setOauthError('YouTube OAuth 연결 전에 먼저 위쪽 SERVER CONNECTION에서 관리자 서버 인증을 완료해주세요.');
      return;
    }
    setOauthBusy(true);
    let popup: Window | null = null;
    try {
      setStoredYouTubeOAuthClientId(oauthClientId);
      setStoredYouTubeOAuthClientSecret(oauthClientSecret);
      if (!oauthClientId.trim() || !oauthClientSecret.trim()) {
        throw new Error('OAuth Client ID와 Client Secret을 먼저 입력해주세요.');
      }

      popup = window.open('about:blank', 'youtube-oauth', 'width=520,height=720');
      if (!popup) {
        throw new Error('브라우저가 OAuth 팝업을 차단했습니다. 팝업을 허용해주세요.');
      }

      const { authorization_url } = await startYouTubeOAuth();
      popup.location.href = authorization_url;

      const deadline = Date.now() + 120_000;
      while (Date.now() < deadline) {
        await new Promise<void>((resolve) => window.setTimeout(resolve, 1200));
        const status = await getYouTubeOAuthStatus();
        setOauthStatus(status);
        if (status.authorized) {
          if (!popup.closed) popup.close();
          setAccountMode('personal');
          markSaved('oauth');
          return;
        }
      }
      throw new Error('YouTube 계정 인증 시간이 초과되었습니다. 다시 시도해주세요.');
    } catch (error) {
      if (popup && !popup.closed) popup.close();
      setOauthError(error instanceof Error ? error.message : 'YouTube 계정 연결에 실패했습니다.');
    } finally {
      setOauthBusy(false);
    }
  };

  const disconnectYouTube = async () => {
    setOauthBusy(true);
    setOauthError(null);
    try {
      const status = await disconnectYouTubeOAuth();
      setOauthStatus(status);
    } catch (error) {
      setOauthError(error instanceof Error ? error.message : 'YouTube 계정 연결 해제에 실패했습니다.');
    } finally {
      setOauthBusy(false);
    }
  };

  return (
    <div className="app">
      <Sidebar current="account" onNav={handleNav} />
      <div className="main">
        <Header title="내 계정 추가하기" subtitle="개인 API Key와 YouTube 계정을 연결합니다." />

        <main className="account-page">
          <section className="account-intro">
            <div className="account-intro-icon"><ShieldCheck size={20} /></div>
            <div>
              <h2>개인 계정 연결</h2>
              <p>
                입력한 키와 OAuth 자격증명은 이 브라우저의 localStorage에만 저장됩니다. GitHub 저장소에는 기록하지 않고,
                필요한 API 요청에만 HTTPS 헤더로 전달합니다. 서버 토큰과 OAuth 자격증명은 브라우저 보안 설정에 유의해야 합니다.
              </p>
            </div>
          </section>

          <div className="account-grid">
             <section className="credential-card">
              <div className="credential-head">
                <div>
                  <span className="credential-kicker">SERVER CONNECTION</span>
                  <h3>서버 연결</h3>
                  <p>API 접속과 관리자 인증은 별개입니다. 일반적인 영상 조회·댓글 추천은 서버가 온라인이면 사용할 수 있습니다.
                    스냅샷 저장·모델 데이터 조회 등 보호된 기능은 별도 관리자 연결이 필요합니다.</p>
                </div>
                <ShieldCheck size={20} />
              </div>
              <div role="status" className={'server-connection-status ' + (apiStatus === 'online' ? 'connected' : apiStatus === 'checking' ? 'checking' : 'disconnected')}>
                {apiStatus === 'online' ? 'API 서버 온라인' : apiStatus === 'checking' ? apiRetryAttempt > 0 ? `Render 백엔드 재기동 확인 중 (${apiRetryAttempt}/4)` : 'API 서버 확인 중' : 'API 서버 접속 실패'}
              </div>
              {apiStatus === 'offline' && (
                <div className="account-field-note" role="status">
                  Render 무료 서버가 일시 중지됐거나 프록시 연결에 실패했을 수 있습니다.
                  <button type="button" className="btn secondary sm" onClick={() => setApiRetryKey((value) => value + 1)}>
                    API 서버 다시 확인
                  </button>
                </div>
              )}
              <div className={'server-connection-status ' + serverStatus} role="status">
                {serverStatus === 'connected' ? '관리자 인증 연결됨' : serverStatus === 'checking' ? '관리자 인증 확인 중' : '관리자 인증 미연결 (일반 API와 별개)'}
              </div>
              <p className="account-field-note">관리자 연결은 비공개 초대 코드나 기존 인증 토큰을 가진 소유자만 사용할 수 있습니다.</p>
              {pairingAvailable === false && (
                <p className="account-field-note" role="status">
                  현재 서버에서는 초대 코드 발급 기능이 비활성화돼 있습니다.
                  아래 ‘기존 서버 토큰으로 연결’을 열어 소유자에게 발급된 인증 토큰으로 연결하세요.
                  토큰이 없다면 서버 관리자가 Render에서 별도 인증 구성을 해야 합니다.
                  공개 채팅에 관리자 토큰을 붙여넣지 마세요.
                </p>
              )}
              <label className="account-label" htmlFor="server-pairing-code">서버 연결 코드</label>
              <div className="secret-input">
                <input id="server-pairing-code" type="password" autoComplete="off"
                  placeholder="초대 링크에서 자동 입력되거나 연결 코드 입력" value={pairingCode}
                  onChange={(event) => setPairingCode(event.target.value)} />
              </div>
              <div className="credential-actions">
                <button type="button" className="btn primary"
                  disabled={serverBusy || pairingAvailable === false || pairingCode.trim().length < 32}
                  onClick={() => void pairServer()}>
                  {serverBusy ? <LoaderCircle size={15} className="spin" /> : <Link2 size={15} />}
                  서버 연결하기
                </button>
                {serverStatus === 'connected' && (
                  <button type="button" className="btn ghost danger" onClick={() => {
                    setStoredApiAccessToken('');
                    setServerToken('');
                    setPairingCode('');
                    setServerStatus('disconnected');
                    setServerError(null);
                  }}>이 브라우저 연결 해제</button>
                )}
              </div>
              {serverError && <div className="oauth-error" role="alert">{serverError}</div>}
              <details className="server-advanced" open={pairingAvailable === false}>
                <summary>기존 서버 토큰으로 연결</summary>
                <label className="account-label" htmlFor="api-access-token">Access Token</label>
                <div className="secret-input">
                  <input id="api-access-token" type="password" autoComplete="off"
                    placeholder="이미 발급된 서버 토큰" value={serverToken}
                    onChange={(event) => setServerToken(event.target.value)} />
                </div>
                <div className="credential-actions">
                  <button type="button" className="btn secondary"
                    disabled={serverBusy || !serverToken.trim()}
                    onClick={() => void saveServerToken()}>
                    {saved === 'server' ? '인증 확인됨' : '인증 확인 후 저장'}
                  </button>
                </div>
              </details>
            </section>
           <section className="credential-card">
              <div className="credential-head">
                <div>
                  <span className="credential-kicker">YOUTUBE DATA</span>
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

            <section className="credential-card oauth-card">
              <div className="credential-head">
                <div>
                  <span className="credential-kicker">YOUTUBE OAUTH</span>
                  <h3>YouTube 계정 연결 / 댓글 게시</h3>
                  <p>내 YouTube 계정으로 실제 댓글을 게시하기 위한 Google OAuth 2.0 Web application 자격증명입니다.</p>
                </div>
                <Link2 size={20} />
              </div>

              <div className="oauth-status-row">
                <span className={`oauth-status-dot${oauthStatus?.authorized ? ' connected' : ''}`} />
                <span>{serverStatus !== 'connected'
                  ? '서버 관리자 인증 필요 · YouTube 연결 상태 미확인'
                  : oauthStatus?.authorized ? 'YouTube 계정 연결됨' : 'YouTube 계정 연결 안 됨'}</span>
              </div>
              {serverStatus !== 'connected' && (
                <p className="account-field-note" role="status">
                  이 기능은 Google OAuth 전에 AI_COMMENT 서버 관리자 인증이 필요합니다.
                  위쪽 SERVER CONNECTION의 비공개 초대 코드 또는 기존 인증 토큰으로 먼저 연결하세요.
                  이메일 회원 로그인 및 YouTube Data API Key로는 이 인증을 대신할 수 없습니다.
                </p>
              )}

              <div className="oauth-fields">
                <div>
                  <label className="account-label" htmlFor="youtube-oauth-client-id">OAuth Client ID</label>
                  <input
                    id="youtube-oauth-client-id"
                    className="account-text-input"
                    type="text"
                    autoComplete="off"
                    placeholder="...apps.googleusercontent.com"
                    value={oauthClientId}
                    onChange={(event) => setOauthClientId(event.target.value)}
                  />
                </div>

                <div>
                  <label className="account-label" htmlFor="youtube-oauth-client-secret">OAuth Client Secret</label>
                  <div className="secret-input">
                    <input
                      id="youtube-oauth-client-secret"
                      type={showOAuthSecret ? 'text' : 'password'}
                      autoComplete="off"
                      placeholder="GOCSPX-..."
                      value={oauthClientSecret}
                      onChange={(event) => setOauthClientSecret(event.target.value)}
                    />
                    <button type="button" aria-label="OAuth Client Secret 표시 전환" onClick={() => setShowOAuthSecret((value) => !value)}>
                      {showOAuthSecret ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
              </div>

              <label className="account-label account-model-label" htmlFor="youtube-oauth-redirect-uri">승인된 리디렉션 URI</label>
              <div className="redirect-uri-row">
                <input id="youtube-oauth-redirect-uri" className="account-text-input" type="text" readOnly value={YOUTUBE_OAUTH_REDIRECT_URI} />
                <button type="button" className="btn secondary" onClick={copyRedirectUri}>
                  {redirectCopied ? <Check size={14} /> : <Copy size={14} />}
                  {redirectCopied ? '복사됨' : '복사'}
                </button>
              </div>
              <p className="account-field-note">Google Cloud의 OAuth 클라이언트 → 승인된 리디렉션 URI에 위 주소를 정확히 추가하세요.</p>

              {oauthError && <div className="oauth-error">{oauthError}</div>}

              <div className="credential-actions oauth-actions">
                <button type="button" className="btn secondary" onClick={saveOAuth}>
                  {saved === 'oauth' ? <Check size={14} /> : null}
                  {saved === 'oauth' ? '저장됨' : '자격증명 저장'}
                </button>
                {oauthStatus?.authorized ? (
                  <button type="button" className="btn ghost danger" onClick={disconnectYouTube} disabled={oauthBusy}>
                    {oauthBusy ? <LoaderCircle size={14} className="spin" /> : <Unlink size={14} />}
                    연결 해제
                  </button>
                ) : (
                  <button type="button" className="btn primary" onClick={connectYouTube} disabled={oauthBusy || serverStatus !== 'connected'}>
                    {oauthBusy ? <LoaderCircle size={14} className="spin" /> : <Link2 size={14} />}
                    YouTube 계정 연결
                  </button>
                )}
                <button type="button" className="btn ghost danger" onClick={clearOAuth} disabled={!oauthClientId && !oauthClientSecret && !oauthStatus?.authorized}>
                  <Trash2 size={14} /> 자격증명 삭제
                </button>
                <a className="btn ghost account-external-link" href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noreferrer">
                  <ExternalLink size={14} /> Google Cloud
                </a>
              </div>
            </section>
          </div>

          <section className="account-note">
            <strong>사용 방법</strong>
            <span>YouTube OAuth 연결이 완료되면 게시 계정이 자동으로 개인 계정으로 전환됩니다. 데모 계정으로 돌아가려면 상단 JY → 계정에서 데모 계정을 선택하세요.</span>
          </section>
        </main>
      </div>
    </div>
  );
}