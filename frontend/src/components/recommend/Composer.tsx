import { Link2, Menu, Clipboard, Info, Shield, Star } from 'lucide-react';
import { VideoPreview } from './VideoPreview';
import type { Category, VideoPreviewData } from '../../types/comment';

type Mode = 'url' | 'manual';

const CATEGORIES: { key: Category; label: string; auto?: boolean }[] = [
  { key: 'auto', label: '자동 감지', auto: true },
  { key: 'social', label: '사회이슈' },
  { key: 'vlog', label: '브이로그' },
];

interface ComposerProps {
  mode: Mode;
  setMode: (mode: Mode) => void;
  url: string;
  setUrl: (url: string) => void;
  manual: string;
  setManual: (manual: string) => void;
  category: Category;
  setCategory: (category: Category) => void;
  count: number;
  setCount: (count: number) => void;
  preview: VideoPreviewData | null;
  onClearPreview: () => void;
  onSubmit: () => void;
  submitting?: boolean;
}

export function Composer({
  mode,
  setMode,
  url,
  setUrl,
  manual,
  setManual,
  category,
  setCategory,
  count,
  setCount,
  preview,
  onClearPreview,
  onSubmit,
  submitting,
}: ComposerProps) {
  const canSubmit = mode === 'url' ? url.trim().length > 0 : manual.trim().length >= 5;

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) setUrl(text);
    } catch {
      // clipboard permission denied — no-op, user can type/paste manually
    }
  };

  return (
    <div className="composer">
      <div className="tabs" role="tablist">
        <button type="button" className={`tab${mode === 'url' ? ' active' : ''}`} onClick={() => setMode('url')}>
          <Link2 size={14} strokeWidth={1.75} />
          유튜브 URL
        </button>
        <button type="button" className={`tab${mode === 'manual' ? ' active' : ''}`} onClick={() => setMode('manual')}>
          <Menu size={14} strokeWidth={1.75} />
          직접 입력
        </button>
      </div>

      <div className="tab-body">
        {mode === 'url' ? (
          <>
            <div className="url-row">
              <svg className="lead" viewBox="0 0 24 24" fill="none" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
                <path d="M23 7l-7 5 7 5V7z" />
                <rect x="1" y="5" width="15" height="14" rx="2" />
              </svg>
              <input placeholder="https://youtube.com/watch?v=..." value={url} onChange={(e) => setUrl(e.target.value)} />
              {!url && (
                <button type="button" className="paste-btn" onClick={handlePaste}>
                  <Clipboard size={12} strokeWidth={2} />
                  붙여넣기
                </button>
              )}
            </div>
            <div className="url-hint">
              <Info size={12} strokeWidth={1.75} />
              지원 형식: <code>youtube.com/watch</code> · <code>youtu.be</code> · 재생목록 URL
            </div>
            {preview && <VideoPreview data={preview} onClear={onClearPreview} />}
          </>
        ) : (
          <>
            <textarea
              className="manual-area"
              placeholder={
                '영상 제목 또는 스크립트를 붙여넣으세요.\n\n예) AI 시대에 개발자는 어떻게 살아남아야 할까? 이번 영상에서는 실무자 3인과 함께 앞으로의 커리어 전략을 이야기합니다.'
              }
              value={manual}
              onChange={(e) => setManual(e.target.value)}
              maxLength={2000}
            />
            <div className="manual-meta">
              <span>제목만 입력해도 추천이 가능합니다.</span>
              <span>{manual.length} / 2,000</span>
            </div>
          </>
        )}

        <div className="options">
          <div className="opt-row">
            <label className="opt-label">카테고리</label>
            <div className="opt-chips">
              {CATEGORIES.map((c) => (
                <button
                  key={c.key}
                  type="button"
                  className={`opt-chip${c.auto ? ' auto' : ''}${category === c.key ? ' on' : ''}`}
                  onClick={() => setCategory(c.key)}
                >
                  {c.auto && <Star size={12} />}
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          <div className="opt-row">
            <label className="opt-label">추천 개수</label>
            <div className="slider-row">
              <input
                type="range"
                min={3}
                max={10}
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="slider"
              />
              <span className="slider-value">
                <b>{count}</b>
                <span>&nbsp;/ 10</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="composer-ft">
        <span className="cost">
          예상 크레딧 <b>{count * 20}</b>
        </span>
        <span className="safety">
          <Shield size={12} strokeWidth={2} />
          안전 필터 켜짐
        </span>
        <button type="button" className="cta" disabled={!canSubmit || submitting} onClick={onSubmit}>
          <Star size={16} strokeWidth={2} />
          {submitting ? '추천 생성 중…' : '댓글 추천받기'}
        </button>
      </div>
    </div>
  );
}
