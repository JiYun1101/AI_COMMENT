import { ArrowRight, Database, Layers3, LoaderCircle, RefreshCw, ExternalLink } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  getAccountMode, getModelDataProgress, getStoredApiAccessToken, getStoredYouTubeApiKey,
  listAnalyses, listMyComments, lookupPublicCommentMetrics,
} from '../../api/client';
import { cachedAccount, getPrivateAnalysisOverview, listPrivatePublishedReceipts } from '../../api/account';
import type { PrivatePublishedReceipt } from '../../api/account';
import type { AnalysisSummary, ModelDataProgress, PublishedComment } from '../../types/comment';
import type { PublicMetricRow } from '../../utils/publicMetricsBackup';
import { storePublicMetricResponse } from '../../utils/publicMetricsBackup';
import { analysisGrowth, buildOutcomeEvidence } from '../../utils/analysisEvidence';
import { listGuestBrowserAnalyses } from '../../utils/browserAnalysisHistory';
import { listSelectedRecommendationIds } from '../../utils/selectionHistory';

const number = (value: number) => value.toLocaleString('ko-KR');
const shortDate = (value: string) => {
  const at = new Date(value);
  return Number.isNaN(at.getTime()) ? '날짜 미확인' : at.toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' });
};

export function ModelDataProgressPanel() {
  const navigate = useNavigate();
  const [data, setData] = useState<ModelDataProgress | null>(null);
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [recommendations, setRecommendations] = useState<Array<{ analysisId: string; recommendationId: string; comment: string }>>([]);
  const [receipts, setReceipts] = useState<PrivatePublishedReceipt[]>([]);
  const [selectedCopies, setSelectedCopies] = useState(0);
  const [published, setPublished] = useState<PublishedComment[]>([]);
  const [publicMetrics, setPublicMetrics] = useState<PublicMetricRow[]>([]);
  const [isMember, setIsMember] = useState(false);
  const [isBrowserGuest, setIsBrowserGuest] = useState(false);
  const [historyReady, setHistoryReady] = useState(false);
  const [limited, setLimited] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshingMetrics, setRefreshingMetrics] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [metricError, setMetricError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setMetricError(null);
    const member = Boolean(cachedAccount());
    setIsMember(member);
    setIsBrowserGuest(!member && listGuestBrowserAnalyses(1).length > 0);
    setSelectedCopies(listSelectedRecommendationIds().length);
    let canShowHistory = false;
    try {
      if (member) {
        // Supabase owner-scoped saved analyses: no server admin token needed.
        const privateData = await getPrivateAnalysisOverview(500);
        setAnalyses(privateData.analyses);
        setRecommendations(privateData.recommendations);
        setLimited(privateData.limited);
      } else {
        // Guests use the shared backend; records are not persistent on Render Free.
        setAnalyses(await listAnalyses(500));
        setRecommendations([]);
        setLimited(false);
      }
      canShowHistory = true;
      setHistoryReady(true);
    } catch (cause) {
      setHistoryReady(false);
      setAnalyses([]);
      setRecommendations([]);
      setError(cause instanceof Error ? cause.message : '분석 기록을 불러오지 못했습니다.');
    }

    if (getStoredApiAccessToken()) {
      try {
        setData(await getModelDataProgress());
      } catch {
        setData(null); // Reference corpus metrics must not be replaced by fabricated values.
      }
    } else {
      setData(null);
    }

    if (member && canShowHistory) {
      try {
        const owned = await listPrivatePublishedReceipts();
        setReceipts(owned);
        if (owned.length && getAccountMode() === 'personal') {
          // Read-only existing metrics; never refresh or post to YouTube automatically.
          try { setPublished((await listMyComments()).items); } catch { setPublished([]); }
        } else {
          setPublished([]);
        }
      } catch (cause) {
        setReceipts([]);
        setPublished([]);
        setMetricError(cause instanceof Error ? cause.message : '게시 기록을 불러오지 못했습니다.');
      }
    } else {
      setReceipts([]);
      setPublished([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const daily = useMemo(
    () => (!isMember && !isBrowserGuest && data?.daily.length ? data.daily : analysisGrowth(analyses)),
    [data, analyses, isMember, isBrowserGuest],
  );
  const chart = useMemo(() => {
    const maximum = Math.max(1, ...daily.map(point => point.cumulative_analyses));
    const denominator = Math.max(1, daily.length - 1);
    return daily.map((point, index) => {
      const x = 18 + 664 * index / denominator;
      const y = 136 - 108 * point.cumulative_analyses / maximum;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
  }, [daily]);

  const outcome = useMemo(
    () => buildOutcomeEvidence(analyses, receipts, published, recommendations, publicMetrics),
    [analyses, receipts, published, recommendations, publicMetrics],
  );
  const total = isMember || isBrowserGuest ? analyses.length : data?.observations.stored_contexts ?? analyses.length;
  const totalRecommendations = isMember
    ? recommendations.length : isBrowserGuest
      ? analyses.reduce((sum, item)=>sum+item.recommendation_count, 0)
      : data?.observations.recommendations ?? analyses.reduce((sum, item)=>sum+item.recommendation_count, 0);
  const new14 = daily.reduce((sum, item)=>sum + item.new_analyses, 0);
  const recent = useMemo(() => [...analyses].sort((a,b)=>b.created_at.localeCompare(a.created_at)).slice(0,6), [analyses]);

  const refreshPublicMetrics = async () => {
    if (!receipts.length || refreshingMetrics) return;
    setRefreshingMetrics(true);
    setMetricError(null);
    try {
      // Explicit read-only request. This uses a YouTube Data API key and server
      // pairing, but never posts, edits, or deletes a comment.
      const response = await lookupPublicCommentMetrics(
        receipts.slice(0,30).map(row=>({ video_id: row.video_id, comment_id: row.comment_id })),
      );
      setPublicMetrics(response.items);
      storePublicMetricResponse(response, 'personal');
    } catch (cause) {
      setMetricError(cause instanceof Error ? cause.message : '공개 반응 조회에 실패했습니다.');
    } finally {
      setRefreshingMetrics(false);
    }
  };

  return (
    <section className="model-panel" aria-label="LLM 앞단 데이터 모델">
      <div className="model-panel-header">
        <div>
          <span className="model-eyebrow"><Database size={15} /> BEFORE THE LLM · DATA FOUNDATION</span>
          <h2>AI가 참고하는 데이터는 어떻게 쌓일까?</h2>
          <p>실제 추천 분석 기록과 게시 댓글의 관측 반응을 구분해 보여줍니다.
            {isMember ? ' 로그인한 내 계정의 비공개 분석 기준입니다.' : isBrowserGuest ? ' 이 브라우저에 보관된 최근 분석 기록 기준입니다. 다른 기기와 자동 동기화되지 않습니다.' : ' 현재 서버의 공용 분석 기준이며, 무료 서버 재시작 시 이전 기록이 사라질 수 있습니다.'}
          </p>
        </div>
        <button type="button" className="btn secondary sm" disabled={loading} onClick={() => void load()}>
          {loading ? <LoaderCircle size={14} className="spin" /> : <RefreshCw size={14} />} 새로고침
        </button>
      </div>
      <div className="model-flow" aria-label="데이터 처리 흐름">
        <div className="model-step"><small>01 · 입력</small><strong>영상·텍스트</strong><span>제목, 설명, 영상 지표</span></div>
        <ArrowRight size={17} aria-hidden="true" />
        <div className="model-step"><small>02 · 코드 분석</small><strong>영상 맥락 분류</strong><span>주제, 형식, 신선도</span></div>
        <ArrowRight size={17} aria-hidden="true" />
        <div className="model-step emphasized"><small>03 · 데이터 참조</small><strong>과거 댓글 검색</strong><span>관련 사례·말투 통계</span></div>
        <ArrowRight size={17} aria-hidden="true" />
        <div className="model-step model-step-llm"><small>04 · 생성 AI</small><strong>LLM 후보 생성</strong><span>앞단의 데이터 참조</span></div>
      </div>
      <p className="model-flow-caption">이후 단계: 안전성 검사 → 학습된 반응 예측 Ranker → 댓글 선택·게시 → 실제 반응 관찰. 사용자 반응 데이터는 모델 가중치를 자동으로 변경하지 않습니다.</p>

      {error && <div className="inline-status error" role="alert">분석 기록 로딩 실패: {error}</div>}
      {loading && !historyReady && <p className="eng-note" role="status">분석 이력과 게시 성과를 불러오는 중…</p>}

      <div className="model-metrics">
        <div><span>누적 분석</span><strong>{historyReady ? number(total) : '—'}<small>회</small></strong><em>{isMember ? '내 계정 저장 기록' : isBrowserGuest ? '브라우저 최근 기록 · 최대 40건' : '공용 서버 저장 기록'}</em></div>
        <div><span>생성된 추천 후보</span><strong>{historyReady ? number(totalRecommendations) : '—'}<small>개</small></strong><em>성공적으로 저장된 분석 기준</em></div>
        <div><span>실제 게시한 추천</span><strong>{isMember ? number(outcome.publishedCount) : '—'}<small>건</small></strong><em>내 계정 게시 영수증과 추천 ID 연결</em></div>
        <div><span>반응이 확인된 게시 댓글</span><strong>{isMember ? number(outcome.positiveCount) : '—'}<small>건</small></strong><em>좋아요 또는 답글 1개 이상 · 측정 {number(outcome.observedCount)}건</em></div>
      </div>

      <div className="model-lower">
        <div className="model-chart-panel">
          <div className="model-subhead"><strong><Layers3 size={16} /> 분석 기록이 쌓이는 흐름</strong><small>지난 14일 · 누적 분석 횟수</small></div>
          {historyReady || data ? (
            <>
              <svg viewBox="0 0 700 155" role="img" aria-label="지난 14일 누적 분석 기록 추세" className="model-progress-chart" preserveAspectRatio="none">
                <line x1="18" y1="136" x2="682" y2="136" stroke="currentColor" opacity="0.15" />
                <polyline points={chart} fill="none" stroke="#6366f1" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <div className="model-chart-footer">
                <span>{daily[0]?.date.slice(5) ?? ''}</span>
                <span>{number(new14)}건 신규 분석</span>
                <span>{daily[daily.length - 1]?.date.slice(5) ?? ''}</span>
              </div>
              {limited && <p className="eng-note">현재 최신 500건까지만 조회했습니다. 이전 누적 건수는 그래프에 포함되지 않을 수 있습니다.</p>}
            </>
          ) : <p className="eng-note">분석 내역을 불러오면 실제 기록으로 그래프를 표시합니다.</p>}
        </div>
        <div className="model-sources">
          <div className="model-subhead"><strong>기존 댓글 참고 데이터</strong><small>LLM 이전 검색 자료 · 공용 서버</small></div>
          {data ? (
            <>
              {data.reference.sources.map((source, index) => (
                <div className="model-source" key={source.name}>
                  <div><span>{source.name.replaceAll('_', ' ')}</span><strong>{number(source.count)}건</strong></div>
                  <div className="model-source-track"><span className={index % 2 === 0 ? 'source-a' : 'source-b'}
                    style={{ width: (100 * source.count / Math.max(1, data.reference.usable_comments)).toFixed(1) + '%' }} /></div>
                </div>
              ))}
              <div className="model-source-foot">
                <span>공용 분석에서 기존 댓글 매칭</span>
                <strong>{number(data.observations.historical_matched_analyses)}건</strong>
              </div>
              <small className="eng-note">공용 서버 지표에 회원별 Supabase 비공개 분석은 포함하지 않습니다.</small>
              <small className="eng-note">매칭 분석당 평균 {data.observations.average_matches == null ? '—' : number(data.observations.average_matches)}개 사례 참조 · 회원별 분석과 별도 집계</small>
            </>
          ) : (
            <p className="eng-note">참조 댓글 원본 통계는 별도 서버 관리자 연결 시 표시됩니다.
              <Link to="/account/connect"> 서버 연결 설정</Link>
            </p>
          )}
        </div>
      </div>

      <div className="model-recent">
        <div className="model-subhead"><strong>최근 분석 내역</strong><small>{isMember ? '내 계정 저장 기록' : isBrowserGuest ? '이 브라우저 저장 기록' : '공용 서버 최신 기록'} · 최신 6건</small></div>
        {recent.length ? (
          <div className="model-recent-list">
            {recent.map(item => (
              <button type="button" key={item.id} className="model-recent-row"
                onClick={() => navigate('/?analysis=' + encodeURIComponent(item.id))}>
                <span className="model-recent-date">{shortDate(item.created_at)}</span>
                <span className="model-recent-title" title={item.video_title || item.source_text}>{item.video_title || item.source_text || '제목 없음'}</span>
                <span className="model-recent-count">추천 {item.recommendation_count}개</span>
                <ArrowRight size={14} aria-hidden="true" />
              </button>
            ))}
          </div>
        ) : <p className="eng-note">{historyReady ? '저장된 분석이 아직 없습니다. 첫 댓글 추천을 생성하면 이곳에 쌓입니다.' : '기록을 불러오지 못했습니다.'}</p>}
      </div>

      <div className="model-outcomes">
        <div className="model-subhead">
          <strong>실제 선택·게시 댓글의 성과 가중치</strong>
          <small>게시 영수증 + 공개 좋아요·답글 기반 · 모델 학습 가중치 아님</small>
        </div>
        <div className="model-outcome-kpis">
          <span>복사한 추천 <b>{number(selectedCopies)}건</b></span>
          <span>게시 확인 <b>{number(outcome.publishedCount)}건</b></span>
          <span>반응 측정 <b>{number(outcome.observedCount)}건</b></span>
          <span>긍정 반응 발생 <b>{number(outcome.positiveCount)}건</b></span>
          {isMember && receipts.length > 0 && (
            <button type="button" className="btn secondary sm" disabled={refreshingMetrics || !getStoredApiAccessToken() || !getStoredYouTubeApiKey()}
              onClick={() => void refreshPublicMetrics()}>
              {refreshingMetrics ? <LoaderCircle size={13} className="spin" /> : <RefreshCw size={13} />} 공개 반응 확인
            </button>
          )}
        </div>
        {metricError && <p className="eng-note" role="alert">{metricError}</p>}
        {outcome.weighted.length ? (
          <div className="model-evidence-list">
            {outcome.weighted.slice(0,5).map(item=>(
              <div className="model-evidence-row" key={item.recommendationId}>
                <div className="model-evidence-text">
                  <strong title={item.comment}>{item.comment}</strong>
                  <small>{item.title} · {item.measured ? `좋아요 ${number(item.likes ?? 0)} · 답글 ${number(item.replies ?? 0)}` : '게시 확인 · 공개 반응 미측정'}</small>
                </div>
                <div className="model-evidence-track" aria-hidden="true"><span style={{width: ((item.weight/3)*100).toFixed(1)+'%'}} /></div>
                <b className="model-evidence-weight">{item.weight.toFixed(2)}×</b>
                {item.url && <a href={item.url} target="_blank" rel="noopener noreferrer" aria-label="게시 댓글 열기"><ExternalLink size={15} /></a>}
              </div>
            ))}
          </div>
        ) : <p className="eng-note">{isMember ? '추천 댓글을 실제 게시한 기록이 생기면 여기에 연결됩니다. 반응 확인 전에는 성과가 있다고 가정하지 않습니다.' : '회원 로그인 후 게시한 추천 댓글을 안전하게 계정과 연결할 수 있습니다.'}</p>}
        <p className="eng-note">복사한 댓글은 이용자가 후보를 선택한 신호지만 실제 게시나 성과로 간주하지 않습니다. 게시 영수증과 공개 반응이 확인된 댓글에만 아래 관찰 가중치를 적용합니다.</p>
        <p className="eng-note">표시 가중치 = 1 + 0.25 × log₂(1+좋아요) + 0.5 × log₂(1+답글), 최대 3배. 실제 게시 확인만으로는 1.00배이며, 반응이 미측정인 경우 성과가 아닌 게시 기록으로만 표시합니다. 이 수치는 관찰 결과를 살펴보기 위한 상대 지표이며 추천 모델을 자동으로 재학습하지 않습니다.</p>
        {isMember && receipts.length > 0 && (!getStoredApiAccessToken() || !getStoredYouTubeApiKey()) && (
          <p className="eng-note">공개 반응을 새로 측정하려면 <Link to="/account/connect">서버 연결과 YouTube Data API Key</Link>가 필요합니다. 계정에 저장된 분석·게시 기록 조회는 별도로 동작합니다.</p>
        )}
      </div>
      <p className="model-safety-note"><strong>데이터 누적 ≠ 자동 학습.</strong> 분석 기록과 실제 게시 반응은 별도로 저장·표시됩니다. 기존 반응 예측 Ranker의 모델 가중치는 이 화면의 관찰 성과에 따라 자동 갱신되지 않습니다.
      {isMember ? ' 비공개 분석과 게시 영수증은 해당 로그인 계정 기준입니다.' : isBrowserGuest ? ' 게스트 분석은 현재 브라우저에 최대 40개 보관되며 다른 기기에는 공유되지 않습니다. 영구 보존하려면 계정 로그인을 사용하세요.' : ' 공용 기록은 Render 무료 서버 재시작 시 유실될 수 있습니다. 지속 저장하려면 계정 로그인을 사용하세요.'}</p>
    </section>
  );
}
