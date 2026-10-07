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
import { getHealth, recommend } from '../api/client';
import { Header } from '../components/layout/Header';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import type { RecommendResponse, ServiceHealth } from '../types/comment';
import { isValidYouTubeVideoUrl } from '../utils/youtube';

type IntentKey = 'question' | 'praise' | 'confusion' | 'complaint' | 'purchase' | 'risk';

interface IntentDefinition {
  key: IntentKey;
  label: string;
  description: string;
}

interface ReactionItem {
  comment: string;
  intent: IntentKey;
  score: number | null;
  selected: boolean;
}

const INTENTS: IntentDefinition[] = [
  { key: 'question', label: '질문', description: '추가 정보나 설명을 요구하는 반응' },
  { key: 'praise', label: '칭찬', description: '긍정·공감·호감 중심의 반응' },
  { key: 'confusion', label: '혼란', description: '이해가 어렵거나 맥락이 불분명한 반응' },
  { key: 'complaint', label: '불만', description: '아쉬움·비판·불편을 드러내는 반응' },
  { key: 'purchase', label: '구매 의도', description: '가격·구매·출시 여부에 관심을 보이는 반응' },
  { key: 'risk', label: '리스크', description: '논란·신뢰·안전 이슈로 번질 수 있는 반응' },
];

function classifyIntent(comment: string, type: string): IntentKey {
  const text = comment.toLowerCase();
  if (/(사기|거짓|조작|불법|혐오|신고|논란|위험|허위|과장광고|환불)/i.test(text)) return 'risk';
  if (/(구매|구입|사고 싶|살까|사야|가격|얼마|출시|재입고|어디서 사|링크 있|예약)/i.test(text)) return 'purchase';
  if (/(별로|아쉽|실망|불편|비싸|싫|최악|왜 이렇게|문제 있|개선|답답)/i.test(text) || type === 'negative') return 'complaint';
  if (/(무슨 뜻|이해가 안|이해 안|헷갈|모르겠|차이가 뭐|어떤 의미|설명이 부족|왜 그런)/i.test(text)) return 'confusion';
  if (comment.includes('?') || type === 'question' || /(궁금|어떻게|왜 |뭐가|언제|어디|누가|인가요)/i.test(text)) return 'question';
  return 'praise';
}

function buildReactionItems(response: RecommendResponse): ReactionItem[] {
  const traced: ReactionItem[] = (response.trace?.candidates ?? [])
    .filter((candidate) => candidate.safety === 'passed' && !candidate.duplicate)
    .sort((a, b) => {
      if (a.selected !== b.selected) return a.selected ? -1 : 1;
      return (b.ranker_score ?? -1) - (a.ranker_score ?? -1);
    })
    .map((candidate) => ({
      comment: candidate.comment,
      intent: classifyIntent(candidate.comment, candidate.type),
      score: candidate.ranker_score,
      selected: candidate.selected,
    }));

  const fallback: ReactionItem[] = response.recommendations.map((item) => ({
    comment: item.comment,
    intent: classifyIntent(item.comment, item.type),
    score: item.predicted_score,
    selected: true,
  }));

  const seen = new Set<string>();
  return [...traced, ...fallback].filter((item) => {
    const key = item.comment.trim();
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
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
              <p>기존 댓글 생성 파이프라인의 Safety 통과 후보를 재사용해 질문·칭찬·혼란·불만·구매 의도·리스크 6개 반응으로 묶어 보여줍니다.</p>
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
                  setError(null);
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void runPreview();
                }}
              />
              <button type="button" className="btn primary reaction-run-button" onClick={() => void runPreview()} disabled={!urlValid || loading || missingSetup}>
                {loading ? <LoaderCircle size={15} className="spin" /> : <Play size={15} />}
                {loading ? '분석 중...' : '반응 미리보기'}
              </button>
            </div>
            {url.trim() && !urlValid && <div className="reaction-inline-error">올바른 YouTube 영상 URL을 입력해주세요.</div>}
            {missingSetup && (
              <div className="reaction-readiness">
                <AlertCircle size={16} />
                <span>YouTube 또는 LLM 연결이 필요합니다.</span>
                <button type="button" onClick={() => navigate('/account/connect')}><Settings size={13} /> 계정 설정</button>
              </div>
            )}
            {error && <div className="reaction-inline-error">{error}</div>}
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
                  <p>Safety를 통과한 생성 후보를 기준으로 집계했습니다.</p>
                  <div className="reaction-mini-status"><CheckCircle2 size={14} /> 기존 Ranker 결과 재사용</div>
                </article>
                <article className="reaction-summary-card">
                  <span className="reaction-card-kicker"><MessageCircleQuestion size={14} /> 반응 다양성</span>
                  <strong>{distribution.filter((item) => item.count > 0).length}/6</strong>
                  <p>현재 영상에서 감지된 서로 다른 intent 유형입니다.</p>
                  <div className="reaction-mini-status">분류기는 다음 단계에서 모델화 예정</div>
                </article>
              </section>

              <section className="reaction-panel">
                <div className="reaction-panel-head">
                  <div><span>REACTION MIX</span><h3>예상 반응 분포</h3></div>
                  <small>확률이 아니라 현재 생성 후보의 구성 비율입니다.</small>
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
                <div><strong>다음 단계</strong><span>실제 채널 댓글을 수집하면 게시 후 실제 반응과 이 예상 분포를 비교해 calibration할 수 있습니다.</span></div>
                <button type="button" className="btn secondary" onClick={() => navigate('/')}>댓글 추천으로 이동 <ArrowRight size={14} /></button>
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
