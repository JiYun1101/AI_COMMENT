import {
  Activity,
  AlertCircle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Eye,
  LoaderCircle,
  MessageCircleQuestion,
  Play,
  Settings,
  Sparkles,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAudienceObserved, getHealth, recommend, saveAudienceSnapshot } from '../api/client';
import { Header } from '../components/layout/Header';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import type { AudienceObservationReport, AudienceSnapshotSummary, RecommendResponse, ServiceHealth } from '../types/comment';
import { extractYouTubeVideoId, isValidYouTubeVideoUrl } from '../utils/youtube';
import { INTENTS, classifyIntent, attachLocalComparison, type IntentKey } from '../utils/audienceComparison';

interface ReactionItem {
  comment: string;
  intent: IntentKey;
  score: number | null;
  selected: boolean;
}

function buildReactionItems(response: RecommendResponse): ReactionItem[] {
  // The backend's observed comparison uses saved final Top-K, not all
  // Safety-passed trace candidates. Keep the chart and score cards in sync.
  return response.recommendations.filter((item) => item.comment.trim()).map((item) => ({
    comment: item.comment,
    intent: classifyIntent(item.comment, item.type),
    score: item.predicted_score,
    selected: true,
  }));
}

function labelFor(key: IntentKey) {
  return INTENTS.find((intent) => intent.key === key)?.label ?? key;
}

