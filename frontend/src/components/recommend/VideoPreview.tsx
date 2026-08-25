import { Captions, Play, X } from 'lucide-react';
import type { VideoPreviewData } from '../../types/comment';

interface VideoPreviewProps {
  data: VideoPreviewData;
  onClear: () => void;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '--:--';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
    : `${minutes}:${String(rest).padStart(2, '0')}`;
}

function formatCount(value: number | null): string {
  if (value === null) return '정보 없음';
  return new Intl.NumberFormat('ko-KR', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

function formatPublishedAt(value: string | null): string {
  if (!value) return '게시일 정보 없음';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '게시일 정보 없음';
  return new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: 'numeric', day: 'numeric' }).format(date);
}

export function VideoPreview({ data, onClear }: VideoPreviewProps) {
  return (
    <div className="video-preview">
      <div
        className="vp-thumb"
        style={data.thumbnail_url ? { backgroundImage: `url(${data.thumbnail_url})`, backgroundPosition: 'center', backgroundSize: 'cover' } : undefined}
      >
        <span className="play"><Play size={12} fill="currentColor" /></span>
        <span className="dur">{formatDuration(data.duration_seconds)}</span>
      </div>
      <div className="vp-body">
        <div className="vp-title">{data.title}</div>
        <div className="vp-channel"><span className="ch-avatar" />{data.channel} · 구독자 {formatCount(data.subscriber_count)}</div>
        <div className="vp-meta">조회수 {formatCount(data.view_count)} · {formatPublishedAt(data.published_at)}</div>
        <div className={`transcript-badge${data.transcript_available ? ' on' : ''}`}>
          <Captions size={12} />
          {data.transcript_available
            ? `공개 자막 반영${data.transcript_language ? ` · ${data.transcript_language}` : ''}`
            : '공개 자막 없음 · 제목/설명으로 추천'}
        </div>
      </div>
      <button type="button" className="vp-clear" onClick={onClear} title="지우기">
        <X size={14} strokeWidth={2} />
      </button>
    </div>
  );
}
