import { Link } from 'react-router-dom';
import { Database, ExternalLink, LoaderCircle, RefreshCw, Upload } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  getAccountMode, getStoredApiAccessToken, getStoredYouTubeApiKey,
  listMyComments, lookupPublicCommentMetrics,
} from '../../api/client';
import { applySavedPublicMetrics, storePublicMetricResponse } from '../../utils/publicMetricsBackup';
import { listVerifiedTakeoutImports } from '../../utils/takeoutImportLedger';
import { buildCsvImportDashboard } from '../../utils/csvImportDashboard';
import type { PublishedCommentsResponse } from '../../types/comment';

const fmt = (n: number) => n.toLocaleString('ko-KR');

export function ImportedCsvCommentsPanel() {
  const [imports, setImports] = useState(() => listVerifiedTakeoutImports());
  const [published, setPublished] = useState<PublishedCommentsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const stats = useMemo(() => buildCsvImportDashboard(imports,published?.items || []),[imports,published]);

  const load = useCallback(async () => {
    const imported = listVerifiedTakeoutImports();
    setImports(imported);
    if (!imported.length || getAccountMode() !== 'personal') {
      setPublished(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      // Read-only. Browser-backed receipts are merged even if the free Render
      // instance lost its SQLite records.
      setPublished(await listMyComments());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '게시 댓글 상태를 조회하지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const refresh = async () => {
    if (refreshing || !imports.length) return;
    setRefreshing(true);
    setError(null);
    try {
      const baseline = published ?? await listMyComments();
      const latest = imports.slice(0,50);
      // Only explicit user request triggers YouTube Data API quota usage.
      const response = await lookupPublicCommentMetrics(
        latest.map(row=>({video_id:row.video_id,comment_id:row.comment_id})),
      );
      if (!storePublicMetricResponse(response,'personal')) {
        throw new Error('공개 반응 결과를 브라우저에 저장하지 못했습니다.');
      }
      setPublished(applySavedPublicMetrics(baseline,'personal'));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '댓글 공개 반응 확인에 실패했습니다.');
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <section className="model-panel imported-csv-panel" aria-label="기존 댓글 CSV 분석">
      <div className="model-panel-header">
        <div>
          <span className="model-eyebrow"><Database size={15} /> VERIFIED CSV · HISTORICAL COMMENTS</span>
          <h2>CSV로 가져온 기존 댓글</h2>
          <p>Google Takeout CSV를 불러온 뒤 연결된 YouTube 계정의 댓글로 <strong>검증된 항목만</strong> 반영합니다.
            기존 댓글은 AI 추천 생성 횟수나 학습 데이터 수에 합산하지 않습니다.</p>
        </div>
        <div className="imported-csv-actions">
          <Link to="/my-comments" className="btn secondary sm"><Upload size={14} /> 기존 댓글 CSV 가져오기</Link>
          <button type="button" className="btn secondary sm" disabled={loading} onClick={() => void load()}>
            {loading ? <LoaderCircle size={14} className="spin" /> : <RefreshCw size={14} />} 새로고침
          </button>
        </div>
      </div>
      <div className="model-metrics imported-csv-metrics">
        <div><span>CSV로 검증·가져온 댓글</span><strong>{fmt(stats.imported)}<small>건</small></strong><em>현재 브라우저·로그인 계정 범위 · 중복 제외</em></div>
        <div><span>실제 반응 측정 완료</span><strong>{fmt(stats.measured)}<small>건</small></strong><em>좋아요·답글 중 하나 이상 측정 가능</em></div>
        <div><span>실제 좋아요 합계</span><strong>{stats.measured ? fmt(stats.likes) : '—'}<small>{stats.measured ? '개' : ''}</small></strong><em>공개 수치를 확인한 댓글만 집계</em></div>
        <div><span>실제 답글 합계</span><strong>{stats.measured ? fmt(stats.replies) : '—'}<small>{stats.measured ? '개' : ''}</small></strong><em>공개 수치를 확인한 댓글만 집계</em></div>
      </div>
      {stats.imported > 0 && (
        <div className="imported-csv-summary">
          <span>반응 발생 <strong>{fmt(stats.reacted)}건</strong> / 측정 <strong>{fmt(stats.measured)}건</strong></span>
          <button className="btn secondary sm" type="button" disabled={refreshing || loading || !getStoredApiAccessToken() || !getStoredYouTubeApiKey() || getAccountMode() !== 'personal'}
            onClick={() => void refresh()}>
            {refreshing ? <LoaderCircle size={14} className="spin" /> : <RefreshCw size={14} />}
            {refreshing ? '반응 확인 중…' : '최근 50건 실제 반응 확인'}
          </button>
        </div>
      )}
      {error && <p className="inline-status error" role="alert">{error}</p>}
      {stats.imported ? (
        <>
          <div className="imported-csv-list">
            <div className="model-subhead"><strong>기존 댓글 성과</strong><small>측정 완료·관찰 가중치 높은 순 · 최대 8개 표시</small></div>
            {stats.items.slice(0,8).map(item=>(
              <div className="model-evidence-row" key={item.video_id+':'+item.comment_id}>
                <div className="model-evidence-text">
                  <strong>{item.comment}</strong>
                  <small>{item.measured
                    ? `좋아요 ${fmt(item.likes ?? 0)} · 답글 ${fmt(item.replies ?? 0)}`
                    : '본인 댓글 확인 · 공개 반응 미측정'} · {new Date(item.published_at).toLocaleDateString('ko-KR')}</small>
                </div>
                <div className="model-evidence-track" aria-hidden="true"><span style={{width:(item.weight/3*100).toFixed(1)+'%'}} /></div>
                <b className="model-evidence-weight">{item.weight.toFixed(2)}×</b>
                {item.comment_url ? <a href={item.comment_url} target="_blank" rel="noopener noreferrer" aria-label="원본 YouTube 댓글 열기"><ExternalLink size={15}/></a> : <span />}
              </div>
            ))}
          </div>
          <p className="eng-note">관찰 가중치(1.00~3.00배)는 공개 좋아요·답글을 비교하기 위한 표시값입니다. AI Ranker 학습에 자동 반영하지 않습니다. 과거 CSV에는 AI 추천 ID가 없으므로 AI가 생성한 댓글 성과와 혼합하지 않습니다.</p>
          {(!getStoredApiAccessToken() || !getStoredYouTubeApiKey()) && (
            <p className="eng-note">새 공개 반응을 확인하려면 <Link to="/account/connect">서버 관리자 인증과 YouTube Data API Key</Link>가 필요합니다. CSV로 검증된 내역 자체는 현재 브라우저에 남습니다.</p>
          )}
        </>
      ) : <p className="eng-note">아직 확인된 CSV 댓글이 없습니다. <Link to="/my-comments">내 댓글 성과에서 Google Takeout 댓글 CSV를 가져오기</Link> 하면 본인 댓글 확인 후 여기에 나타납니다. 단순 CSV 업로드만으로 성과를 추정하지 않습니다.</p>}
    </section>
  );
}