export function ReactionPreviewPage() {
  const navigate = useNavigate();
  const [url, setUrl] = useState('');
  const [health, setHealth] = useState<ServiceHealth | null>(null);
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<RecommendResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [observed, setObserved] = useState<AudienceObservationReport | null>(null);
  const [observing, setObserving] = useState(false);
  const [observationError, setObservationError] = useState<string | null>(null);
  const [savingSnapshot, setSavingSnapshot] = useState(false);
  const [savedSnapshot, setSavedSnapshot] = useState<AudienceSnapshotSummary | null>(null);

  const urlValid = useMemo(() => isValidYouTubeVideoUrl(url), [url]);
  const reactions = useMemo(() => (response ? buildReactionItems(response) : []), [response]);
  const distribution = useMemo(() => {
    const total = reactions.length || 1;
    return INTENTS.map((intent) => {
      const count = reactions.filter((item) => item.intent === intent.key).length;
      return { ...intent, count, percentage: Math.round((count / total) * 100) };
    });
  }, [reactions]);
  const dominant = useMemo(
    () => distribution.reduce((best, item) => (item.count > best.count ? item : best), distribution[0]),
    [distribution],
  );
  const representative = useMemo(
    () => [...reactions].sort((a, b) => (b.score ?? -1) - (a.score ?? -1)).slice(0, 8),
    [reactions],
  );

  const missingSetup = Boolean(health && (!health.youtube.configured || !health.llm.ready));

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  const runPreview = async () => {
    if (!urlValid || loading) return;
    setLoading(true);
    setError(null);
    setResponse(null);
    setObserved(null);
    setSavedSnapshot(null);
    try {
      const next = await recommend({
        youtube_url: url.trim(),
        additional_context: '영상 반응 미리보기용입니다. 실제 시청자가 남길 법한 서로 다른 관점의 반응을 다양하게 생성해주세요.',
        top_k: 10,
      });
      setResponse(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : '영상 반응을 분석하지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };


  const loadObserved = async () => {
    const videoId = extractYouTubeVideoId(url);
    if (!videoId || observing) return;
    setObserving(true);
    setObservationError(null);
    setObserved(null);
    setSavedSnapshot(null);
    try {
      const id = response?.youtube_context?.video_id === videoId ? response.analysis_id : null;
      const report = await getAudienceObserved(videoId, id);
      setObserved(response?.youtube_context?.video_id === videoId
        ? attachLocalComparison(report, response.recommendations) : report);
    } catch (err) {
      setObservationError(err instanceof Error ? err.message : '실제 댓글을 불러오지 못했습니다.');
    } finally {
      setObserving(false);
    }
  };

  const persistObserved = async () => {
    const videoId = extractYouTubeVideoId(url);
    if (!videoId || savingSnapshot) return;
    setSavingSnapshot(true);
    setObservationError(null);
    try {
      const result = await saveAudienceSnapshot(videoId, observed?.analysis_id);
      setObserved(response?.youtube_context?.video_id === videoId
        ? attachLocalComparison(result.report, response.recommendations) : result.report);
      setSavedSnapshot(result.snapshot);
    } catch (err) {
      setObservationError(err instanceof Error ? err.message : '실측 기록을 저장하지 못했습니다. 서버 연결을 확인해주세요.');
    } finally {
      setSavingSnapshot(false);
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
      <Sidebar current="reaction" onNav={handleNav} />
      <div className="main">
        <Header title="영상 반응 미리보기" subtitle="게시 전, 현재 모델이 예상하는 시청자 반응의 방향과 대표 댓글을 확인합니다." />

        <main className="reaction-page">
          <section className="reaction-hero">
            <div>
              <span className="reaction-kicker"><Eye size={14} /> AUDIENCE REACTION PREVIEW</span>
              <h2>이 영상을 본 시청자는<br />어떤 반응을 남길까?</h2>
              <p>기존 댓글 생성 파이프라인의 최종 Top-K 후보를 사용해 질문·칭찬·혼란·불만·구매 의도·리스크·기타 7개 반응으로 묶어 보여줍니다.</p>
            </div>
            <div className="reaction-hero-badge">
              <Activity size={20} />
              <div>
                <strong>Expected Audience Reaction</strong>
                <span>현재는 규칙 기반 intent 분류를 사용하는 MVP입니다.</span>
              </div>
            </div>
          </section>

          <section className="reaction-input-card">
            <div className="reaction-input-copy">
              <label htmlFor="reaction-youtube-url">YouTube 영상 URL</label>
              <span>공개 영상 URL을 입력하면 영상 맥락과 예상 댓글 후보를 분석합니다.</span>
            </div>
            <div className="reaction-input-row">
              <input
                id="reaction-youtube-url"
                type="url"
                value={url}
                placeholder="https://www.youtube.com/watch?v=..."
                onChange={(event) => {
                  setUrl(event.target.value);
                  setResponse(null);
                  setObserved(null);
                  setSavedSnapshot(null);
                  setObservationError(null);
                  setError(null);
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void runPreview();
                }}
              />
              <button type="button" className="btn primary reaction-run-button" onClick={() => void runPreview()} disabled={!urlValid || loading || missingSetup}>
                {loading ? <LoaderCircle size={15} className="spin" /> : <Play size={15} />}
                {loading ? '분석 중...' : '예상 반응 생성'}
              </button>
            </div>
            {url.trim() && !urlValid && <div className="reaction-inline-error">올바른 YouTube 영상 URL을 입력해주세요.</div>}
            {missingSetup && (
              <div className="reaction-readiness">
                <AlertCircle size={16} />
                <span>예상 반응 생성은 YouTube·LLM 연결이 필요하지만 실제 댓글 분석은 LLM 없이 할 수 있습니다.</span>
                <button type="button" onClick={() => navigate('/account/connect')}><Settings size={13} /> 계정 설정</button>
              </div>
            )}
            {error && <div className="reaction-inline-error">{error}</div>}
          </section>


          <section className="reaction-panel audience-observation-panel">
            <div className="reaction-panel-head">
              <div><span>OBSERVED AUDIENCE</span><h3>실제 댓글 반응</h3></div>
              <small>LLM 없이 YouTube의 공개 댓글을 읽고 유형별로 분류합니다.</small>
            </div>
            <div className="audience-observation-actions">
              <button className="btn secondary" type="button" onClick={() => void loadObserved()} disabled={!urlValid || observing}>
                {observing ? <LoaderCircle size={15} className="spin" /> : <BarChart3 size={15} />}
                {observing ? '조회 중...' : '실제 반응 불러오기'}
              </button>
              {observed && (
                <button className="btn secondary" type="button" onClick={() => void persistObserved()} disabled={savingSnapshot}>
                  {savingSnapshot ? <LoaderCircle size={15} className="spin" /> : <CheckCircle2 size={15} />}
                  {savingSnapshot ? '저장 중...' : '실측 스냅샷 저장'}
                </button>
              )}
            </div>
            {observationError && <div role="alert" className="reaction-inline-error">{observationError}</div>}
            {savedSnapshot && (
              <p className="audience-observation-note">
                저장됨 · {new Date(savedSnapshot.observed_at).toLocaleString()} · {savedSnapshot.sample_count}개 댓글
              </p>
            )}
            {observed && (
              <>
                <p className="audience-observation-note">공개 최상위 댓글 {observed.observed.total}개 · 관련도순 표본</p>
                {observed.observed.total === 0 ? (
                  <p className="audience-observation-note">공개 댓글이 조회되지 않아 비교할 수 없습니다.</p>
                ) : (
                  <div className="reaction-distribution">
                    {observed.observed.distribution.map((item) => (
                      <div className="reaction-dist-row" key={item.key}>
                        <div className="reaction-dist-label"><strong>{item.label}</strong><span>{item.count}개</span></div>
                        <div className="reaction-dist-track"><span style={{ width: item.percentage + '%' }} /></div>
                        <b>{item.percentage.toFixed(1)}%</b>
                      </div>
                    ))}
                  </div>
                )}
                {observed.comparison && (
                  <div className="audience-comparison">
                    <h4>예상 후보 ↔ 실제 댓글</h4>
                    <p>추천된 댓글 후보 {observed.expected?.total}개와 실제 댓글 {observed.observed.total}개의 유형 구성 차이입니다.</p>
                    <div className="audience-comparison-header"><span>유형</span><span>생성 후보</span><span>실제 댓글</span><span>차이</span></div>
                    {observed.comparison.distribution.map((item) => (
                      <div className="audience-comparison-row" key={item.key}>
                        <span>{item.label}</span>
                        <span>{item.expected_percentage.toFixed(1)}%</span>
                        <span>{item.observed_percentage.toFixed(1)}%</span>
                        <strong>{item.delta_percentage_points > 0 ? '+' : ''}{item.delta_percentage_points.toFixed(1)}%p</strong>
                      </div>
                    ))}
                    <p className="audience-observation-note">{observed.comparison.warning}</p>
                  </div>
                )}
                {observed.examples.length > 0 && (
                  <div className="audience-observed-comments">
                    <h4>실제 댓글 예시</h4>
                    {observed.examples.map((item) => (
                      <article key={item.id} className="audience-observed-comment">
                        <span>{observed.observed.distribution.find((entry) => entry.key === item.intent)?.label ?? '기타'}</span>
                        <p>{item.text}</p>
                        <small>좋아요 {item.like_count} · 답글 {item.reply_count}</small>
                      </article>
                    ))}
                  </div>
                )}
                <p className="audience-observation-note">{observed.caveat}</p>
              </>
            )}
          </section>

          {loading && (
            <section className="reaction-loading">
              <LoaderCircle size={24} className="spin" />
              <div><strong>예상 시청자 반응을 구성하고 있습니다</strong><span>영상 맥락 → 댓글 후보 → Safety → Ranker → intent 분류</span></div>
            </section>
          )}

          {response && reactions.length > 0 && (
            <>
              {response.youtube_context && (
                <section className="reaction-video-card">
                  {response.youtube_context.thumbnail_url ? <img src={response.youtube_context.thumbnail_url} alt="" /> : <div className="reaction-video-placeholder"><Play size={22} /></div>}
                  <div>
                    <span className="reaction-video-channel">{response.youtube_context.channel || 'YouTube'}</span>
                    <h3>{response.youtube_context.title}</h3>
                    <div className="reaction-video-meta">
                      {response.youtube_context.view_count != null && <span>조회수 {response.youtube_context.view_count.toLocaleString()}</span>}
                      {response.youtube_context.comment_count != null && <span>댓글 {response.youtube_context.comment_count.toLocaleString()}</span>}
                      {response.context && <span>과거 댓글 {response.context.historical_match_count}건 참조</span>}
                    </div>
                  </div>
                </section>
              )}

              <section className="reaction-summary-grid">
                <article className="reaction-summary-card primary">
                  <span className="reaction-card-kicker"><Sparkles size={14} /> 가장 두드러진 반응</span>
                  <strong>{labelFor(dominant.key)}</strong>
                  <p>{dominant.description}</p>
                  <div className="reaction-big-number">{dominant.percentage}%</div>
                </article>
                <article className="reaction-summary-card">
                  <span className="reaction-card-kicker"><BarChart3 size={14} /> 분석 후보</span>
                  <strong>{reactions.length}개</strong>
                  <p>Safety와 Ranker를 통과한 최종 Top-K 후보를 집계했습니다.</p>
                  <div className="reaction-mini-status"><CheckCircle2 size={14} /> 기존 Ranker 결과 재사용</div>
                </article>
                <article className="reaction-summary-card">
                  <span className="reaction-card-kicker"><MessageCircleQuestion size={14} /> 반응 다양성</span>
                  <strong>{distribution.filter((item) => item.count > 0).length}/7</strong>
                  <p>현재 영상에서 감지된 서로 다른 intent 유형입니다.</p>
                  <div className="reaction-mini-status">분류기는 다음 단계에서 모델화 예정</div>
                </article>
              </section>

              <section className="reaction-panel">
                <div className="reaction-panel-head">
                  <div><span>REACTION MIX</span><h3>예상 반응 분포</h3></div>
                  <small>확률이 아니라 현재 최종 Top-K 생성 후보의 구성 비율입니다.</small>
                </div>
                <div className="reaction-distribution">
                  {distribution.map((item) => (
                    <div className="reaction-dist-row" key={item.key}>
                      <div className="reaction-dist-label"><strong>{item.label}</strong><span>{item.count}개</span></div>
                      <div className="reaction-dist-track"><span style={{ width: `${item.percentage}%` }} /></div>
                      <b>{item.percentage}%</b>
                    </div>
                  ))}
                </div>
              </section>

              <section className="reaction-panel">
                <div className="reaction-panel-head">
                  <div><span>EXPECTED COMMENTS</span><h3>대표 예상 반응</h3></div>
                  <small>Ranker 점수가 높은 후보부터 표시합니다.</small>
                </div>
                <div className="reaction-comment-grid">
                  {representative.map((item, index) => (
                    <article className="reaction-comment-card" key={`${item.comment}-${index}`}>
                      <div className="reaction-comment-top">
                        <span className={`reaction-intent reaction-intent-${item.intent}`}>{labelFor(item.intent)}</span>
                        {item.selected && <span className="reaction-topk">Top-K</span>}
                      </div>
                      <p>{item.comment}</p>
                      <div className="reaction-comment-score"><span>반응 모델 점수</span><strong>{item.score == null ? '—' : item.score.toFixed(1)}</strong></div>
                    </article>
                  ))}
                </div>
              </section>

              <section className="reaction-next-step">
                <div><strong>다음 단계</strong><span>실제 댓글을 조회해 예상 후보와 비교할 수 있습니다. 저장한 표본은 후속 검증과 Audience Memory의 기반이 됩니다.</span></div>
                <button type="button" className="btn secondary" onClick={() => navigate('/')}>댓글 추천으로 이동 <ArrowRight size={14} /></button>
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
