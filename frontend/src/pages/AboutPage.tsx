import { ArrowRight, ImagePlus, MessageCircleMore, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export function AboutPage() {
  const navigate = useNavigate();

  return (
    <main className="about-page">
      <header className="about-topbar">
        <button type="button" className="about-brand" onClick={() => navigate('/about')}>
          <span className="about-brand-mark">
            <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 6h11a4 4 0 010 8H8l-4 4V6z" />
              <circle cx="18" cy="6" r="2.5" fill="currentColor" stroke="none" />
            </svg>
          </span>
          <span>AI<em>_</em>COMMENT</span>
        </button>

        <button type="button" className="about-enter" onClick={() => navigate('/')}>
          서비스 이용하기 <ArrowRight size={14} />
        </button>
      </header>

      <section className="about-shell">
        <div className="about-visual-placeholder">
          <div className="about-placeholder-grid" aria-hidden="true" />
          <div className="about-placeholder-label">
            <span><ImagePlus size={20} /></span>
            <strong>메인 이미지 영역</strong>
            <small>서비스 대표 이미지 · 썸네일 · 일러스트를 넣을 수 있습니다.</small>
          </div>

          <div className="about-comment-chip chip-one">
            <MessageCircleMore size={14} />
            <span>이 장면 진짜 좋다</span>
          </div>
          <div className="about-comment-chip chip-two">
            <Sparkles size={14} />
            <span>다음 편도 궁금해요</span>
          </div>
          <div className="about-comment-chip chip-three">
            <span>🔥</span>
            <span>댓글까지 맛있다</span>
          </div>
        </div>

        <section className="about-message">
          <span className="about-eyebrow">CONTENT IS ONLY HALF THE STORY</span>
          <h1>
            당신의 계정에 필요한건 더이상 잘 만든 컨텐츠가 아니에요.<br />
            <strong>맛있는 댓글로 장식할 시간입니다!</strong>
          </h1>
          <p>
            영상에 어울리는 댓글을 만들고, 시청자 반응을 미리 보고,
            작성자의 첫 댓글까지 준비하는 AI 댓글 워크스페이스입니다.
          </p>

          <div className="about-actions">
            <button type="button" className="about-primary" onClick={() => navigate('/')}>
              댓글 추천 시작하기 <ArrowRight size={15} />
            </button>
            <button type="button" className="about-secondary" onClick={() => navigate('/reaction-preview')}>
              영상 반응 미리보기
            </button>
          </div>
        </section>

        <section className="about-feature-strip">
          <article>
            <span>01</span>
            <strong>댓글 추천</strong>
            <p>영상 맥락과 페르소나에 맞춰 자연스러운 댓글 후보를 만듭니다.</p>
          </article>
          <article>
            <span>02</span>
            <strong>반응 미리보기</strong>
            <p>질문·칭찬·혼란·불만 등 예상 시청자 반응을 미리 확인합니다.</p>
          </article>
          <article>
            <span>03</span>
            <strong>작성자 첫 댓글</strong>
            <p>고정댓글, 보충 설명, 대화 유도용 첫 댓글을 업로드 전부터 준비합니다.</p>
          </article>
        </section>
      </section>
    </main>
  );
}
