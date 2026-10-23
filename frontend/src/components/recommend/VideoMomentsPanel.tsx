import { Captions, ChevronDown, ExternalLink, LoaderCircle } from 'lucide-react';
import { useState } from 'react';
import { getVideoCaptionMoments } from '../../api/client';
import type { VideoCaptionMomentsResponse } from '../../types/comment';
import '../../styles/video-moments.css';

function timecode(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

/** Read-only, captions-only first step in grounded video understanding. */
export function VideoMomentsPanel({ url }: { url: string }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<VideoCaptionMomentsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggle = async () => {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (data || loading) return;
    setLoading(true);
    try {
      setData(await getVideoCaptionMoments(url));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '자막 타임라인 조회에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="video-moments">
      <button type="button" className="video-moments-trigger" aria-expanded={open} onClick={() => void toggle()}>
        <Captions size={16} />
        <span>영상 자막 타임라인</span>
        <small>화면 분석 전 단계 · 자막 구간만 표시</small>
        <ChevronDown size={15} className={open ? 'is-open' : ''} />
      </button>
      {open && (
        <div className="video-moments-body">
          {loading && <p><LoaderCircle size={14} className="spin" /> 자막 구간 확인 중...</p>}
          {error && <p role="alert">{error} <button type="button" className="video-moments-retry"
            onClick={() => { setOpen(false); setError(null); }}>닫고 다시 시도</button></p>}
          {data && (
            <>
              <p className="video-moments-warning">{data.warning}</p>
              {!data.moments.length && <p>확인 가능한 시간대별 자막이 없습니다.</p>}
              {data.moments.map((moment) => (
                <div className="video-moments-line" key={moment.start_seconds}>
                  <a href={`https://www.youtube.com/watch?v=${data.video_id}&t=${moment.start_seconds}s`}
                    target="_blank" rel="noopener noreferrer" title="해당 시간의 YouTube 영상으로 이동">
                    {timecode(moment.start_seconds)} <ExternalLink size={11} />
                  </a>
                  <p>{moment.text}</p>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </section>
  );
}
