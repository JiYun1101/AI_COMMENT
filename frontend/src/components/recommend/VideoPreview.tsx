import { Captions, ExternalLink, Play, Tags, X } from 'lucide-react';
import type { TranscriptStatus, VideoPreviewData } from '../../types/comment';

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

function resolvedTranscriptStatus(data: VideoPreviewData): TranscriptStatus {
  if (data.transcript_available) return 'available';
  return data.transcript_status ?? 'unavailable';
}

function transcriptLabel(data: VideoPreviewData): string {
  const status = resolvedTranscriptStatus(data);
  if (status === 'available') {
    return `공개 자막 반영${data.transcript_language ? ` · ${data.transcript_language}` : ''}`;
  }
  if (status === 'fetch_failed') return '자막 조회 실패 · 제목/설명으로 분석';
  return '공개 자막 없음 · 제목/설명으로 분석';
}

export function VideoPreview({ data, onClear }: VideoPreviewProps) {
  const transcriptStatus = resolvedTranscriptStatus(data);

  return (
    <div className="video-preview">
      <a
        className="vp-thumb"
        href={data.url}
        target="_blank"
        rel="noreferrer"
        title="YouTube에서 영상 열기"
        style={data.thumbnail_url ? { backgroundImage: `url(${data.thumbnail_url})`, backgroundPosition: 'center', backgroundSize: 'cover' } : undefined}
      >
        <span className="play"><Play size={12} fill="currentColor" /></span>
        <span className="dur">{formatDuration(data.duration_seconds)}</span>
      </a>
      <div className="vp-body">
        <div className="vp-title">{data.title}</div>
        <div className="vp-channel"><span className="ch-avatar" />{data.channel} · 구독자 {formatCount(data.subscriber_count)}</div>
        <div className="vp-meta">조회수 {formatCount(data.view_count)} · {formatPublishedAt(data.published_at)}</div>
        <div className="vp-context-row">
          {data.category_name && <span className="transcript-badge on"><Tags size={12} /> {data.category_name}</span>}
          <span className={`transcript-badge${transcriptStatus === 'available' ? ' on' : ''}`}>
            <Captions size={12} />
            {transcriptLabel(data)}
          </span>
          <a className="transcript-badge vp-open" href={data.url} target="_blank" rel="noreferrer">
            <ExternalLink size={11} /> 영상 열기
          </a>
        </div>
      </div>
      <button type="button" className="vp-clear" onClick={onClear} title="지우기">
        <X size={14} strokeWidth={2} />
      </button>
    </div>
  );
}
