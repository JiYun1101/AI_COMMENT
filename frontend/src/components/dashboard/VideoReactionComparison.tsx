import { BarChart3, Check, Eye, Heart, MessageCircle } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { OwnedVideoMetric } from '../../types/comment';

type Mode = 'rate' | 'reactions' | 'views';
const MODES: { id: Mode; label: string }[] = [
  { id: 'rate', label: '참여율' },
  { id: 'reactions', label: '총 반응 수' },
  { id: 'views', label: '조회수' },
];

const format = (value: number | null) => value == null ? '—' : value.toLocaleString('ko-KR');
const reactions = (video: OwnedVideoMetric) =>
  video.likes == null || video.comments == null ? null : video.likes + video.comments;
const rate = (video: OwnedVideoMetric) => {
  const count = reactions(video);
  return count == null || video.views == null || video.views <= 0 ? null : 100 * count / video.views;
};
const metric = (video: OwnedVideoMetric, mode: Mode) =>
  mode === 'views' ? video.views : mode === 'reactions' ? reactions(video) : rate(video);
const display = (value: number | null, mode: Mode) =>
  value == null ? '미측정' : mode === 'rate' ? value.toFixed(2) + '%' : format(value);

export function VideoReactionComparison({ videos }: { videos: OwnedVideoMetric[] }) {
  const [mode, setMode] = useState<Mode>('rate');
  const [showAll, setShowAll] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const ranked = useMemo(() => [...videos].sort((first, second) => {
    const a = metric(first, mode);
    const b = metric(second, mode);
    if (a == null && b == null) return first.title.localeCompare(second.title, 'ko');
    if (a == null) return 1;
    if (b == null) return -1;
    return b - a || first.title.localeCompare(second.title, 'ko');
  }), [videos, mode]);
  const top = showAll ? ranked : ranked.slice(0, 8);
  const max = Math.max(0, ...top.map((video) => metric(video, mode) ?? 0));
  const compared = selected.map((id) => videos.find((video) => video.video_id === id)).filter((v): v is OwnedVideoMetric => Boolean(v));

  const toggle = (id: string) => setSelected((current) =>
    current.includes(id) ? current.filter((item) => item !== id) : current.length >= 3 ? current : [...current, id]);

  return (
    <section className="eng-panel video-compare" aria-label="영상별 반응 비교">
      <div className="eng-panel-head">
        <h3><BarChart3 size={17} /> 영상별 반응 비교</h3>
        <small>실제 조회수·좋아요·댓글 수로 비교합니다. 지표를 바꾸면 상위 영상 순위도 바뀝니다.</small>
      </div>
      <div className="video-compare-tabs" role="group" aria-label="영상 비교 지표">
        {MODES.map((item) => (
          <button type="button" key={item.id} className={mode === item.id ? 'active' : ''}
            aria-pressed={mode === item.id} onClick={() => setMode(item.id)}>{item.label}</button>
        ))}
      </div>
      <div className="video-compare-list">
        {top.map((video, index) => {
          const value = metric(video, mode);
          const isSelected = selected.includes(video.video_id);
          return (
            <button type="button" className={'video-compare-row' + (isSelected ? ' selected' : '')}
              key={video.video_id} onClick={() => toggle(video.video_id)} aria-pressed={isSelected}
              title={isSelected ? '비교에서 제거' : selected.length >= 3 ? '최대 3개 영상까지 선택할 수 있습니다' : '클릭해 비교에 추가'}>
              <span className="video-compare-rank">{index + 1}</span>
              <span className="video-compare-name" title={video.title}>{video.title}</span>
              <span className="video-compare-meter"><span style={{ width: (value == null || max <= 0 ? 0 : Math.max(0, 100 * value / max)).toFixed(1) + '%' }} /></span>
              <strong>{display(value, mode)}</strong>
              <span className="video-compare-check">{isSelected ? <Check size={14} /> : '+'}</span>
            </button>
          );
        })}
      </div>
      {ranked.length > 8 && (
        <button type="button" className="btn secondary sm" onClick={() => setShowAll((current) => !current)}>
          {showAll ? '상위 8개만 보기' : '전체 ' + ranked.length + '개 영상 보기'}
        </button>
      )}
      <p className="eng-note">참여율 = (좋아요 + 댓글) ÷ 조회수 × 100. 플랫폼 공식 참여율이나 서로 다른 고유 시청자의 반응 확률이 아닙니다. 좋아요·댓글이 비공개이거나 조회수가 0이면 미측정으로 표시합니다.</p>
      <div className="video-compare-selection">
        <div className="model-subhead"><strong>선택한 영상 상세 비교</strong><small>{selected.length}/3 선택 · 위의 영상 행을 클릭</small></div>
        {compared.length === 0 ? (
          <p className="eng-note">비교하고 싶은 영상을 최대 3개 선택해 보세요. 조회수 규모와 반응률의 차이를 함께 확인할 수 있습니다.</p>
        ) : (
          <div className="video-compare-cards">
            {compared.map((video) => (
              <div key={video.video_id} className="video-compare-card">
                <div className="video-compare-card-top">
                  <strong title={video.title}>{video.title}</strong>
                  <button type="button" onClick={() => toggle(video.video_id)} aria-label={video.title + ' 비교에서 제거'}>×</button>
                </div>
                <div className="video-compare-card-rate">{rate(video) == null ? '—' : rate(video)?.toFixed(2) + '%'}<small>조회 대비 참여율</small></div>
                <div className="video-compare-card-stats">
                  <span><Eye size={14} /> {format(video.views)}</span>
                  <span><Heart size={14} /> {format(video.likes)}</span>
                  <span><MessageCircle size={14} /> {format(video.comments)}</span>
                </div>
                {video.local_only && <small className="eng-note">브라우저에 남은 과거 측정값</small>}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
