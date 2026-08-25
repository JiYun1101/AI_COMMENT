import type { DashboardSummary } from '../../types/comment';

interface KpiProps {
  label: string;
  value: string;
  sub: string;
}

function Kpi({ label, value, sub }: KpiProps) {
  return (
    <div className="kpi">
      <div className="kpi-k">{label}</div>
      <div className="kpi-v">{value}</div>
      <div className="kpi-sub">{sub}</div>
    </div>
  );
}

export function KpiStrip({ summary, loading }: { summary: DashboardSummary | null; loading?: boolean }) {
  const value = (input: string) => (loading ? '…' : input);
  return (
    <div className="kpi-strip">
      <Kpi label="분석 횟수" value={value(String(summary?.analysis_count ?? 0))} sub="저장된 실제 분석" />
      <Kpi label="추천 댓글" value={value(String(summary?.recommendation_count ?? 0))} sub="누적 생성 결과" />
      <Kpi label="평균 예상 점수" value={value(`${(summary?.average_score ?? 0).toFixed(1)}%`)} sub="저장된 추천 평균" />
      <Kpi
        label="도움됨 피드백"
        value={value(summary?.helpful_rate == null ? '—' : `${summary.helpful_rate.toFixed(1)}%`)}
        sub={summary?.feedback_count ? `피드백 ${summary.feedback_count}건 기준` : '아직 피드백 없음'}
      />
    </div>
  );
}
