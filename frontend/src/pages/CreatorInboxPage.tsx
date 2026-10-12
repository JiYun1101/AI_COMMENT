import {
  AlertCircle,
  ArrowUpRight,
  Check,
  Copy,
  Inbox,
  LoaderCircle,
  MessageSquareReply,
  Send,
  Settings,
  ThumbsUp,
  Wand2,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAccountMode, getCreatorInbox, getReplyDrafts, getYouTubeOAuthStatus, postCreatorReply } from '../api/client';
import { Kpi } from '../components/dashboard/KpiStrip';
import { Header } from '../components/layout/Header';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import type { CreatorInboxResponse, InboxCategory, InboxItem, YouTubeOAuthStatus } from '../types/comment';
import { isValidYouTubeVideoUrl } from '../utils/youtube';

type FilterKey = 'needs_reply' | 'all' | InboxCategory;

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'needs_reply', label: '답 필요' },
  { key: 'all', label: '전체' },
  { key: 'question', label: '질문' },
  { key: 'complaint', label: '불만·개선 요청' },
  { key: 'risk', label: '확인 필요' },
  { key: 'praise', label: '칭찬·응원' },
  { key: 'other', label: '기타' },
];

const RISK_REASON_LABEL: Record<string, string> = {
  profanity: '욕설',
  hate_speech: '혐오 표현',
  threat: '위협',
  spam: '스팸·홍보',
  dispute: '분쟁 소지',
};

interface ReplyState {
  loading: boolean;
  source?: 'llm' | 'template';
  drafts: string[];
  text: string;
  posting: boolean;
  postedUrl?: string | null;
  posted?: boolean;
  error?: string;
}

