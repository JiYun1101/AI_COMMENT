import { ArrowUpRight, LoaderCircle, MessageSquareReply, Pencil, RefreshCw, ThumbsUp, Trash2, TrendingUp } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { claimLegacyPublishedHistory, getAccountMode, getAuthenticatedYouTubeIdentity, listMyComments, recoverPublishedBatch, recoverPublishedComment, refreshMyComments, lookupPublicCommentMetrics, editPublishedYouTubeComment, deletePublishedYouTubeComment, type AuthenticatedYouTubeIdentity } from '../api/client';
import { parseTakeoutCommentsCsv } from '../utils/takeoutComments';
import { exportPostedBackup, importPostedBackup, updatePostedBackupText, removePostedBackupComment } from '../utils/publishedLedger';
import { applySavedPublicMetrics, storePublicMetricResponse } from '../utils/publicMetricsBackup';
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
  if (item.local_only && item.hours_since_publish >= threshold) {
    return <span className="eng-muted">기준 기록 없음</span>;
  }
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
  const [recoveryUrl, setRecoveryUrl] = useState('');
  const [recoveryBusy, setRecoveryBusy] = useState(false);
  const [identity, setIdentity] = useState<AuthenticatedYouTubeIdentity | null>(null);
  const [takeoutProgress, setTakeoutProgress] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [mutatingId, setMutatingId] = useState<string | null>(null);

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
    if (accountMode === 'personal') {
      void getAuthenticatedYouTubeIdentity().then(setIdentity).catch(() => setIdentity(null));
    }
  }, [load, accountMode]);

  const refresh = async () => {
    if (refreshing || loading) return;
    setRefreshing(true);
    setError(null);
    setNotice(null);
    let next = data;
    let serverError: string | null = null;
    let savedCount = 0;
    let publicCount = 0;
    let unavailableCount = 0;
    let publicError: string | null = null;
    try {
      // Local-only receipts cannot be refreshed via the OAuth-only server DB.
      const onlyBrowserReceipts = Boolean(next?.items.length)
        && next!.items.every((item) => item.local_only);
      if (!onlyBrowserReceipts) {
        try {
          next = await refreshMyComments();
          savedCount = next.checked_count ?? 0;
        } catch (err) {
          serverError = err instanceof Error ? err.message : '서버 기록을 확인하지 못했습니다.';
          next = await listMyComments();
        }
      }
      if (!next) next = await listMyComments();

      const targets = next.items.filter((item) => item.local_only || serverError);
      for (let i = 0; i < Math.min(targets.length, 150); i += 50) {
        const chunk = targets.slice(i, i + 50);
        try {
          const result = await lookupPublicCommentMetrics(
            chunk.map((item) => ({ video_id: item.video_id, comment_id: item.comment_id })),
          );
          if (!storePublicMetricResponse(result, accountMode)) {
            publicError = '브라우저가 결과를 보관하지 못했습니다. 저장 공간 또는 시크릿 모드를 확인해주세요.';
            break;
          }
          publicCount += result.observed_count;
          unavailableCount += result.checked_count - result.observed_count;
        } catch (err) {
          publicError = err instanceof Error ? err.message : '공개 댓글 반응 조회에 실패했습니다.';
          break;
        }
      }

      setData(applySavedPublicMetrics(next, accountMode));
      if (publicError) {
        setError(publicError + ' 연결 설정에서 YouTube Data API 키를 확인해주세요.');
      } else if (serverError && !publicCount) {
        setError(serverError + ' 서버의 OAuth 연결 상태를 확인해주세요.');
      }

      const messages = [];
      if (savedCount) messages.push(`서버 기록 ${savedCount}개 갱신`);
      if (publicCount) messages.push(`브라우저 백업 포함 공개 댓글 ${publicCount}개 반응 확인`);
      if (unavailableCount) messages.push(`공개 조회 불가 ${unavailableCount}개(삭제 여부는 확인 불가)`);
      if (serverError && publicCount) messages.push('서버 추적은 연결되지 않았지만 공개 지표는 확인했습니다');
      if (targets.length > 150) messages.push('최대 150개까지만 조회했습니다');
      if (!messages.length && !publicError && !serverError) {
        messages.push('최근 10분 이내에 서버 지표를 조회했거나 새로 확인할 공개 댓글이 없습니다.');
      }
      if (messages.length) setNotice(messages.join(' · '));
    } catch (err) {
      setError(err instanceof Error ? err.message : '실제 반응을 확인하지 못했습니다.');
    } finally {
      setRefreshing(false);
    }
  };

  const saveEditedComment = async (item: PublishedComment) => {
    const updated = editingText.trim();
    if (!updated || updated === item.comment || updated.length > 10000 || mutatingId) return;
    setMutatingId(item.comment_id);
    setError(null);
    try {
      const result = await editPublishedYouTubeComment(item.comment_id, updated);
      updatePostedBackupText(item.comment_id, result.comment);
      setEditingId(null);
      await load();
      setNotice(result.tracking_saved
        ? 'YouTube 댓글과 서버 추적 기록을 수정했습니다.'
        : 'YouTube 댓글을 수정했습니다. 브라우저 백업은 변경했지만 서버 기록은 별도로 확인해야 합니다.');
    } catch (err) {
      setError(err instanceof Error ? err.message : '댓글 수정에 실패했습니다.');
    } finally {
      setMutatingId(null);
    }
  };

  const deleteComment = async (item: PublishedComment) => {
    if (mutatingId) return;
    setMutatingId(item.comment_id);
    setError(null);
    try {
      const result = await deletePublishedYouTubeComment(item.comment_id);
      if (!result.deleted) throw new Error('YouTube에서 댓글 삭제를 확인하지 못했습니다.');
      removePostedBackupComment(item.comment_id);
      setDeletingId(null);
      setEditingId(null);
      await load();
      setNotice(result.tracking_removed
        ? 'YouTube 댓글을 삭제하고 서버·브라우저 기록에서도 제거했습니다.'
        : 'YouTube 댓글을 삭제하고 브라우저 기록에서 제거했습니다.');
    } catch (err) {
      setError(err instanceof Error ? err.message : '댓글 삭제에 실패했습니다.');
    } finally {
      setMutatingId(null);
    }
  };

  const restoreFromYouTube = async () => {
    setRecoveryBusy(true);
    setError(null);
    setNotice(null);
    try {
      const link = new URL(recoveryUrl);
      if (!['www.youtube.com', 'youtube.com', 'm.youtube.com'].includes(link.hostname) ||
          link.protocol !== 'https:') throw new Error('YouTube 댓글 주소를 붙여넣어 주세요.');
      const video = link.searchParams.get('v') || '';
      const comment = link.searchParams.get('lc') || '';
      if (!/^[\w-]{11}$/.test(video) || !comment) throw new Error('주소에 영상 ID와 댓글 ID(lc)가 필요합니다.');
      await recoverPublishedComment(video, comment);
      setRecoveryUrl('');
      await load();
      setNotice('YouTube 작성자 인증을 확인하고 댓글 추적을 다시 등록했습니다.');
    } catch (e) {
      setError(e instanceof Error ? e.message : '댓글 복구에 실패했습니다.');
    } finally {
      setRecoveryBusy(false);
    }
  };

  const importBackupFile = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    try {
      if (file.size > 2 * 1024 * 1024) throw new Error('2MB 이하의 백업 파일만 지원합니다.');
      const count = importPostedBackup(JSON.parse(await file.text()));
      await load();
      setNotice('이 브라우저에 댓글 영수증 ' + count + '개를 불러왔습니다. 실측 추적에는 YouTube 재인증과 영구 DB가 필요합니다.');
    } catch (e) {
      setError(e instanceof Error ? e.message : '백업 파일을 확인할 수 없습니다.');
    }
  };

  const restoreLocalComments = async () => {
    const pending = (data?.items || []).filter((item) => item.local_only && item.account_mode === 'personal');
    if (!pending.length) return;
    setRecoveryBusy(true);
    setError(null);
    let restored = 0;
    try {
      for (const item of pending.slice(0, 50)) {
        try {
          await recoverPublishedComment(item.video_id, item.comment_id);
          restored++;
        } catch (e) {
          setError(e instanceof Error ? e.message : '일부 댓글을 복구하지 못했습니다.');
        }
      }
      await load();
      setNotice('본인 확인된 댓글 ' + restored + '개를 서버 추적 목록에 복구했습니다.');
    } finally {
      setRecoveryBusy(false);
    }
  };


  const recoverFromTakeout = async (file: File | undefined) => {
    if (!file) return;
    setRecoveryBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (accountMode !== 'personal') throw new Error('내 YouTube 계정을 연결해야 복구할 수 있습니다.');
      const verified = await getAuthenticatedYouTubeIdentity();
      setIdentity(verified);
      if (file.size > 8 * 1024 * 1024) throw new Error('CSV 파일은 8MB 이하만 지원합니다.');
      const records = parseTakeoutCommentsCsv(await file.text());
      if (!records.length) throw new Error('복구 가능한 YouTube 댓글 ID를 찾지 못했습니다.');
      let recovered = 0;
      let failed = 0;
      const bounded = records.slice(0, 150);
      // Batch calls avoid one YouTube API round-trip for each historical comment.
      for (let i = 0; i < bounded.length; i += 30) {
        const subset = bounded.slice(i, i + 30);
        const result = await recoverPublishedBatch(
          subset.map((item) => ({ video_id: item.videoId, comment_id: item.commentId })),
        );
        recovered += result.registered_count;
        failed += result.failed_count;
        setTakeoutProgress('댓글 본인 확인 ' + Math.min(i + 30, bounded.length) + '/' + bounded.length);
      }
      await load();
      setNotice('같은 YouTube 채널로 확인된 과거 댓글 ' + recovered + '개 등록, 실패 ' + failed + '개.' +
        (records.length > bounded.length ? ' 150개를 초과한 나머지는 파일을 나누어 등록해주세요.' : '') +
        ' 영구 DB 미연결 시 서버 재시작으로 다시 사라질 수 있습니다.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Takeout 기록 복구에 실패했습니다.');
    } finally {
      setTakeoutProgress(null);
      setRecoveryBusy(false);
    }
  };


  const reconnectExistingRecords = async () => {
    setRecoveryBusy(true);
    setError(null);
    try {
      const result = await claimLegacyPublishedHistory();
      await load();
      setNotice('기존 서버 기록 중 본인 소유 댓글 ' + result.restored +
        '개를 다시 연결했습니다. 확인한 댓글 ' + result.checked + '개.');
    } catch (error) {
      setError(error instanceof Error ? error.message : '이전 기록 연결에 실패했습니다.');
    } finally {
      setRecoveryBusy(false);
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


          <section className="eng-panel" style={{ padding: '18px 22px', display: 'grid', gap: 12 }}>
            <div className="eng-panel-head">
              <h3>같은 계정의 이전 댓글 복구 및 백업</h3>
              <small>현재 무료 서버의 DB는 영구 저장되지 않습니다. 서버 기록과 브라우저 보조 백업을 구분해 표시합니다.</small>
            </div>
            {accountMode === 'personal' && (
              <p className="eng-muted" style={{ fontSize: 13 }}>
                {identity ? '연결된 YouTube 채널: ' + (identity.channel_title || identity.channel_id)
                  : '연결 계정 확인이 필요합니다. 계정 설정에서 YouTube를 다시 연결해 주세요.'}
              </p>
            )}
            {takeoutProgress && <p role="status" className="eng-muted">{takeoutProgress}</p>}
            {data?.backend_unavailable && (
              <div role="alert" className="inline-status error">서버 추적 기록에 연결할 수 없어 브라우저 백업을 표시합니다. ‘실제 반응 새로 확인’으로 공개된 댓글의 좋아요·답글을 조회할 수 있습니다.</div>
            )}
            {items.some((item) => item.local_only) && (
              <div role="status" className="inline-status">
                서버에 없는 브라우저 백업 {items.filter((item) => item.local_only).length}개
                {accountMode === 'personal' && (
                  <button type="button" className="btn secondary" disabled={recoveryBusy}
                    onClick={() => void restoreLocalComments()}>YouTube 본인 확인 후 서버 기록 복구</button>
                )}
              </div>
            )}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
              {accountMode === 'personal' && (
                <button type="button" className="btn secondary" disabled={recoveryBusy}
                  onClick={() => void reconnectExistingRecords()}>
                  이전 서버 댓글 기록 다시 연결
                </button>
              )}
              <button type="button" className="btn secondary" onClick={exportPostedBackup}>게시 기록 JSON 백업</button>
              {accountMode === 'personal' && (
                <label className="btn secondary" style={{ cursor: recoveryBusy ? 'not-allowed' : 'pointer' }}>
                  Google Takeout 댓글 CSV 가져오기
                  <input type="file" accept=".csv,text/csv" disabled={recoveryBusy} style={{ display: 'none' }}
                    onChange={(event) => { void recoverFromTakeout(event.target.files?.[0]); event.target.value = ''; }} />
                </label>
              )}
              <label className="btn secondary" style={{ cursor: 'pointer' }}>
                백업 파일 가져오기
                <input type="file" accept="application/json,.json" style={{ display: 'none' }}
                  onChange={(event) => { void importBackupFile(event.target.files?.[0]); event.target.value = ''; }} />
              </label>
              <a href="https://www.youtube.com/feed/history/comment_history" target="_blank" rel="noreferrer">
                YouTube에서 내 댓글 기록 보기
              </a>
            </div>
            {accountMode === 'personal' && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                <input className="account-text-input" style={{ flex: '1 1 300px', minWidth: 0 }}
                  aria-label="복구할 YouTube 댓글 링크" placeholder="YouTube 댓글 주소 (v=영상ID&lc=댓글ID)"
                  value={recoveryUrl} onChange={(event) => setRecoveryUrl(event.target.value)} />
                <button type="button" className="btn primary" disabled={!recoveryUrl.trim() || recoveryBusy}
                  onClick={() => void restoreFromYouTube()}>
                  {recoveryBusy ? '복구 중...' : '기존 댓글 다시 추적'}
                </button>
              </div>
            )}
            <p className="eng-muted" style={{ fontSize: 12 }}>
              YouTube에 게시된 댓글은 다시 조회할 수 있어도 삭제된 AI 추천 점수나 분석 기록까지 자동 복구되지는 않습니다.
              기기 간 영구 보존은 별도의 영구 DB가 필요합니다.
            </p>
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
                              {item.local_only && (
                                <span className="eng-flag">
                                  {item.public_metric_status === 'active'
                                    ? '브라우저 백업 · 공개 반응 확인됨'
                                    : item.public_metric_status === 'unavailable'
                                      ? '브라우저 백업 · 현재 공개 조회 불가'
                                      : '브라우저 백업 · 공개 반응 조회 가능'}
                                </span>
                              )}
                            </div>

                            {editingId === item.comment_id ? (
                              <div className="eng-comment-editor">
                                <label htmlFor={`comment-edit-${item.id}`}>YouTube 댓글 수정</label>
                                <textarea
                                  id={`comment-edit-${item.id}`}
                                  value={editingText}
                                  onChange={(event) => setEditingText(event.target.value)}
                                  maxLength={10000}
                                  rows={3}
                                  disabled={mutatingId !== null}
                                />
                                <div className="eng-comment-controls">
                                  <span className="eng-muted">{editingText.length.toLocaleString()}/10,000자</span>
                                  <button type="button" className="btn primary"
                                    disabled={Boolean(mutatingId) || !editingText.trim() || editingText.trim() === item.comment}
                                    onClick={() => void saveEditedComment(item)}>
                                    {mutatingId === item.comment_id ? '저장 중...' : 'YouTube에 저장'}
                                  </button>
                                  <button type="button" className="btn secondary" disabled={Boolean(mutatingId)}
                                    onClick={() => setEditingId(null)}>취소</button>
                                </div>
                              </div>
                            ) : <p>{item.comment}</p>}
                            <div className="eng-comment-meta">
                              <span>{item.video_title || item.video_id}</span>
                              {item.last_checked_at && (
                                <span className="eng-muted">마지막 실제 확인 {new Date(item.last_checked_at).toLocaleString('ko-KR')}</span>
                              )}
                              {item.comment_url && (
                                <a href={item.comment_url} target="_blank" rel="noopener noreferrer">
                                  YouTube에서 보기 <ArrowUpRight size={12} />
                                </a>
                              )}
                            </div>
                            {accountMode === 'personal' && editingId !== item.comment_id && (
                              <div className="eng-comment-actions">
                                <button type="button" className="eng-comment-action"
                                  disabled={Boolean(mutatingId) || Boolean(deletingId)}
                                  aria-label="YouTube 댓글 수정"
                                  onClick={() => { setEditingId(item.comment_id); setEditingText(item.comment); setDeletingId(null); setError(null); }}>
                                  <Pencil size={13} /> 수정
                                </button>
                                <button type="button" className="eng-comment-action danger"
                                  disabled={Boolean(mutatingId) || Boolean(deletingId && deletingId !== item.comment_id)}
                                  aria-label="YouTube 댓글 삭제"
                                  onClick={() => { setDeletingId(item.comment_id); setEditingId(null); setError(null); }}>
                                  <Trash2 size={13} /> 삭제
                                </button>
                              </div>
                            )}
                            {deletingId === item.comment_id && (
                              <div className="eng-comment-delete-confirm" role="group" aria-label="댓글 삭제 확인">
                                <strong>YouTube에서 이 댓글을 영구 삭제할까요?</strong>
                                <span>삭제한 댓글은 되돌릴 수 없고, 앱의 추적 기록에서도 제거됩니다.</span>
                                <div className="eng-comment-controls">
                                  <button type="button" className="btn secondary" disabled={Boolean(mutatingId)}
                                    onClick={() => setDeletingId(null)}>취소</button>
                                  <button type="button" className="btn primary" disabled={Boolean(mutatingId)}
                                    onClick={() => void deleteComment(item)}>
                                    {mutatingId === item.comment_id ? '삭제 중...' : 'YouTube 댓글 영구 삭제'}
                                  </button>
                                </div>
                              </div>
                            )}
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
