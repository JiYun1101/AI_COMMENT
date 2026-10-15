import { Check, ExternalLink, LoaderCircle, MessageSquareReply, RefreshCw, Sparkles, Send } from 'lucide-react';
import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '../components/layout/Header';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import {
  getAccountMode, getAutoReplyCandidates, postViewerReply, suggestAutoReply,
  type AutoReplyCandidate, type AutoReplyCandidatesResponse,
} from '../api/client';
import { isValidYouTubeVideoUrl } from '../utils/youtube';

type Suggestion = {
  drafts: string[];
  text: string;
  selected: boolean;
  generating?: boolean;
  postedUrl?: string | null;
  error?: string;
  uncertain?: boolean;
};

const CATEGORY: Record<string, string> = {
  question: '질문', praise: '공감', other: '의견', complaint: '개선 의견',
};

export function ViewerRepliesPage() {
  const navigate = useNavigate();
  const mode = getAccountMode();
  const [videoUrl, setVideoUrl] = useState('');
  const [data, setData] = useState<AutoReplyCandidatesResponse | null>(null);
  const [suggestions, setSuggestions] = useState<Record<string, Suggestion>>({});
  const [loading, setLoading] = useState(false);
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const actionLock = useRef(false);

  // Existing single-comment posting remains available for any valid parent ID.
  const [manualParent, setManualParent] = useState('');
  const [manualText, setManualText] = useState('');
  const [manualBusy, setManualBusy] = useState(false);
  const [manualDone, setManualDone] = useState<string | null>(null);
  const [manualError, setManualError] = useState('');
  const [manualUncertain, setManualUncertain] = useState(false);

  const manualId = (() => {
    try { return new URL(manualParent).searchParams.get('lc') || ''; }
    catch { return manualParent.trim(); }
  })();
  const validManual = /^[A-Za-z0-9_.-]{5,100}$/.test(manualId);

  const patch = (id: string, update: Partial<Suggestion>) =>
    setSuggestions(current => ({
      ...current,
      [id]: { drafts: [], text: '', selected: false, ...current[id], ...update },
    }));

  const generateFor = async (videoId: string, row: AutoReplyCandidate, select: boolean) => {
    patch(row.parent_id, { generating: true, error: undefined });
    try {
      const result = await suggestAutoReply({ video_id: videoId, parent_id: row.parent_id });
      patch(row.parent_id, {
        drafts: result.drafts,
        text: result.drafts[0] || '',
        selected: select && result.drafts.length > 0,
        generating: false,
      });
    } catch (cause) {
      patch(row.parent_id, {
        generating: false,
        error: cause instanceof Error ? cause.message : '추천을 생성하지 못했습니다.',
      });
    }
  };

  const load = async () => {
    if (actionLock.current || mode !== 'personal' || !isValidYouTubeVideoUrl(videoUrl)) return;
    actionLock.current = true;
    setLoading(true);
    setError('');
    setNotice('');
    setData(null);
    setSuggestions({});
    try {
      const response = await getAutoReplyCandidates(videoUrl.trim());
      setData(response);
      const top = response.items.slice(0, 3);
      for (const row of top) {
        await generateFor(response.video.video_id, row, true);
      }
      setNotice(response.items.length
        ? '상위 댓글의 대댓글 초안을 만들었습니다. 내용을 확인한 후 선택 게시하세요.'
        : '확인한 댓글 중 안전하게 추천할 수 있는 대댓글 대상이 없습니다.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '댓글을 불러오지 못했습니다.');
    } finally {
      actionLock.current = false;
      setLoading(false);
    }
  };

  const checked = (data?.items ?? []).filter(item => {
    const suggestion = suggestions[item.parent_id];
    return suggestion?.selected && suggestion.text.trim() && !suggestion.postedUrl && !suggestion.uncertain;
  });

  const publishSelected = async () => {
    if (actionLock.current || posting || mode !== 'personal' || checked.length === 0) return;
    if (checked.length > 3) {
      setError('한 번에 최대 3개의 대댓글만 게시할 수 있습니다.');
      return;
    }
    if (!window.confirm(`선택한 ${checked.length}개 대댓글을 내 YouTube 계정으로 실제 게시할까요? 각 문구를 확인했는지 점검해주세요.`)) return;
    actionLock.current = true;
    setPosting(true);
    setError('');
    let succeeded = 0;
    for (const row of checked) {
      const id = row.parent_id;
      const text = suggestions[id]?.text.trim();
      if (!text) continue;
      try {
        const result = await postViewerReply({ parent_id: id, text });
        patch(id, { postedUrl: result.comment_url, selected: false, error: undefined });
        succeeded++;
      } catch (cause) {
        // A timeout can occur AFTER YouTube accepted a comment. Never retry automatically.
        patch(id, {
          selected: false, uncertain: true,
          error: (cause instanceof Error ? cause.message : '게시 결과를 확인하지 못했습니다.') +
            ' — YouTube에서 게시 여부를 확인한 뒤 다시 시도해주세요.',
        });
      }
    }
    setNotice(`게시 확인 ${succeeded}개 / 시도 ${checked.length}개. 실패한 항목은 자동으로 재시도하지 않습니다.`);
    setPosting(false);
    actionLock.current = false;
  };

  const manualPost = async () => {
    if (manualBusy || manualUncertain || mode !== 'personal' || !validManual || !manualText.trim()) return;
    if (!window.confirm('이 대댓글을 YouTube에 실제로 게시할까요?')) return;
    setManualBusy(true); setManualError('');
    try {
      const result = await postViewerReply({ parent_id: manualId, text: manualText.trim() });
      setManualDone(result.comment_url);
      setManualText('');
    } catch (cause) {
      setManualUncertain(true);
      setManualError((cause instanceof Error ? cause.message : '게시 결과를 확인하지 못했습니다.') +
        ' YouTube에서 게시 여부를 확인해주세요. 중복 게시 방지를 위해 이 화면에서 재시도는 막았습니다.');
    } finally { setManualBusy(false); }
  };

  const onNav = (key: SidebarKey) => {
    const paths: Partial<Record<SidebarKey, string>> = {
      comments: '/', dashboard: '/dashboard', persona: '/persona', account: '/account',
    };
    navigate(paths[key] || '/');
  };

  return (
    <div className="app">
      <Sidebar current="viewer-replies" onNav={onNav} />
      <div className="main">
        <Header
          title="대댓글 자동 달기"
          subtitle="영상의 실제 댓글을 분석해 어울리는 대댓글을 추천하고, 선택한 초안을 YouTube에 게시합니다."
        />
        <main className="content eng-page">
          <section className="eng-panel auto-reply-panel">
            <div className="eng-panel-head">
              <h3><Sparkles size={17} /> AI 대댓글 추천</h3>
              <small>시청자 모드 · 댓글 검토 후 게시</small>
            </div>
            {mode !== 'personal' && (
              <div className="inline-status error">
                개인 YouTube 계정으로 연결해야 게시할 수 있습니다.
                <button type="button" className="btn secondary sm" onClick={() => navigate('/account/connect')}>연결 설정</button>
              </div>
            )}
            <label htmlFor="auto-reply-video">댓글을 찾을 YouTube 영상 URL</label>
            <div className="auto-reply-input-row">
              <input id="auto-reply-video" type="url" className="account-text-input"
                placeholder="https://www.youtube.com/watch?v=..."
                value={videoUrl} disabled={loading || posting}
                onChange={e => { setVideoUrl(e.target.value); setData(null); setSuggestions({}); setNotice(''); }} />
              <button type="button" className="btn primary" disabled={loading || posting || mode !== 'personal' || !isValidYouTubeVideoUrl(videoUrl)} onClick={() => void load()}>
                {loading ? <LoaderCircle size={15} className="spin" /> : <Sparkles size={15} />}
                {loading ? '댓글 분석 중...' : '댓글 찾아 AI 추천'}
              </button>
            </div>
            <p className="eng-note">
              댓글 최대 40개에서 적합한 후보 6개를 고르고, 상위 3개에 답글 초안을 생성합니다.
              내용에 따라 추천할 댓글이 없을 수 있습니다. 댓글 수·위험도 등을 고려한 휴리스틱 우선순위이며 실제 AI 품질 점수는 아닙니다.
            </p>
            {error && <div className="inline-status error" role="alert">{error}</div>}
            {notice && <div className="inline-status" role="status">{notice}</div>}
          </section>

          {data && (
            <section className="eng-panel auto-reply-panel">
              <div className="eng-panel-head">
                <div>
                  <h3>{data.video.title}</h3>
                  <small>{data.video.channel} · {data.scanned_count}개 댓글 확인 · {data.items.length}개 추천 후보</small>
                </div>
                <a target="_blank" rel="noopener noreferrer" href={`https://www.youtube.com/watch?v=${data.video.video_id}`}>영상 보기 <ExternalLink size={13} /></a>
              </div>
              {data.items.length === 0 && <p className="eng-muted">조건에 맞는 댓글이 없습니다. 다른 영상을 선택해 보세요.</p>}
              <div className="auto-reply-list">
                {data.items.map(item => {
                  const suggestion = suggestions[item.parent_id];
                  const ready = Boolean(suggestion?.text.trim()) && !suggestion?.postedUrl && !suggestion?.uncertain;
                  return (
                    <article key={item.parent_id} className="auto-reply-item">
                      <div className="auto-reply-row">
                        <span className="eng-flag">{CATEGORY[item.category] || '댓글'}</span>
                        <strong>{item.author}</strong>
                        <span className="eng-muted">추천 우선순위 {item.match_score}</span>
                        <a target="_blank" rel="noopener noreferrer"
                          href={`https://www.youtube.com/watch?v=${data.video.video_id}&lc=${encodeURIComponent(item.parent_id)}`}>
                          원본 <ExternalLink size={12} />
                        </a>
                      </div>
                      <p className="auto-reply-original">{item.comment}</p>
                      {!suggestion?.drafts.length && !suggestion?.generating && !suggestion?.postedUrl && (
                        <button type="button" className="btn secondary sm" disabled={loading || posting}
                          onClick={() => void generateFor(data.video.video_id, item, false)}>
                          <Sparkles size={13} /> 이 댓글에 AI 답글 추천
                        </button>
                      )}
                      {suggestion?.generating && <span className="eng-muted"><LoaderCircle className="spin" size={14} /> AI 초안 생성 중...</span>}
                      {Boolean(suggestion?.drafts.length) && !suggestion?.postedUrl && !suggestion?.uncertain && (
                        <div className="auto-reply-compose">
                          <div className="auto-reply-drafts">
                            {suggestion!.drafts.map((draft, index) => (
                              <button key={index} type="button" className={suggestion!.text === draft ? 'active' : ''}
                                disabled={posting} onClick={() => patch(item.parent_id, { text: draft })}>
                                초안 {index + 1} · {draft}
                              </button>
                            ))}
                          </div>
                          <textarea className="account-text-input" aria-label={`${item.author}에게 작성할 대댓글`}
                            maxLength={2000} rows={3} value={suggestion!.text} disabled={posting}
                            onChange={e => patch(item.parent_id, { text: e.target.value })} />
                          <label className="auto-reply-select">
                            <input type="checkbox" checked={Boolean(suggestion!.selected)} disabled={!ready || posting}
                              onChange={e => patch(item.parent_id, { selected: e.target.checked })} />
                            이 대댓글 게시 대상으로 선택
                          </label>
                        </div>
                      )}
                      {suggestion?.postedUrl !== undefined && suggestion?.postedUrl !== null && (
                        <p className="inline-status"><Check size={14} /> 게시 완료
                          <a href={suggestion.postedUrl} target="_blank" rel="noopener noreferrer">댓글 보기</a>
                        </p>
                      )}
                      {suggestion?.error && <div className="inline-status error" role="alert">{suggestion.error}</div>}
                    </article>
                  );
                })}
              </div>
              {!!data.items.length && (
                <div className="auto-reply-footer">
                  <p className="eng-note">선택한 문구만 게시합니다. 한 번에 최대 3개, 실패 항목은 자동 재시도하지 않습니다.</p>
                  <button type="button" className="btn primary" disabled={posting || loading || checked.length === 0 || checked.length > 3}
                    onClick={() => void publishSelected()}>
                    {posting ? <LoaderCircle size={15} className="spin" /> : <Send size={15} />}
                    {posting ? 'YouTube 게시 중...' : `선택한 ${checked.length}개 대댓글 게시`}
                  </button>
                </div>
              )}
            </section>
          )}

          <section className="eng-panel auto-reply-panel">
            <div className="eng-panel-head">
              <h3><MessageSquareReply size={17} /> 직접 대댓글 달기</h3>
              <small>기존 댓글 ID로 직접 답글을 작성할 수도 있어요</small>
            </div>
            <label htmlFor="viewer-parent">원본 댓글 링크 또는 댓글 ID</label>
            <input id="viewer-parent" className="account-text-input" value={manualParent}
              disabled={manualBusy || manualUncertain} onChange={e => { setManualParent(e.target.value); setManualDone(null); }}
              placeholder="https://www.youtube.com/watch?v=...&lc=..." />
            <label htmlFor="viewer-reply">대댓글 내용</label>
            <textarea id="viewer-reply" className="account-text-input" value={manualText}
              disabled={manualBusy || manualUncertain} onChange={e => setManualText(e.target.value)}
              maxLength={2000} rows={3} placeholder="원본 댓글에 맞는 내용을 직접 작성하세요." />
            <button type="button" className="btn secondary" onClick={() => void manualPost()}
              disabled={manualBusy || manualUncertain || mode !== 'personal' || !validManual || !manualText.trim()}>
              {manualBusy ? <LoaderCircle size={14} className="spin" /> : <Send size={14} />} 직접 게시
            </button>
            {manualError && <div className="inline-status error" role="alert">{manualError}</div>}
            {manualDone && <div className="inline-status">게시 완료!
              <a href={manualDone} target="_blank" rel="noopener noreferrer">YouTube에서 보기</a>
            </div>}
          </section>
        </main>
      </div>
    </div>
  );
}
