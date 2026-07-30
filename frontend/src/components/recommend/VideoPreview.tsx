import { Play, X } from 'lucide-react';
import type { VideoPreviewData } from '../../types/comment';

interface VideoPreviewProps {
  data: VideoPreviewData;
  onClear: () => void;
}

export function VideoPreview({ data, onClear }: VideoPreviewProps) {
  return (
    <div className="video-preview">
      <div className="vp-thumb">
        <span className="play">
          <Play size={12} fill="currentColor" />
        </span>
        <span className="dur">{data.duration}</span>
      </div>
      <div className="vp-body">
        <div className="vp-title">{data.title}</div>
        <div className="vp-channel">
          <span className="ch-avatar" />
          {data.channel} · 구독자 {data.subs}
        </div>
        <div className="vp-meta">
          조회수 {data.views} · {data.age}
        </div>
      </div>
      <button type="button" className="vp-clear" onClick={onClear} title="지우기">
        <X size={14} strokeWidth={2} />
      </button>
    </div>
  );
}
