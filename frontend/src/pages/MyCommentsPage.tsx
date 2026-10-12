import { ArrowUpRight, LoaderCircle, MessageSquareReply, RefreshCw, ThumbsUp, TrendingUp } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAccountMode, listMyComments, refreshMyComments } from '../api/client';
import { TypeTag } from '../components/TypeTag';
import { Kpi } from '../components/dashboard/KpiStrip';
import { Header } from '../components/layout/Header';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import { COMMENT_TYPE_LABEL, type CommentType, type PublishedComment, type PublishedCommentsResponse } from '../types/comment';

function formatAge(hours: number): string {
  if (hours < 1) return '방금 전';
  if (hours < 24) return `${Math.floor(hours)}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

function correlationLabel(value: number | null, pairs: number): { value: string; sub: string } {
  if (value == null) {
    return { value: '—', sub: pairs < 3 ? `반응을 확인한 추천 댓글 ${pairs}/3개` : '반응 차이가 아직 없음' };
  }
  const strength = Math.abs(value) >= 0.5 ? '강한' : Math.abs(value) >= 0.3 ? '보통' : '약한';
  const direction = value >= 0 ? '같은 방향' : '반대 방향';
  return { value: value.toFixed(2), sub: `${strength} ${direction} · ${pairs}개 기준` };
}

function metric(value: number | null, waiting: string) {
  return value == null ? <span className="eng-muted">{waiting}</span> : value.toLocaleString();
}

function MilestoneCell({ item, label }: { item: PublishedComment; label: '24h' | '7d' }) {
  const likes = label === '24h' ? item.likes_24h : item.likes_7d;
  const threshold = label === '24h' ? 24 : 24 * 7;
  if (likes != null) return <>{likes.toLocaleString()}</>;
  return <span className="eng-muted">{item.hours_since_publish < threshold ? '대기' : '다음 확인 때'}</span>;
}

export function MyCommentsPage() {
  const navigate = useNavigate();
  const accountMode = getAccountMode();
  const [data, setData] = useState<PublishedCommentsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await listMyComments());
    } catch (err) {
      setError(err instanceof Error ? err.message : '내가 단 댓글을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    setError(null);
    setNotice(null);
    try {
      const next = await refreshMyComments();
      setData(next);
      setNotice(
        next.checked_count
          ? `댓글 ${next.checked_count}개의 실제 반응을 확인했습니다.`
          : '최근 10분 안에 모두 확인한 댓글이라 새로 조회하지 않았습니다.',
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : '실제 반응을 확인하지 못했습니다.');
    } finally {
      setRefreshing(false);
    }
  };

  const handleNav = (key: SidebarKey) => {
    if (key === 'comments') navigate('/');
    if (key === 'dashboard') navigate('/dashboard');
    if (key === 'persona') navigate('/persona');
    if (key === 'account') navigate('/account');
  };

  const summary = data?.summary;
  const items = data?.items ?? [];
  const correlation = correlationLabel(summary?.prediction_spearman ?? null, summary?.prediction_pair_count ?? 0);
  const maxTypeLikes = Math.max(1, ...(summary?.by_type ?? []).map((row) => row.average_likes ?? 0));

  return (
    <div className="app">
      <Sidebar current="mycomments" onNav={handleNav} />
      <div className="main">
        <Header
          title="내 댓글 성과"
          subtitle="앱에서 YouTube에 게시한 댓글의 실제 좋아요·답글을 확인하고, 추천 단계의 예상 점수와 비교합니다."
        />

        <main className="content eng-page">
          <section className="eng-toolbar">
            <div>
              <span className="eng-kicker"><TrendingUp size={14} /> PREDICTED VS ACTUAL</span>
              <p>
                {accountMode === 'personal' ? '개인 계정' : '데모 계정'}으로 게시한 댓글만 보여 줍니다.
                24시간·7일 값은 그 시점이 지난 뒤 처음 확인한 반응으로 고정합니다.
              </p>
            </div>
            <button type="button" className="btn primary" onClick={() => void refresh()} disabled={refreshing || loading || !items.length}>
              {refreshing ? <LoaderCircle size={15} className="spin" /> : <RefreshCw size={15} />}
              {refreshing ? '확인 중...' : '실제 반응 새로 확인'}
            </button>
          </section>

          {error && <div className="inline-status error">{error}</div>}
          {notice && <div className="inline-status">{notice}</div>}

          <div className="kpi-strip">
            <Kpi
              label="추적 중인 댓글"
              value={loading ? '…' : String(summary?.tracked_count ?? 0)}
              sub={summary?.missing_count ? `삭제·검토 대기 ${summary.missing_count}개` : '앱에서 게시한 댓글'}
            />
            <Kpi
              label="평균 좋아요"
              value={loading ? '…' : summary?.average_likes == null ? '—' : summary.average_likes.toFixed(1)}
              sub={summary?.measured_count ? `반응 확인 ${summary.measured_count}개 기준` : '아직 확인 전'}
            />
            <Kpi
              label="답글 받은 비율"
              value={loading ? '…' : summary?.replied_rate == null ? '—' : `${summary.replied_rate.toFixed(0)}%`}
              sub="답글이 1개 이상 달린 댓글"
            />
            <Kpi label="예측-실제 순위 상관" value={loading ? '…' : correlation.value} sub={correlation.sub} />
          </div>

          {!loading && !items.length && !error && (
            <section className="eng-empty">
              <MessageSquareReply size={22} />
              <div>
                <strong>아직 추적 중인 댓글이 없습니다</strong>
                <span>댓글 추천 결과에서 "YouTube에 게시"를 누르면 이곳에서 실제 반응을 확인할 수 있습니다.</span>
              </div>
              <button type="button" className="btn secondary" onClick={() => navigate('/')}>댓글 추천으로 이동</button>
            </section>
          )}

          {items.length > 0 && (
            <div className="eng-grid">
              <section className="eng-panel">
                <div className="eng-panel-head">
                  <h3>게시한 댓글</h3>
                  <small>예상 점수는 추천 당시 랭커 점수입니다. 직접 쓴 댓글은 비어 있습니다.</small>
                </div>
                <div className="eng-table-wrap">
                  <table className="eng-table">
                    <thead>
                      <tr>
                        <th>댓글</th>
                        <th className="num">예상 점수</th>
                        <th className="num"><ThumbsUp size={12} /> 현재</th>
                        <th className="num">24시간</th>
                        <th className="num">7일</th>
                        <th className="num">답글</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) => (
                        <tr key={item.id} className={item.status === 'missing' ? 'is-missing' : undefined}>
                          <td className="eng-comment-cell">
                            <div className="eng-comment-top">
                              {item.comment_type && <TypeTag type={item.comment_type} />}
                              <span className="eng-muted">{formatAge(item.hours_since_publish)}</span>
                              {item.status === 'missing' && <span className="eng-flag">삭제·검토 대기</span>}
                            </div>
                            <p>{item.comment}</p>
                            <div className="eng-comment-meta">
                              <span>{item.video_title || item.video_id}</span>
                              {item.comment_url && (
                                <a href={item.comment_url} target="_blank" rel="noopener noreferrer">
                                  YouTube에서 보기 <ArrowUpRight size={12} />
                                </a>
                              )}
                            </div>
                          </td>
                          <td className="num">{item.predicted_score == null ? <span className="eng-muted">—</span> : item.predicted_score.toFixed(1)}</td>
                          <td className="num strong">{metric(item.like_count, '확인 전')}</td>
                          <td className="num"><MilestoneCell item={item} label="24h" /></td>
                          <td className="num"><MilestoneCell item={item} label="7d" /></td>
                          <td className="num">{metric(item.reply_count, '—')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <aside className="eng-panel eng-side">
                <div className="eng-panel-head">
                  <h3>유형별 평균 좋아요</h3>
                  <small>반응을 확인한 댓글 기준</small>
                </div>
                {(summary?.by_type ?? []).length === 0 && <p className="eng-muted">새로 확인을 누르면 집계됩니다.</p>}
                {(summary?.by_type ?? []).map((row) => (
                  <div className="eng-bar" key={row.type}>
                    <div className="eng-bar-label">
                      <span>{row.type in COMMENT_TYPE_LABEL ? COMMENT_TYPE_LABEL[row.type as CommentType] : '직접 작성'}</span>
                      <b>{row.average_likes == null ? '—' : row.average_likes.toFixed(1)}</b>
                    </div>
                    <div className="eng-bar-track">
                      <span style={{ width: `${((row.average_likes ?? 0) / maxTypeLikes) * 100}%` }} />
                    </div>
                    <small>{row.count}개</small>
                  </div>
                ))}
                <p className="eng-note">
                  예측-실제 상관은 예상 점수 순위와 실제 좋아요 순위가 얼마나 같은 방향인지 보여 줍니다(스피어만, -1~1).
                  표본이 적을 때는 참고용으로만 보세요.
                </p>
              </aside>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
