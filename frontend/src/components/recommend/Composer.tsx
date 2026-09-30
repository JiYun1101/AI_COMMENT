import {
  AlertCircle,
  Clipboard,
  Info,
  Link2,
  LoaderCircle,
  Menu,
  RefreshCw,
  Shield,
  Sparkles,
  Star,
} from 'lucide-react';
import { VideoPreview } from './VideoPreview';
import { isRecommendationInputReady } from '../../utils/recommendationInput';
import type { VideoPreviewData } from '../../types/comment';

type Mode = 'url' | 'manual';

interface ComposerProps {
  mode: Mode;
  setMode: (mode: Mode) => void;
  url: string;
  setUrl: (url: string) => void;
  urlValid: boolean;
  manual: string;
  setManual: (manual: string) => void;
  additionalContext: string;
  setAdditionalContext: (value: string) => void;
  count: number;
  setCount: (count: number) => void;
  preview: VideoPreviewData | null;
  previewLoading: boolean;
  previewError: string | null;
  readinessMessage: string | null;
  readinessChecking?: boolean;
  onRetryPreview: () => void;
  onSwitchToManual: () => void;
  onClearPreview: () => void;
  onSubmit: () => void;
  submitting?: boolean;
}

export function Composer({
  mode,
  setMode,
  url,
  setUrl,
  urlValid,
  manual,
  setManual,
  additionalContext,
  setAdditionalContext,
  count,
  setCount,
  preview,
  previewLoading,
  previewError,
  readinessMessage,
  readinessChecking,
  onRetryPreview,
  onSwitchToManual,
  onClearPreview,
  onSubmit,
  submitting,
}: ComposerProps) {
  const inputReady = isRecommendationInputReady({
    mode,
    urlValid,
    manualLength: manual.trim().length,
    previewReady: Boolean(preview),
    previewLoading,
  });
  const canSubmit = inputReady && !readinessMessage && !readinessChecking;

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) setUrl(text);
    } catch {
      // Clipboard permissions are optional; manual paste remains available.
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
            <div className={`url-row${url && !urlValid ? ' invalid' : ''}`}>
              <svg className="lead" viewBox="0 0 24 24" fill="none" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
                <path d="M23 7l-7 5 7 5V7z" />
                <rect x="1" y="5" width="15" height="14" rx="2" />
              </svg>
              <input placeholder="https://youtube.com/watch?v=..." value={url} onChange={(e) => setUrl(e.target.value)} />
              {!url && (
                <button type="button" className="paste-btn" onClick={handlePaste}>
                  <Clipboard size={12} strokeWidth={2} /> 붙여넣기
                </button>
              )}
            </div>
            <div className="url-hint">
              <Info size={12} strokeWidth={1.75} />
              단일 영상 지원: <code>watch?v=</code> · <code>youtu.be</code> · <code>shorts</code> · <code>live</code>
            </div>
            {url && !urlValid && (
              <div className="inline-status error">
                <AlertCircle size={14} /> 지원되는 단일 YouTube 영상 URL을 입력해주세요. 재생목록은 현재 지원하지 않습니다.
              </div>
            )}
            {previewLoading && (
              <div className="preview-loading">
                <LoaderCircle size={16} className="spin" /> 영상 정보와 공개 자막을 확인하고 있습니다…
              </div>
            )}
            {previewError && !previewLoading && (
              <div className="preview-error">
                <div><AlertCircle size={15} /> {previewError}</div>
                <div className="preview-error-actions">
                  <button type="button" className="btn secondary sm" onClick={onRetryPreview}>
                    <RefreshCw size={12} /> 다시 시도
                  </button>
                  <button type="button" className="btn ghost sm" onClick={onSwitchToManual}>직접 입력으로 계속</button>
                </div>
              </div>
            )}
            {preview && !previewLoading && <VideoPreview data={preview} onClear={onClearPreview} />}
          </>
        ) : (
          <>
            <textarea
              className="manual-area"
              placeholder={'영상 제목 또는 스크립트를 붙여넣으세요.\n\n예) AI 시대에 개발자는 어떻게 살아남아야 할까? 이번 영상에서는 실무자 3인과 함께 앞으로의 커리어 전략을 이야기합니다.'}
              value={manual}
              onChange={(e) => setManual(e.target.value)}
              maxLength={10000}
            />
            <div className="manual-meta">
              <span>5자 이상이면 추천할 수 있습니다.</span>
              <span>{manual.length} / 10,000</span>
            </div>
          </>
        )}

        <div className="composer-extra">
          <label htmlFor="additional-context">추가 맥락 <span>선택</span></label>
          <textarea
            id="additional-context"
            value={additionalContext}
            onChange={(e) => setAdditionalContext(e.target.value)}
            maxLength={4000}
            placeholder="기본 내용에 없는 관점, 댓글 대상, 꼭 반영할 내용을 적어주세요."
          />
          <small>{additionalContext.length} / 4,000</small>
        </div>

        <div className="options">
          <div className="opt-row context-auto-row">
            <label className="opt-label">맥락 분석</label>
            <div className="context-auto-note">
              <Sparkles size={13} /> YouTube 공식 카테고리·주제·형식·최신성·반응 지표와 기존 댓글 패턴을 자동 분석합니다.
            </div>
          </div>

          <div className="opt-row">
            <label className="opt-label">추천 개수</label>
            <div className="slider-row">
              <input type="range" min={3} max={10} value={count} onChange={(e) => setCount(Number(e.target.value))} className="slider" />
              <span className="slider-value"><b>{count}</b><span>&nbsp;/ 10</span></span>
            </div>
          </div>
        </div>

        {readinessChecking && (
          <div className="inline-status">
            <LoaderCircle size={14} className="spin" /> 추천 서비스 준비 상태를 확인하고 있습니다…
          </div>
        )}
        {!readinessChecking && readinessMessage && (
          <div className="inline-status error">
            <AlertCircle size={14} /> {readinessMessage}
          </div>
        )}
      </div>

      <div className="composer-ft">
        <span className="safety"><Shield size={12} strokeWidth={2} /> 안전 필터 항상 적용</span>
        <button type="button" className="cta" disabled={!canSubmit || submitting} onClick={onSubmit}>
          <Star size={16} strokeWidth={2} />
          {submitting ? 'LLM 댓글 생성 중…' : '댓글 추천받기'}
        </button>
      </div>
    </div>
  );
}
