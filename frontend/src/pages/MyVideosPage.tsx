import { ArrowUpRight, BarChart3, Film, LoaderCircle, Plus, RefreshCw, TrendingUp } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAccountMode, getMyVideos, refreshMyVideos, trackMyVideo } from '../api/client';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import { Header } from '../components/layout/Header';
import { Kpi } from '../components/dashboard/KpiStrip';
import { VideoReactionComparison } from '../components/dashboard/VideoReactionComparison';
import { exportVideoBackup, mergeVideoBackup, saveVideoBackup } from '../utils/videoBackup';
import { extractYouTubeVideoId } from '../utils/youtube';
import type { OwnedVideoMetric, OwnedVideoPerformanceResponse } from '../types/comment';

const format = (n: number | null | undefined) => n == null ? '—' : n.toLocaleString('ko-KR');
const observed = (n: number | null) => n == null ? '미측정' : (n > 0 ? '+' : '') + format(n);
const date = (s: string | null) => s ? new Date(s).toLocaleString('ko-KR') : '확인 전';

export function MyVideosPage() {
  const navigate = useNavigate();
  const mode = getAccountMode();
  const [data, setData] = useState<OwnedVideoPerformanceResponse | null>(null);
  const [loading, setLoading] = useState(mode === 'personal');
  const [syncing, setSyncing] = useState(false);
  const [adding, setAdding] = useState(false);
  const [input, setInput] = useState('');
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const display = (response: OwnedVideoPerformanceResponse) => {
    saveVideoBackup(response);
    setData(mergeVideoBackup(response));
  };

  const sync = useCallback(async () => {
    setSyncing(true);
    setError(null);
    setNotice(null);
    try {
      const response = await refreshMyVideos();
      display(response);
      setNotice(response.cached
        ? '최근 5분 안에 확인한 데이터입니다. 잠시 후 다시 조회할 수 있습니다.'
        : `내 업로드 영상 ${response.checked_count ?? 0}개의 최신 누적 지표를 확인했습니다.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : '영상 성과를 조회하지 못했습니다.');
    } finally {
      setSyncing(false);
    }
  }, []);

  useEffect(() => {
    if (mode !== 'personal') return;
    let cancelled = false;
    getMyVideos()
      .then(async (response) => {
        if (cancelled) return;
        display(response);
        setLoading(false);
        if (!response.last_sync_at) await sync();
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : '영상 성과를 불러오지 못했습니다.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [mode, sync]);

  const addVideo = async () => {
    const id = /^[A-Za-z0-9_-]{11}$/.test(input.trim())
      ? input.trim() : extractYouTubeVideoId(input.trim());
    if (!id) {
      setError('유효한 YouTube 영상 주소 또는 11자리 영상 ID를 입력해주세요.');
      return;
    }
    setAdding(true);
    setError(null);
    setNotice(null);
    try {
      const response = await trackMyVideo(id);
      display(response);
      setInput('');
      setNotice('현재 연결된 채널의 영상이 추적 목록에 추가되었습니다.');
    } catch (e) {
      setError(e instanceof Error ? e.message : '영상을 추가하지 못했습니다.');
    } finally {
      setAdding(false);
    }
  };

  const handleNav = (key: SidebarKey) => {
    if (key === 'comments') navigate('/');
    else if (key === 'dashboard') navigate('/dashboard');
    else if (key === 'persona') navigate('/persona');
    else if (key === 'account') navigate('/account');
  };
  const matches = (data?.items ?? []).filter((item) =>
    !query.trim() || (item.title + item.video_id).toLowerCase().includes(query.trim().toLowerCase()));
  const summary = data?.summary;

  return (
    <div className="app">
      <Sidebar current="myvideos" onNav={handleNav} />
      <div className="main">
        <Header title="내 영상 성과"
          subtitle="내 YouTube 채널에 실제 게시한 영상의 누적 조회수·좋아요·댓글 수를 기록하고 비교합니다." />
        <main className="content eng-page">
          <section className="eng-toolbar">
            <div>
              <span className="eng-kicker"><TrendingUp size={14} /> YOUR VIDEO PERFORMANCE</span>
              <p>조회수·좋아요·댓글 수는 YouTube Data API의 실제 누적 수치입니다. 24시간·7일 변화는 저장된 측정값이 있을 때만 표시합니다.</p>
            </div>
            <button className="btn primary" type="button"
              disabled={mode !== 'personal' || syncing || loading || adding}
              onClick={() => void sync()}>
              {syncing ? <LoaderCircle size={15} className="spin" /> : <RefreshCw size={15} />}
              {syncing ? '확인 중...' : '실제 반응 새로 확인'}
            </button>
          </section>

          {mode !== 'personal' && (
            <section className="eng-empty">
              <Film size={22} />
              <div><strong>내 YouTube 계정을 연결해주세요.</strong>
                <span>개인 YouTube 채널의 영상만 조회할 수 있습니다. 데모 계정에는 실제 영상이 없습니다.</span></div>
              <button type="button" className="btn primary" onClick={() => navigate('/account/connect')}>연결 설정</button>
            </section>
          )}

          {mode === 'personal' && (
            <>
              <section className="eng-panel" style={{ display: 'grid', gap: 10 }}>
                <div className="eng-panel-head">
                  <h3>{data?.channel_title || '내 YouTube 채널'} · 영상 추적</h3>
                  <small>연결된 채널의 전체 업로드 영상 목록을 가져옵니다. 영상이 많을 경우 동기화에 시간이 걸릴 수 있습니다.</small>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                  <input className="account-text-input" value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && !adding) void addVideo(); }}
                    placeholder="오래된 내 영상 URL 또는 영상 ID"
                    aria-label="추적할 내 영상 URL"
                    style={{ flex: '1 1 320px', minWidth: 0 }} />
                  <button type="button" className="btn secondary" onClick={() => void addVideo()}
                    disabled={adding || syncing || !input.trim()}>
                    {adding ? <LoaderCircle size={15} className="spin" /> : <Plus size={15} />}
                    영상 추가
                  </button>
                  <button type="button" className="btn secondary"
                    disabled={!data?.channel_id || !data.items.length}
                    onClick={() => data && exportVideoBackup(data.channel_id)}>
                    JSON 백업
                  </button>
                </div>
                <p className="eng-note">마지막 확인: {date(data?.last_sync_at ?? null)} · 서버 동기화는 최소 5분 간격입니다.
                  개인 채널의 영상만 가져오며 다른 채널의 영상은 등록할 수 없습니다.</p>
                {data?.storage_warning && <div className="inline-status error" role="status">{data.storage_warning}</div>}
                {data?.items.some((x) => x.local_only) && (
                  <div className="inline-status" role="status">이 브라우저에만 남은 영상 성과가 있습니다. 이 수치는 과거 측정값이며 실시간 정보가 아닙니다.</div>
                )}
              </section>

              {error && (
                <div className="inline-status error" role="alert">
                  {error}
                  <button type="button" className="btn secondary sm" onClick={() => void sync()} disabled={syncing}>다시 시도</button>
                  <button type="button" className="btn secondary sm" onClick={() => navigate('/account/connect')}>연결 설정</button>
                </div>
              )}
              {notice && <div className="inline-status" role="status">{notice}</div>}

              <div className="kpi-strip">
                <Kpi label="추적 중인 영상" value={loading ? '…' : format(summary?.tracked_count)}
                  sub="최근 업로드 및 개별 추가" />
                <Kpi label="누적 조회수" value={loading ? '…' : format(summary?.total_views)}
                  sub="추적 중인 영상 합산" />
                <Kpi label="누적 좋아요" value={loading ? '…' : format(summary?.total_likes)}
                  sub="공개된 좋아요 합계" />
                <Kpi label="누적 댓글" value={loading ? '…' : format(summary?.total_comments)}
                  sub="공개된 댓글 수 합계" />
              </div>

              {!!data?.items.length && <VideoReactionComparison videos={data.items} />}

              {!loading && data && data.items.length === 0 && (
                <section className="eng-empty">
                  <Film size={22} />
                  <div><strong>아직 가져온 영상이 없습니다</strong>
                    <span>내 계정으로 YouTube에 업로드한 영상이 있다면 ‘실제 반응 새로 확인’을 눌러주세요.</span></div>
                  <button type="button" className="btn primary" onClick={() => void sync()} disabled={syncing}>영상 불러오기</button>
                </section>
              )}

              {!!data?.items.length && (
                <section className="eng-panel">
                  <div className="eng-panel-head">
                    <h3>내 영상별 성과</h3>
                    <small>변화 수치는 스냅샷 차이이며 YouTube Studio의 일별 분석과는 다를 수 있습니다. 누락된 수치는 ‘—’로 표시합니다.</small>
                  </div>
                  <input className="account-text-input" type="search" value={query}
                    onChange={(e) => setQuery(e.target.value)} placeholder="영상 제목 검색"
                    aria-label="영상 제목 검색" style={{ width: '100%', marginBottom: 12 }} />
                  <div className="eng-table-wrap">
                    <table className="eng-table">
                      <thead><tr>
                        <th>영상</th>
                        <th className="num">조회수</th>
                        <th className="num">최근 측정 간</th>
                        <th className="num">24시간 변화</th>
                        <th className="num">7일 변화</th>
                        <th className="num">좋아요</th>
                        <th className="num">댓글</th>
                      </tr></thead>
                      <tbody>
                        {matches.map((item: OwnedVideoMetric) => (
                          <tr key={item.video_id}>
                            <td className="eng-comment-cell">
                              <div className="video-performance-item">
                                {item.thumbnail_url && <img src={item.thumbnail_url} alt="" loading="lazy" className="video-performance-thumb" />}
                                <div>
                                  <div className="eng-comment-top">
                                    <span className="eng-muted">{item.privacy_status === 'public' ? '공개' : item.privacy_status === 'private' ? '비공개' : item.privacy_status === 'unlisted' ? '일부 공개' : '상태 미확인'}</span>
                                    {item.local_only && <span className="eng-flag">브라우저 백업</span>}
                                  </div>
                                  <strong className="video-performance-title">{item.title}</strong>
                                  <div className="eng-comment-meta">
                                    <span>{date(item.published_at)}</span>
                                    <a href={`https://www.youtube.com/watch?v=${item.video_id}`} target="_blank" rel="noopener noreferrer">
                                      YouTube에서 보기 <ArrowUpRight size={12} />
                                    </a>
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td className="num strong">{format(item.views)}</td>
                            <td className="num">{observed(item.views_since_previous)}</td>
                            <td className="num">{observed(item.views_24h)}</td>
                            <td className="num">{observed(item.views_7d)}</td>
                            <td className="num">{format(item.likes)}</td>
                            <td className="num">{format(item.comments)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {!matches.length && <p className="eng-muted">검색 결과가 없습니다.</p>}
                </section>
              )}
              <p className="eng-note"><BarChart3 size={14} /> 정확한 일별 시청 시간·시청 지속률은 YouTube Analytics의 별도 권한이 필요하며,
                이 화면은 누적 지표의 측정 시점별 변화만 제공합니다.</p>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
