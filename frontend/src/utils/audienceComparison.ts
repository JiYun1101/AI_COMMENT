/** Compare observed public comments with the same final Top-K used by the backend.
 * Logged-in analyses are stored privately in Supabase, not in the shared SQLite
 * database. Their expected distribution must be computed client-side.
 * Heuristic labels and differences are NOT model accuracy or audience probabilities.
 */
export type IntentKey = 'question' | 'praise' | 'confusion' | 'complaint' | 'purchase' | 'risk' | 'other';
export const INTENTS: { key: IntentKey; label: string; description: string }[] = [
  { key: 'question', label: '질문', description: '추가 정보나 설명을 요구하는 반응' },
  { key: 'praise', label: '칭찬', description: '긍정·공감·호감 중심의 반응' },
  { key: 'confusion', label: '혼란', description: '이해가 어렵거나 맥락이 불분명한 반응' },
  { key: 'complaint', label: '불만', description: '아쉬움·비판·불편을 드러내는 반응' },
  { key: 'purchase', label: '구매 의도', description: '가격·구매·출시 여부에 관심을 보이는 반응' },
  { key: 'risk', label: '리스크', description: '논란·신뢰·안전 이슈로 번질 수 있는 반응' },
  { key: 'other', label: '기타', description: '분류 규칙에 해당하지 않는 반응' },
];

/** Same rule order as src/audience/reactions.py (keep both covered by tests). */
export function classifyIntent(comment: string, type = ''): IntentKey {
  const text = comment.trim();
  if (!text) return 'other';
  if (/사기|거짓|조작|불법|혐오|신고|논란|위험|허위|과장광고|환불|저작권/i.test(text)) return 'risk';
  if (/구매|구입|사고 싶|살까|사야|가격|얼마|출시|재입고|어디서 사|링크 있|예약/i.test(text)) return 'purchase';
  if (/별로|아쉽|실망|불편|비싸|싫|최악|왜 이렇게|문제 있|개선|답답/i.test(text) || type === 'negative') return 'complaint';
  if (/무슨 뜻|이해가 안|이해 안|헷갈|모르겠|차이가 뭐|어떤 의미|설명이 부족|왜 그런/i.test(text)) return 'confusion';
  if (/[?？]/.test(text) || type === 'question' || /궁금|어떻게|왜 |뭐가|언제|어디|누가|인가요|나요\b|까요\b/i.test(text)) return 'question';
  if (type === 'empathy' || type === 'insight' || /감사|고마|최고|좋아요|좋네요|잘\s*봤|잘봤|응원|유익|도움|재밌|재미있|멋지|대박|힐링|만족/i.test(text)) return 'praise';
  return 'other';
}

interface RecommendationLike { comment: string; type: string }
interface Distribution { key: string; label: string; count: number; percentage: number }
interface ObservationLike {
  observed: { total: number; distribution: Distribution[] };
  expected: { total: number; distribution: Distribution[] } | null;
  comparison: {
    method: string; warning: string; sample_difference_points: number;
    distribution: Array<{
      key: string; label: string; expected_percentage: number;
      observed_percentage: number; delta_percentage_points: number;
    }>;
  } | null;
}

const oneDecimal = (value: number) => Math.round(value * 10) / 10;

/** Only used when server cannot look up a Supabase-private analysis. */
export function attachLocalComparison<T extends ObservationLike>(
  report: T, recommendations: RecommendationLike[],
): T {
  if (report.expected || report.comparison || !recommendations.length) return report;
  const candidates = recommendations.filter((item) => item.comment.trim());
  if (!candidates.length) return report;
  const total = candidates.length;
  const expected = {
    total,
    distribution: INTENTS.map(({ key, label }) => {
      const count = candidates.filter((item) => classifyIntent(item.comment, item.type) === key).length;
      return { key, label, count, percentage: oneDecimal(100 * count / total) };
    }),
  };
  if (!report.observed.total) return { ...report, expected };
  const actual = new Map(report.observed.distribution.map((item) => [item.key, item.percentage]));
  const distribution = expected.distribution.map((item) => {
    const observed = actual.get(item.key) ?? 0;
    return {
      key: item.key, label: item.label, expected_percentage: item.percentage,
      observed_percentage: observed, delta_percentage_points: oneDecimal(observed - item.percentage),
    };
  });
  return {
    ...report,
    expected,
    comparison: {
      method: 'client_private_top_k_vs_public_comment_sample',
      distribution,
      sample_difference_points: oneDecimal(distribution.reduce((sum, item) => sum + Math.abs(item.delta_percentage_points), 0) / 2),
      warning: '로그인 회원의 최종 Top-K 생성 후보를 브라우저 안에서만 실제 공개 댓글 표본과 비교했습니다. 예측 확률·정확도나 전체 시청자의 반응을 의미하지 않습니다.',
    },
  };
}
