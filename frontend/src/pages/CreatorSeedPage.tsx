import {
  Check,
  Copy,
  FileText,
  Link2,
  LoaderCircle,
  MessageSquare,
  Pin,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getHealth, recommend } from '../api/client';
import { Header } from '../components/layout/Header';
import { Sidebar, type SidebarKey } from '../components/layout/Sidebar';
import type { CommentRecommendation, ServiceHealth } from '../types/comment';
import { isValidYouTubeVideoUrl } from '../utils/youtube';

type Mode = 'url' | 'draft';

const CREATOR_CONTEXT = [
  '당신은 이 영상의 작성자 본인입니다.',
  '댓글 섹션의 대화를 자연스럽게 시작하기 위한 첫 댓글 또는 고정댓글 후보를 만들어주세요.',
  '시청자인 척하거나 제3자인 척하지 마세요.',
  '영상에서 못다 한 보충 정보, 비하인드, 선택형 질문, 다음 편 떡밥, 가벼운 참여 유도처럼 작성자만 할 수 있는 말을 우선하세요.',
  '과장된 낚시, 좋아요 구걸, 반복적인 홍보 문구는 피하세요.',
].join(' ');

function purposeLabel(item: CommentRecommendation): string {
  const text = item.comment;
  if (text.includes('?') || item.type === 'question') return '대화 유도';
  if (/(다음|다음 편|후속|이어|공개)/.test(text)) return '다음 콘텐츠 떡밥';
  if (/(추가|참고|설명|비하인드|촬영|영상에서)/.test(text)) return '보충 설명';
  if (/(감사|고마|봐주|응원)/.test(text)) return '감사·커뮤니티';
  return '첫 댓글';
}