export function CreatorInboxPage() {
  const navigate = useNavigate();
  const accountMode = getAccountMode();
  const [url, setUrl] = useState('');
  const [order, setOrder] = useState<'relevance' | 'time'>('relevance');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inbox, setInbox] = useState<CreatorInboxResponse | null>(null);
  const [filter, setFilter] = useState<FilterKey>('needs_reply');
  const [openId, setOpenId] = useState<string | null>(null);
  const [replies, setReplies] = useState<Record<string, ReplyState>>({});
  const [oauth, setOAuth] = useState<YouTubeOAuthStatus | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const urlValid = useMemo(() => isValidYouTubeVideoUrl(url), [url]);

  useEffect(() => {
    if (accountMode !== 'personal') return;
    getYouTubeOAuthStatus().then(setOAuth).catch(() => setOAuth(null));
  }, [accountMode]);

  const canPost = accountMode === 'personal' && Boolean(oauth?.authorized);
  const postBlockedReason =
    accountMode !== 'personal'
      ? '데모 계정은 답글을 게시할 수 없습니다. 초안을 복사해 직접 달거나 개인 계정으로 전환하세요.'
      : !oauth?.authorized
        ? '본인 YouTube 채널을 연결하면 이 화면에서 바로 답글을 게시할 수 있습니다.'
        : null;

  const load = async () => {
    if (!urlValid || loading) return;
    setLoading(true);
    setError(null);
    setInbox(null);
    setOpenId(null);
    setReplies({});
    try {
      const next = await getCreatorInbox(url.trim(), order);
      setInbox(next);
      setFilter(next.summary.needs_reply ? 'needs_reply' : 'all');
    } catch (err) {
      setError(err instanceof Error ? err.message : '받은 댓글을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const visible = useMemo(() => {
    const items = inbox?.items ?? [];
    if (filter === 'all') return items;
    if (filter === 'needs_reply') return items.filter((item) => item.needs_reply);
    return items.filter((item) => item.category === filter);
  }, [inbox, filter]);

  const filterCount = (key: FilterKey) => {
    if (!inbox) return 0;
    if (key === 'all') return inbox.summary.total;
    if (key === 'needs_reply') return inbox.summary.needs_reply;
    return inbox.summary.by_category[key];
  };

  const emptyReply: ReplyState = { loading: false, drafts: [], text: '', posting: false };
  const patchReply = (id: string, patch: Partial<ReplyState>) =>
    setReplies((current) => ({
      ...current,
      [id]: { ...emptyReply, ...current[id], ...patch },
    }));

  const openDrafts = async (item: InboxItem) => {
    setOpenId(item.id);
    if (replies[item.id]?.drafts.length) return;
    patchReply(item.id, { loading: true, error: undefined });
    try {
      const result = await getReplyDrafts({
        comment: item.text,
        category: item.category,
        video_title: inbox?.video.title,
      });
      patchReply(item.id, { loading: false, drafts: result.drafts, source: result.source, text: result.drafts[0] ?? '' });
    } catch (err) {
      patchReply(item.id, { loading: false, error: err instanceof Error ? err.message : '답글 초안을 만들지 못했습니다.' });
    }
  };

  const postReply = async (item: InboxItem) => {
    const state = replies[item.id];
    if (!state?.text.trim() || !canPost) return;
    patchReply(item.id, { posting: true, error: undefined });
    try {
      const result = await postCreatorReply({ parent_id: item.id, text: state.text.trim() });
      patchReply(item.id, { posting: false, posted: true, postedUrl: result.comment_url });
    } catch (err) {
      patchReply(item.id, { posting: false, error: err instanceof Error ? err.message : '답글 게시에 실패했습니다.' });
    }
  };

  const copyText = async (id: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      window.setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 1500);
    } catch {
      patchReply(id, { error: '클립보드에 복사하지 못했습니다.' });
    }
  };

  const handleNav = (key: SidebarKey) => {
    if (key === 'comments') navigate('/');
    if (key === 'dashboard') navigate('/dashboard');
    if (key === 'persona') navigate('/persona');
    if (key === 'account') navigate('/account');
  };

  return (
    <div className="app">
      <Sidebar current="inbox" onNav={handleNav} />
      <div className="main">
        <Header
          title="받은 댓글함"
          subtitle="내 영상에 달린 댓글을 질문·불만·확인 필요·칭찬으로 나누고, 답하지 않은 질문부터 보여 줍니다."
        />

        <main className="content eng-page">
          <section className="eng-input-card">
            <label htmlFor="inbox-url">내 영상 URL</label>
            <div className="eng-input-row">
              <input
                id="inbox-url"
                type="url"
                value={url}
                placeholder="https://www.youtube.com/watch?v=..."
                onChange={(event) => {
                  setUrl(event.target.value);
                  setError(null);
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void load();
                }}
              />
              <select value={order} onChange={(event) => setOrder(event.target.value as 'relevance' | 'time')} aria-label="댓글 정렬 기준">
                <option value="relevance">인기순으로 불러오기</option>
                <option value="time">최신순으로 불러오기</option>
              </select>
              <button type="button" className="btn primary" onClick={() => void load()} disabled={!urlValid || loading}>
                {loading ? <LoaderCircle size={15} className="spin" /> : <Inbox size={15} />}
                {loading ? '불러오는 중...' : '댓글 불러오기'}
              </button>
            </div>
            {url.trim() && !urlValid && <div className="inline-status error">올바른 YouTube 영상 URL을 입력해주세요.</div>}
            {postBlockedReason && (
              <div className="eng-readiness">
                <AlertCircle size={15} />
                <span>{postBlockedReason}</span>
                {accountMode === 'personal' ? (
                  <button type="button" onClick={() => navigate('/account/connect')}><Settings size={13} /> 연결 설정</button>
                ) : (
                  <button type="button" onClick={() => navigate('/account')}><Settings size={13} /> 계정 모드</button>
                )}
              </div>
            )}
            {error && <div className="inline-status error">{error}</div>}
          </section>

          {inbox && (
            <>
              <section className="eng-video">
                {inbox.video.thumbnail_url && <img src={inbox.video.thumbnail_url} alt="" />}
                <div>
                  <span>{inbox.video.channel}</span>
                  <strong>{inbox.video.title}</strong>
                  <small>
                    {order === 'time' ? '최신' : '인기'}순 최상위 댓글 {inbox.summary.total + inbox.summary.own_comments}개를 불러왔습니다(답글 포함 전체 댓글 {inbox.video.comment_count?.toLocaleString() ?? '—'}개).
                    {inbox.summary.own_comments > 0 && ` 내가 단 댓글 ${inbox.summary.own_comments}개는 제외했습니다.`}
                  </small>
                </div>
              </section>

              <div className="kpi-strip">
                <Kpi label="답이 필요한 댓글" value={String(inbox.summary.needs_reply)} sub="아직 답하지 않은 질문·불만" />
                <Kpi label="질문" value={String(inbox.summary.by_category.question)} sub="물음표·질문 표현 기준" />
                <Kpi label="확인 필요" value={String(inbox.summary.by_category.risk)} sub="욕설·스팸·분쟁 소지" />
                <Kpi label="이미 답한 댓글" value={String(inbox.summary.creator_replied)} sub="스레드에 내 답글이 있음" />
              </div>

              <div className="chip-row" role="tablist" aria-label="댓글 분류">
                {FILTERS.map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    role="tab"
                    aria-selected={filter === item.key}
                    className={`chip${filter === item.key ? ' active' : ''}`}
                    onClick={() => setFilter(item.key)}
                  >
                    {item.label} <span className="chip-k">{filterCount(item.key)}</span>
                  </button>
                ))}
              </div>

              {visible.length === 0 && (
                <section className="eng-empty">
                  <Check size={20} />
                  <div><strong>이 분류에 해당하는 댓글이 없습니다</strong><span>다른 분류를 선택해 보세요.</span></div>
                </section>
              )}

              <section className="inbox-list">
                {visible.map((item) => {
                  const reply = replies[item.id];
                  const open = openId === item.id;
                  return (
                    <article key={item.id} className={`inbox-item inbox-${item.category}${item.needs_reply ? ' needs' : ''}`}>
                      <div className="inbox-top">
                        <span className={`inbox-tag inbox-tag-${item.category}`}>{item.category_label}</span>
                        {item.risk_reason && <span className="eng-flag">{RISK_REASON_LABEL[item.risk_reason] ?? item.risk_reason}</span>}
                        {item.needs_reply && <span className="inbox-needs">답 필요</span>}
                        {item.creator_replied && <span className="inbox-done"><Check size={12} /> 답변함</span>}
                        <span className="inbox-author">{item.author}</span>
                        <span className="inbox-stats">
                          <ThumbsUp size={12} /> {item.like_count.toLocaleString()}
                          <MessageSquareReply size={12} /> {item.reply_count.toLocaleString()}
                        </span>
                      </div>
                      <p className="inbox-text">{item.text}</p>

                      {!open && item.can_reply && (
                        <button type="button" className="btn sm secondary" onClick={() => void openDrafts(item)}>
                          <Wand2 size={13} /> 답글 초안 보기
                        </button>
                      )}

                      {open && (
                        <div className="inbox-reply">
                          {reply?.loading && <div className="eng-muted"><LoaderCircle size={14} className="spin" /> 초안을 만드는 중...</div>}
                          {reply && !reply.loading && reply.drafts.length > 0 && !reply.posted && (
                            <>
                              <div className="inbox-drafts">
                                <span className="eng-muted">
                                  {reply.source === 'llm' ? 'AI 초안' : '기본 문구 초안'} · 고른 뒤 직접 고쳐서 쓰세요
                                </span>
                                {reply.drafts.map((draft) => (
                                  <button
                                    key={draft}
                                    type="button"
                                    className={`inbox-draft${reply.text === draft ? ' active' : ''}`}
                                    onClick={() => patchReply(item.id, { text: draft })}
                                  >
                                    {draft}
                                  </button>
                                ))}
                              </div>
                              <textarea
                                value={reply.text}
                                maxLength={2000}
                                rows={3}
                                aria-label="게시할 답글"
                                onChange={(event) => patchReply(item.id, { text: event.target.value })}
                              />
                              <div className="inbox-actions">
                                <button type="button" className="btn sm ghost" onClick={() => setOpenId(null)}>닫기</button>
                                <button type="button" className="btn sm secondary" onClick={() => void copyText(item.id, reply.text)} disabled={!reply.text.trim()}>
                                  {copiedId === item.id ? <Check size={13} /> : <Copy size={13} />}
                                  {copiedId === item.id ? '복사됨' : '복사'}
                                </button>
                                <button
                                  type="button"
                                  className="btn sm primary"
                                  onClick={() => void postReply(item)}
                                  disabled={!canPost || !reply.text.trim() || reply.posting}
                                  title={postBlockedReason ?? undefined}
                                >
                                  {reply.posting ? <LoaderCircle size={13} className="spin" /> : <Send size={13} />}
                                  {reply.posting ? '게시 중...' : '이 답글 게시'}
                                </button>
                              </div>
                            </>
                          )}
                          {reply?.posted && (
                            <div className="inline-status">
                              <Check size={14} /> 답글을 게시했습니다.
                              {reply.postedUrl && (
                                <a href={reply.postedUrl} target="_blank" rel="noopener noreferrer">
                                  YouTube에서 보기 <ArrowUpRight size={12} />
                                </a>
                              )}
                            </div>
                          )}
                          {reply?.error && <div className="inline-status error">{reply.error}</div>}
                        </div>
                      )}
                    </article>
                  );
                })}
              </section>

              <p className="eng-note">
                분류는 규칙 기반이라 틀릴 수 있습니다. 답글은 스레드당 최근 5개까지만 확인하므로, 답글이 많은 댓글은 이미 답했어도 '답 필요'로 보일 수 있습니다.
              </p>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
