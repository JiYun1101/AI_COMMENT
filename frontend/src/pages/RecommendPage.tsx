import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import { Header } from '../components/layout/Header';
import { Composer } from '../components/recommend/Composer';
import { EmptyExamples, type ExampleVideo } from '../components/recommend/EmptyExamples';
import { HistoryStrip } from '../components/recommend/HistoryStrip';
import { TypeTag } from '../components/TypeTag';
import { getVideoPreview, recommend } from '../api/client';
import type { Category, CommentRecommendation, VideoPreviewData } from '../types/comment';

type Mode = 'url' | 'manual';

const YOUTUBE_URL_RE = /(?:youtube\.com\/(?:watch|shorts|embed|live)|youtu\.be\/)/i;

export function RecommendPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>('url');
  const [url, setUrl] = useState('');
  const [manual, setManual] = useState('');
  const [category, setCategory] = useState<Category>('auto');
  const [count, setCount] = useState(5);
  const [preview, setPreview] = useState<VideoPreviewData | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [results, setResults] = useState<CommentRecommendation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isEmpty = mode === 'url' ? !url.trim() : !manual.trim();

  const looksLikeYoutubeUrl = useMemo(() => {
    const trimmed = url.trim();
    return mode === 'url' && !!trimmed && YOUTUBE_URL_RE.test(trimmed);
  }, [mode, url]);

  useEffect(() => {
    if (!looksLikeYoutubeUrl) {
      setPreview(null);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(() => {
      getVideoPreview(url.trim())
        .then((nextPreview) => {
          if (cancelled) return;
          setPreview(nextPreview);
          setError(null);
        })
        .catch((err) => {
          if (cancelled) return;
          setPreview(null);
          setError(err instanceof Error ? err.message : '영상 정보를 불러오지 못했습니다.');
        });
    }, 500);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [looksLikeYoutubeUrl, url]);

  const applyUrl = (nextUrl: string) => {
    setUrl(nextUrl);
    setPreview(null);
    setError(null);
  };

  const clearPreview = () => {
    setUrl('');
    setPreview(null);
    setError(null);
  };

  const pickExample = (example: ExampleVideo) => {
    setMode('manual');
    setCategory(example.category);
    setManual(`${example.title}\n채널: ${example.channel}`);
    setUrl('');
    setPreview(null);
    setError(null);
  };

  const submit = async () => {
    const hasInput = mode === 'url' ? url.trim() : manual.trim();
    if (!hasInput) return;

    setSubmitting(true);
    setError(null);
    setResults(null);
    try {
      const response = await recommend(
        mode === 'url'
          ? { youtube_url: url.trim(), top_k: count }
          : { post_text: manual.trim(), top_k: count },
      );
      setResults(response.recommendations);
      if (response.youtube_context) setPreview(response.youtube_context);
    } catch (err) {
      setError(err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleNav = (key: SidebarKey) => {
    if (key === 'dashboard') navigate('/dashboard');
    // other nav targets have no route yet
  };

  return (
    <div className="app">
      <Sidebar current="comments" onNav={handleNav} />
      <div className="main">
        <Header title="댓글 추천" />
        <div className="recommend">
      <div className="hero">
        <span className="hero-eyebrow">
          <span className="dot" /> AI 댓글 추천 · v1
        </span>
        <h1 className="hero-title">
          영상에 어울리는
          <br />
          안전한 댓글을 찾아드립니다
        </h1>
        <p className="hero-sub">반응이 좋았던 댓글 패턴을 학습해, 자극적이지 않은 댓글만 추천합니다.</p>
      </div>

      <Composer
        mode={mode}
        setMode={setMode}
        url={url}
        setUrl={applyUrl}
        manual={manual}
        setManual={setManual}
        category={category}
        setCategory={setCategory}
        count={count}
        setCount={setCount}
        preview={mode === 'url' && looksLikeYoutubeUrl ? preview : null}
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
              <div className="sub" style={{ marginTop: 3 }}>
                {results.length}개 후보 · 안전 필터 통과
              </div>
            </div>
          </div>
          <div className="results">
            {results.map((r) => (
              <div className="result-card" key={r.rank}>
                <span className={`result-rank${r.rank === 1 ? ' top' : ''}`}>{r.rank}</span>
                <div className="result-body">
                  <div className="result-text">{r.comment}</div>
                  <div className="result-meta">
                    <TypeTag type={r.type} />
                    <span className="result-score">
                      예상 점수 {r.predicted_score.toFixed(1)}%
                      <span className="result-score-bar">
                        <span
                          className="result-score-fill"
                          style={{ width: `${Math.min(100, Math.max(0, r.predicted_score))}%` }}
                        />
                      </span>
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <HistoryStrip />
        </div>
      </div>
    </div>
  );
}
