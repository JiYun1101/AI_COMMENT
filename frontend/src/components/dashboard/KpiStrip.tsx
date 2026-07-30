interface KpiProps {
  label: string;
  value: string;
  delta?: string;
  deltaDir?: 'up' | 'down';
  sub: string;
}

function Kpi({ label, value, delta, deltaDir, sub }: KpiProps) {
  return (
    <div className="kpi">
      <div className="kpi-k">{label}</div>
      <div className="kpi-v">
        {value}
        {delta && (
          <span className={`kpi-delta ${deltaDir}`}>
            {deltaDir === 'up' ? '▲' : '▼'} {delta}
          </span>
        )}
      </div>
      <div className="kpi-sub">{sub}</div>
    </div>
  );
}

export function KpiStrip() {
  return (
    <div className="kpi-strip">
      <Kpi label="총 생성 댓글" value="128,402" delta="12.4%" deltaDir="up" sub="지난 7일 대비" />
      <Kpi label="활성 브랜드" value="37" delta="2" deltaDir="up" sub="이번 주 신규 3개 등록" />
      <Kpi label="이번 달 크레딧" value="80,041" delta="4.2%" deltaDir="up" sub="한도의 80% 사용" />
      <Kpi label="안전 필터 차단" value="1,204" delta="3.1%" deltaDir="down" sub="차단율 0.94%" />
    </div>
  );
}
