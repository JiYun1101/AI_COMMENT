import { CheckCircle2, ChevronDown, CircleMinus, ShieldX, Trophy } from 'lucide-react';
import { TypeTag } from '../TypeTag';
import type { RecommendationTrace } from '../../types/comment';

const SAFETY_REASON_LABEL: Record<string, string> = {
  empty: '빈 댓글',
  too_short: '너무 짧음',
  too_long: '너무 김',
  profanity: '욕설/비속어',
  hate_speech: '혐오/차별 표현',
  threat: '위협/자해 조장',
  spam: '스팸/홍보',
};

interface RecommendationTracePanelProps {
  trace: RecommendationTrace;
}

export function RecommendationTracePanel({ trace }: RecommendationTracePanelProps) {
  const selectedCount = trace.candidates.filter((candidate) => candidate.selected).length;

  return (
    <details className="trace-panel">
      <summary className="trace-summary">
        <span className="trace-summary-title">
          생성 로그 보기
          <ChevronDown className="trace-chevron" size={15} />
        </span>
        <span className="trace-summary-meta">
          LLM {trace.candidates.length} · safety 탈락 {trace.safety_blocked_count} · 중복 제외 {trace.duplicate_candidate_count} · 최종 {selectedCount}
        </span>
      </summary>

      <div className="trace-content">
        <div className="trace-flow" aria-label="추천 생성 단계">
          <span>LLM 원본 후보</span><b>→</b>
          <span>Safety</span><b>→</b>
          <span>Ranker</span><b>→</b>
          <span>최종 선택</span>
        </div>

        <div className="trace-table-wrap">
          <table className="trace-table">
            <thead>
              <tr>
                <th>#</th>
                <th>LLM 원본 후보</th>
                <th>성향</th>
                <th>Safety</th>
                <th>Ranker</th>
                <th>최종</th>
              </tr>
            </thead>
            <tbody>
              {trace.candidates.map((candidate) => {
                const safetyLabel = candidate.safety_reason
                  ? SAFETY_REASON_LABEL[candidate.safety_reason] ?? candidate.safety_reason
                  : null;

                return (
                  <tr key={`${candidate.attempt}-${candidate.sequence}`} className={candidate.selected ? 'trace-selected' : undefined}>
                    <td className="trace-sequence">
                      {candidate.sequence}
                      {candidate.attempt > 1 && <span>시도 {candidate.attempt}</span>}
                    </td>
                    <td className="trace-comment">{candidate.comment}</td>
                    <td><TypeTag type={candidate.type} /></td>
                    <td>
                      {candidate.safety === 'blocked' ? (
                        <span className="trace-status blocked"><ShieldX size={13} /> 탈락 · {safetyLabel}</span>
                      ) : candidate.duplicate ? (
                        <span className="trace-status duplicate"><CircleMinus size={13} /> 중복 제외</span>
                      ) : (
                        <span className="trace-status passed"><CheckCircle2 size={13} /> 통과</span>
                      )}
                    </td>
                    <td className="trace-score">
                      {candidate.ranker_score == null ? '—' : `${candidate.ranker_score.toFixed(2)}%`}
                    </td>
                    <td>
                      {candidate.selected ? (
                        <span className="trace-status selected"><Trophy size={13} /> Top {candidate.final_rank}</span>
                      ) : (
                        <span className="trace-status muted">미선택</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="trace-note">Ranker 점수는 safety를 통과하고 중복 제거까지 마친 후보에만 계산됩니다. 이 로그는 현재 생성 응답에만 포함되며 과거 기록에는 저장하지 않습니다.</p>
      </div>
    </details>
  );
}
