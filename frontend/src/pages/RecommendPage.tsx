import { Check, Copy, RefreshCw, ThumbsDown, ThumbsUp } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import { Header } from '../components/layout/Header';
import { Composer } from '../components/recommend/Composer';
import { EmptyExamples, type ExampleVideo } from '../components/recommend/EmptyExamples';
import { HistoryStrip } from '../components/recommend/HistoryStrip';
import { TypeTag } from '../components/TypeTag';
import { getAnalysis, getVideoPreview, recommend, sendFeedback } from '../api/client';
import { isValidYouTubeVideoUrl } from '../utils/youtube';
import type {
  Category,
  CommentRecommendation,
  GenerationMeta,
  ResolvedCategory,
  VideoPreviewData,
} from '../types/comment';

type Mode = 'url' | 'manual';

export function RecommendPage() {
  const navigate = useNavigate();
  const [mode, setModeState] = useState<Mode>('url');
  const [url, setUrlState] = useState('');
  const [manual, setManualState] = useState('');
  const [additionalContext, setAdditionalContextState] = useState('');
  const [category, setCategoryState] = useState<Category>('auto');
  const [count, setCountState] = useState(5);
  const [preview, setPreview] = useState<VideoPreviewData | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewReloadToken, setPreviewReloadToken] = useState(0);

  const [submitting, setSubmitting] = useState(false);
  const [results, setResults] = useState<CommentRecommendation[] | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [resolvedCategory, setResolvedCategory] = useState<ResolvedCategory | null>(null);
  const [generation, setGeneration] = useState<GenerationMeta | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const urlValid = useMemo(() => isValidYouTubeVideoUrl(url), [url]);
  const isEmpty = mode === 'url' ? !url.trim() : !manual.trim();

  const invalidateResults = () => {
    setResults(null);
    setAnalysisId(null);
    setResolvedCategory(null);
    setGeneration(null);
    setCopiedId(null);
  };

  useEffect(() => {
    if (mode !== 'url' || !url.trim() || !urlValid) {
      setPreviewLoading(false);
      if (!url.trim() || !urlValid) setPreview(null);
      return;
    }

    let cancelled = false;
    setPreviewLoading(true);
    setPreviewError(null);
    const timer = window.setTimeout(() => {
      getVideoPreview(url.trim())
        .then((nextPreview) => {
          if (cancelled) return;
          setPreview(nextPreview);
          setPreviewError(null);
        })
        .catch((err) => {
          if (cancelled) return;
          setPreview(null);
          setPreviewError(err instanceof Error ? err.message : '영상 정보를 불러오지 못했습니다.');
        })
        .finally(() => {
          if (!cancelled) setPreviewLoading(false);
        });
    }, 500);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [mode, url, urlValid, previewReloadToken]);

  const setMode = (nextMode: Mode) => {
    if (nextMode === mode) return;
    setModeState(nextMode);
    setError(null);
    setPreviewError(null);
    invalidateResults();
  };

  const setUrl = (nextUrl: string) => {
    setUrlState(nextUrl);
    setPreview(null);
    setPreviewError(null);
    setError(null);
    invalidateResults();
  };

  const setManual = (nextManual: string) => {
    setManualState(nextManual);
    setError(null);
    invalidateResults();
  };

  const setAdditionalContext = (value: string) => {
    setAdditionalContextState(value);
    invalidateResults();
  };

  const setCategory = (value: Category) => {
    setCategoryState(value);
    invalidateResults();
  };

  const setCount = (value: number) => {
    setCountState(value);
    invalidateResults();
  };

  const clearPreview = () => {
    setUrlState('');
    setPreview(null);
    setPreviewError(null);
    setError(null);
    invalidateResults();
  };

  const switchToManual = () => {
    setModeState('manual');
    if (!manual.trim() && additionalContext.trim()) setManualState(additionalContext.trim());
    setPreviewError(null);
    setError(null);
    invalidateResults();
  };

  const pickExample = (example: ExampleVideo) => {
    setModeState('manual');
    setCategoryState(example.category);
    setManualState(`${example.title}\n채널: ${example.channel}`);
    setUrlState('');
    setAdditionalContextState('');
    setPreview(null);
    setPreviewError(null);
    setError(null);
    invalidateResults();
  };

  const submit = async () => {
    if (mode === 'url' ? !urlValid : manual.trim().length < 5) return;

    setSubmitting(true);
    setError(null);
    try {
      const response = await recommend(
        mode === 'url'
          ? {
              youtube_url: url.trim(),
              additional_context: additionalContext.trim() || undefined,
              category,
              top_k: count,
            }
          : { post_text: manual.trim(), category, top_k: count },
      );
      setResults(response.recommendations);
      setAnalysisId(response.analysis_id);
      setResolvedCategory(response.resolved_category);
      setGeneration(response.generation);
      if (response.youtube_context) setPreview(response.youtube_context);
    } catch (err) {
      setError(err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  const loadHistory = async (id: string) => {
    setError(null);
    try {
      const detail = await getAnalysis(id);
      setCategoryState(detail.category);
      setAnalysisId(detail.id);
      setResolvedCategory(detail.category);
      setGeneration(null);
      setResults(detail.recommendations);
      if (detail.source_type === 'youtube' && detail.youtube_url) {
        setModeState('url');
        setUrlState(detail.youtube_url);
        setManualState('');
        setPreview(null);
      } else {
        setModeState('manual');
        setManualState(detail.source_text);
        setUrlState('');
        setPreview(null);
      }
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      setError(err instanceof Error ? err.message : '분석 기록을 불러오지 못했습니다.');
    }
  };

  const copyComment = async (recommendation: CommentRecommendation) => {
    try {
      await navigator.clipboard.writeText(recommendation.comment);
      setCopiedId(recommendation.id);
      window.setTimeout(() => setCopiedId((current) => (current === recommendation.id ? null : current)), 1500);
    } catch {
      setError('클립보드 권한이 없어 복사하지 못했습니다.');
    }
  };

  const saveFeedback = async (recommendationId: string, useful: boolean) => {
    try {
      const feedback = await sendFeedback(recommendationId, useful);
      setResults((current) =>
        current?.map((item) => (item.id === recommendationId ? { ...item, feedback } : item)) ?? null,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : '피드백 저장에 실패했습니다.');
    }
  };

  const handleNav = (key: SidebarKey) => {
    if (key === 'dashboard') navigate('/dashboard');
    if (key === 'comments') navigate('/');
  };

  return (
    <div className="app">
      <Sidebar current="comments" onNav={handleNav} />
      <div className="main">
        <Header title="댓글 추천" />
        <div className="recommend">
          <div className="hero">
            <span className="hero-eyebrow"><span className="dot" /> AI 댓글 추천 · v0.4</span>
            <h1 className="hero-title">영상에 어울리는<br />안전한 댓글을 찾아드립니다</h1>
            <p className="hero-sub">영상 문맥으로 후보를 만들고 안전 필터와 반응 예측 모델로 순위를 정합니다.</p>
          </div>

          <Composer
            mode={mode}
            setMode={setMode}
            url={url}
            setUrl={setUrl}
            urlValid={urlValid}
            manual={manual}
            setManual={setManual}
            additionalContext={additionalContext}
            setAdditionalContext={setAdditionalContext}
            category={category}
            setCategory={setCategory}
            count={count}
            setCount={setCount}
            preview={preview}
            previewLoading={previewLoading}
            previewError={previewError}
            onRetryPreview={() => setPreviewReloadToken((value) => value + 1)}
            onSwitchToManual={switchToManual}
            onClearPreview={clearPreview}
            onSubmit={submit}
            submitting={submitting}
          />

          {isEmpty && !results && <EmptyExamples onPick={pickExample} />}
          {error && <div className="result-error">{error}</div>}

          {results && (
            <section>
              <div className="section-h">
                <div>
                  <h2>추천 댓글</h2>
                  <div className="sub result-summary" style={{ marginTop: 3 }}>
                    {results.length}개 추천
                    {resolvedCategory && <> · {resolvedCategory === 'vlog' ? '브이로그' : '사회이슈'}</>}
                    {generation && <> · 안전 후보 {generation.safe_candidate_count}개</>}
                    {analysisId && <span className="result-saved"> · 자동 저장됨</span>}
                  </div>
                </div>
                <button type="button" className="btn secondary sm" onClick={submit} disabled={submitting}>
                  <RefreshCw size={13} /> 다시 생성
                </button>
              </div>
              <div className="results">
                {results.map((r) => (
                  <div className="result-card" key={r.id}>
                    <span className={`result-rank${r.rank === 1 ? ' top' : ''}`}>{r.rank}</span>
                    <div className="result-body">
                      <div className="result-text">{r.comment}</div>
                      <div className="result-meta">
                        <TypeTag type={r.type} />
                        <span className="result-score">
                          예상 점수 {r.predicted_score.toFixed(1)}%
                          <span className="result-score-bar">
                            <span className="result-score-fill" style={{ width: `${Math.min(100, Math.max(0, r.predicted_score))}%` }} />
                          </span>
                        </span>
                      </div>
                      <div className="result-actions">
                        <button type="button" className="result-action" onClick={() => copyComment(r)}>
                          {copiedId === r.id ? <Check size={13} /> : <Copy size={13} />}
                          {copiedId === r.id ? '복사됨' : '복사'}
                        </button>
                        <button
                          type="button"
                          className={`result-action${r.feedback === 'useful' ? ' active' : ''}`}
                          onClick={() => saveFeedback(r.id, true)}
                        >
                          <ThumbsUp size={13} /> 도움됨
                        </button>
                        <button
                          type="button"
                          className={`result-action${r.feedback === 'not_useful' ? ' active' : ''}`}
                          onClick={() => saveFeedback(r.id, false)}
                        >
                          <ThumbsDown size={13} /> 아쉬움
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <HistoryStrip refreshKey={analysisId} onSelect={loadHistory} />
        </div>
      </div>
    </div>
  );
}