export function CreatorSeedPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>('url');
  const [url, setUrl] = useState('');
  const [draft, setDraft] = useState('');
  const [health, setHealth] = useState<ServiceHealth | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<CommentRecommendation[] | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const urlValid = useMemo(() => isValidYouTubeVideoUrl(url), [url]);
  const llmReady = Boolean(health?.llm.ready);
  const youtubeReady = Boolean(health?.youtube.configured);
  const inputReady = mode === 'url' ? urlValid && youtubeReady : draft.trim().length >= 12;
  const setupMissing = Boolean(health && (!llmReady || (mode === 'url' && !youtubeReady)));

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then((next) => {
        if (cancelled) return;
        setHealth(next);
        setHealthError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setHealth(null);
        setHealthError(err instanceof Error ? err.message : '서비스 상태를 확인하지 못했습니다.');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const generate = async () => {
    if (!inputReady || !llmReady || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await recommend(
        mode === 'url'
          ? {
              youtube_url: url.trim(),
              additional_context: CREATOR_CONTEXT,
              top_k: 5,
            }
          : {
              post_text: draft.trim(),
              additional_context: CREATOR_CONTEXT,
              top_k: 5,
            },
      );
      setResults(response.recommendations);
    } catch (err) {
      setError(err instanceof Error ? err.message : '댓글 후보를 생성하지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const copy = async (item: CommentRecommendation) => {
    try {
      await navigator.clipboard.writeText(item.comment);
      setCopied(item.id);
      window.setTimeout(() => setCopied((current) => (current === item.id ? null : current)), 1400);
    } catch {
      setError('클립보드 권한이 없어 복사하지 못했습니다.');
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
      <Sidebar current="seed" onNav={handleNav} />
      <div className="main">
        <Header
          title="맛있는 댓글 미리 달기"
          subtitle="영상 작성자가 직접 남길 첫 댓글·고정댓글 후보를 업로드 전부터 준비합니다."
        />

        <main className="creator-seed-page">
          <section className="creator-seed-hero">
            <div>
              <span className="creator-seed-kicker"><Sparkles size={14} /> CREATOR FIRST COMMENT</span>
              <h2>댓글창 분위기를 여는<br />첫 한마디를 미리 준비하세요</h2>
              <p>
                시청자인 척하는 댓글이 아니라 작성자 본인의 첫 댓글을 만듭니다.
                영상 보충 설명, 비하인드, 질문, 다음 편 떡밥처럼 댓글창에서 대화를 이어가기 좋은 후보를 추천합니다.
              </p>
            </div>
            <div className="creator-seed-example">
              <Pin size={18} />
              <div>
                <strong>고정댓글로 쓰기 좋은 방식</strong>
                <span>“영상에서 못 다룬 부분 중 뭐가 가장 궁금했나요? 다음 편에서 더 풀어볼게요.”</span>
              </div>
            </div>
          </section>

          <section className="creator-seed-composer">
            <div className="creator-seed-tabs">
              <button
                type="button"
                className={mode === 'url' ? 'active' : ''}
                onClick={() => {
                  setMode('url');
                  setResults(null);
                  setError(null);
                }}
              >
                <Link2 size={14} /> 공개 영상 URL
              </button>
              <button
                type="button"
                className={mode === 'draft' ? 'active' : ''}
                onClick={() => {
                  setMode('draft');
                  setResults(null);
                  setError(null);
                }}
              >
                <FileText size={14} /> 업로드 전 초안
              </button>
            </div>

            {mode === 'url' ? (
              <div className="creator-seed-field">
                <label htmlFor="creator-video-url">YouTube 영상 URL</label>
                <input
                  id="creator-video-url"
                  type="url"
                  value={url}
                  placeholder="https://www.youtube.com/watch?v=..."
                  onChange={(event) => {
                    setUrl(event.target.value);
                    setResults(null);
                    setError(null);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') void generate();
                  }}
                />
                {url.trim() && !urlValid && <small className="creator-seed-error">올바른 YouTube 영상 URL을 입력해주세요.</small>}
              </div>
            ) : (
              <div className="creator-seed-field">
                <label htmlFor="creator-video-draft">영상 제목 · 설명 · 스크립트 초안</label>
                <textarea
                  id="creator-video-draft"
                  value={draft}
                  placeholder={"예) 제주도 3박 4일 혼자 여행 브이로그\n첫날에는 동문시장과 함덕을 갔고..."}
                  onChange={(event) => {
                    setDraft(event.target.value);
                    setResults(null);
                    setError(null);
                  }}
                />
                <span className="creator-seed-help">영상이 아직 공개되지 않았어도 제목과 핵심 내용만 있으면 사용할 수 있습니다.</span>
              </div>
            )}

            {setupMissing && (
              <div className="creator-seed-setup">
                API 연결이 필요합니다.
                <button type="button" onClick={() => navigate('/account/connect')}>내 계정 설정 열기</button>
              </div>
            )}
            {healthError && <div className="creator-seed-error">{healthError}</div>}
            {error && <div className="creator-seed-error">{error}</div>}

            <div className="creator-seed-actions">
              <span>작성자 관점 · 자연스러운 참여 유도 · 과장/낚시 제외</span>
              <button
                type="button"
                className="btn primary"
                onClick={() => void generate()}
                disabled={!inputReady || !llmReady || loading}
              >
                {loading ? <LoaderCircle size={14} className="spin" /> : <Sparkles size={14} />}
                {loading ? '만드는 중...' : '맛있는 댓글 만들기'}
              </button>
            </div>
          </section>

          {loading && (
            <section className="creator-seed-loading">
              <LoaderCircle size={22} className="spin" />
              <div>
                <strong>작성자용 첫 댓글을 만들고 있습니다</strong>
                <span>영상 맥락 → 작성자 관점 후보 생성 → Safety → Ranker</span>
              </div>
            </section>
          )}

          {results && (
            <section className="creator-seed-results">
              <div className="creator-seed-results-head">
                <div>
                  <span>FIRST COMMENT CANDIDATES</span>
                  <h3>작성자용 댓글 후보</h3>
                </div>
                <button type="button" className="btn secondary sm" onClick={() => void generate()} disabled={loading}>
                  <RefreshCw size={13} /> 새 후보
                </button>
              </div>

              <div className="creator-seed-grid">
                {results.map((item) => (
                  <article className="creator-seed-card" key={item.id}>
                    <div className="creator-seed-card-top">
                      <span className="creator-seed-purpose">{purposeLabel(item)}</span>
                      <span className="creator-seed-rank">#{item.rank}</span>
                    </div>
                    <p>{item.comment}</p>
                    <div className="creator-seed-card-footer">
                      <span>모델 점수 {item.predicted_score.toFixed(1)}</span>
                      <button type="button" onClick={() => void copy(item)}>
                        {copied === item.id ? <Check size={13} /> : <Copy size={13} />}
                        {copied === item.id ? '복사됨' : '복사'}
                      </button>
                    </div>
                  </article>
                ))}
              </div>

              <div className="creator-seed-note">
                <MessageSquare size={15} />
                <span>현재는 초안 생성까지 제공합니다. 실제 고정댓글 게시·예약은 다음 단계에서 YouTube OAuth와 연결할 수 있습니다.</span>
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
