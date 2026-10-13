import { ChevronRight, LoaderCircle, MessageSquare } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listAnalyses } from '../../api/client';
import { formatCategoryLabel } from '../../utils/category';
import type { AnalysisSummary } from '../../types/comment';

interface HistoryStripProps {
  refreshKey?: string | null;
  onSelect: (analysisId: string) => void;
}

function relativeTime(value: string): string {
  const date = new Date(value);
  const diff = Date.now() - date.getTime();
  if (Number.isNaN(diff)) return '';
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '방금 전';
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  return `${days}일 전`;
}

export function HistoryStrip({ refreshKey, onSelect }: HistoryStripProps) {
  const [items, setItems] = useState<AnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listAnalyses(3)
      .then((nextItems) => {
        if (cancelled) return;
        setItems(nextItems);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : '최근 분석 기록을 불러오지 못했습니다.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey, reloadToken]);

  return (
    <section>
      <div className="section-h">
        <div>
          <h2>최근 분석</h2>
          <div className="sub" style={{ marginTop: 3 }}>실제 저장된 최근 3건</div>
        </div>
        <Link to="/dashboard">대시보드에서 보기 <ChevronRight size={12} strokeWidth={2} /></Link>
      </div>

      {loading && <div className="history-empty"><LoaderCircle size={16} className="spin" /> 최근 기록을 불러오는 중…</div>}
      {!loading && error && <div className="history-empty error" role="alert">{error} <button type="button" className="btn secondary sm" onClick={() => setReloadToken((value) => value + 1)}>다시 시도</button></div>}
      {!loading && !error && items.length === 0 && (
        <div className="history-empty">아직 저장된 분석이 없습니다. 첫 추천을 생성하면 여기에 자동으로 기록됩니다.</div>
      )}
      {!loading && !error && items.length > 0 && (
        <div className="history">
          {items.map((item) => (
            <button key={item.id} type="button" className="hist-card" onClick={() => onSelect(item.id)}>
              <div
                className="hist-thumb"
                style={item.thumbnail_url ? { backgroundImage: `url(${item.thumbnail_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : undefined}
              >
                <span className="badge">{formatCategoryLabel(item.category)}</span>
              </div>
              <div className="hist-body">
                <div className="hist-title">{item.video_title || item.source_text}</div>
                <div className="hist-meta">
                  <span className="count"><MessageSquare size={11} strokeWidth={2} /> 추천 {item.recommendation_count}개</span>
                  <span className="time">{relativeTime(item.created_at)}</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
