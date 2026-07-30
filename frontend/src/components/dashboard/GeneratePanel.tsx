import { useState } from 'react';
import { Video, X, PlayCircle } from 'lucide-react';

const TONES = [
  { key: 'empathy', label: '공감형', desc: '따뜻하게 리액션' },
  { key: 'insight', label: '인사이트', desc: '관점을 더한다' },
  { key: 'question', label: '질문형', desc: '대화를 유도' },
  { key: 'casual', label: '캐주얼', desc: '자연스러운 구어체' },
] as const;

interface GeneratePanelProps {
  open: boolean;
  onClose: () => void;
}

// Tone selection is UI-only for now — src/api/schemas.py::RecommendRequest has no
// `tone` field yet, only `post_text` and `top_k`. Wire this up once the backend
// supports steering comment type.
export function GeneratePanel({ open, onClose }: GeneratePanelProps) {
  const [url, setUrl] = useState('https://youtube.com/watch?v=dQw4w9WgXcQ');
  const [tone, setTone] = useState<(typeof TONES)[number]['key']>('insight');
  const [count, setCount] = useState(5);

  if (!open) return null;

  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <aside className="drawer">
        <div className="drawer-hd">
          <div>
            <div className="drawer-eyebrow">NEW</div>
            <h2 className="drawer-title">댓글 생성</h2>
          </div>
          <button type="button" className="icon-btn" onClick={onClose}>
            <X size={18} strokeWidth={2} />
          </button>
        </div>

        <div className="drawer-body">
          <div className="fld">
            <label>유튜브 URL</label>
            <div className="input">
              <Video size={15} strokeWidth={2} />
              <input value={url} onChange={(e) => setUrl(e.target.value)} />
            </div>
            <p className="fld-help">단일 영상 URL 또는 재생목록 URL 지원.</p>
          </div>

          <div className="fld">
            <label>브랜드</label>
            <div className="input">
              <span>그린티코스메틱</span>
            </div>
          </div>

          <div className="fld">
            <label>톤앤매너</label>
            <div className="tone-grid">
              {TONES.map((t) => (
                <div key={t.key} className={`tone-card${tone === t.key ? ' on' : ''}`} onClick={() => setTone(t.key)}>
                  <div className="tone-lbl">{t.label}</div>
                  <div className="tone-desc">{t.desc}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="fld">
            <label>
              생성 개수 <span className="fld-value">{count}</span>
            </label>
            <input type="range" min={1} max={10} value={count} onChange={(e) => setCount(Number(e.target.value))} className="range" />
          </div>

          <div className="fld">
            <label>
              <span className="toggle" style={{ marginRight: 8 }} />
              안전 필터 사용
            </label>
            <p className="fld-help">욕설·비방·혐오 표현이 감지되면 자동 제거됩니다.</p>
          </div>
        </div>

        <div className="drawer-ft">
          <span className="ft-cost">
            예상 크레딧 <b>{count * 20}</b>
          </span>
          <button type="button" className="btn ghost" onClick={onClose}>
            취소
          </button>
          <button type="button" className="btn primary">
            <PlayCircle size={14} strokeWidth={2} />
            생성 시작
          </button>
        </div>
      </aside>
    </>
  );
}
