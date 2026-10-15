import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '../components/layout/Header';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import { getAccountMode, postViewerReply } from '../api/client';

export function ViewerRepliesPage() {
  const navigate = useNavigate();
  const [parent, setParent] = useState('');
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [postedUrl, setPostedUrl] = useState<string | null>(null);
  const mode = getAccountMode();
  const parentId = (() => {
    try { return new URL(parent).searchParams.get('lc') || ''; }
    catch { return parent.trim(); }
  })();
  const valid = /^[A-Za-z0-9_.-]{5,100}$/.test(parentId);
  const submit = async () => {
    if (busy || mode !== 'personal' || !valid || !body.trim()) return;
    setBusy(true); setError('');
    try {
      const result = await postViewerReply({ parent_id: parentId, text: body.trim() });
      setPostedUrl(result.comment_url);
      setBody('');
    } catch (e) { setError(e instanceof Error ? e.message : '대댓글 게시에 실패했습니다.'); }
    finally { setBusy(false); }
  };
  const onNav = (key: SidebarKey) => {
    const paths: Partial<Record<SidebarKey, string>> = { comments: '/', dashboard: '/dashboard', persona: '/persona', account: '/account' };
    navigate(paths[key] || '/');
  };
  return (
    <div className="app">
      <Sidebar current="viewer-replies" onNav={onNav} />
      <div className="main">
        <Header title="대댓글 달기" subtitle="다른 사용자의 YouTube 댓글에 내 계정으로 직접 답글을 작성합니다." />
        <main className="content eng-page">
          <section className="eng-panel" style={{ maxWidth: 720, display: 'grid', gap: 16 }}>
            <div className="eng-panel-head"><h3>댓글에 답글 달기</h3><small>해당 댓글의 YouTube 링크에서 'lc' 댓글 ID를 읽습니다.</small></div>
            {mode !== 'personal' && <div className="inline-status error">개인 YouTube 계정 연결이 필요합니다. <button className="btn secondary sm" onClick={() => navigate('/account/connect')}>연결 설정</button></div>}
            <label htmlFor="viewer-parent">답글을 달 댓글 링크 또는 댓글 ID</label>
            <input id="viewer-parent" className="account-text-input" value={parent} onChange={e => { setParent(e.target.value); setPostedUrl(null); }} placeholder="https://www.youtube.com/watch?v=...&lc=..." />
            {parent && !valid && <span className="eng-muted">영상 댓글의 공유 링크 또는 댓글 ID를 입력해주세요.</span>}
            <label htmlFor="viewer-reply">대댓글 내용</label>
            <textarea id="viewer-reply" className="account-text-input" value={body} onChange={e => setBody(e.target.value)} maxLength={2000} rows={5} placeholder="상대 댓글에 달 답글을 작성하세요." />
            <button className="btn primary" type="button" disabled={busy || mode !== 'personal' || !valid || !body.trim()} onClick={() => void submit()}>{busy ? '게시 중…' : 'YouTube에 대댓글 게시'}</button>
            {error && <div className="inline-status error" role="alert">{error}</div>}
            {postedUrl && <div className="inline-status" role="status">게시 완료! <a href={postedUrl} target="_blank" rel="noopener noreferrer">YouTube에서 보기</a></div>}
            <p className="eng-note">이 기능은 내 채널 영상이 아니어도 대댓글을 게시할 수 있습니다. 다른 채널이 답글을 제한했거나 댓글을 삭제한 경우 게시에 실패할 수 있습니다.</p>
          </section>
        </main>
      </div>
    </div>
  );
}
