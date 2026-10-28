import type { AnalysisSummary, PublishedComment } from '../types/comment';
import type { PrivatePublishedReceipt } from '../api/account';

export interface EvidenceComment {
  recommendationId: string;
  analysisId: string;
  comment: string;
  title: string;
  publishedAt: string;
  likes: number | null;
  replies: number | null;
  measured: boolean;
  positive: boolean;
  weight: number;
  url: string | null;
}

/** This is a dashboard EVIDENCE weight, not an updated AI model coefficient. */
export function outcomeWeight(likes: number | null, replies: number | null): number {
  if (likes === null && replies === null) return 1;
  const positiveLikes = Math.max(0, likes ?? 0);
  const positiveReplies = Math.max(0, replies ?? 0);
  return Math.min(3, 1 + .25 * Math.log2(1 + positiveLikes) + .5 * Math.log2(1 + positiveReplies));
}

function dayKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
}

export function analysisGrowth(
  analyses: AnalysisSummary[],
  now: Date = new Date(),
): { date: string; new_analyses: number; cumulative_analyses: number }[] {
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const start = new Date(end);
  start.setDate(start.getDate() - 13);
  const dated = analyses
    .map(row => ({ id: row.id, at: new Date(row.created_at) }))
    .filter(row => !Number.isNaN(row.at.getTime()));
  const unique = [...new Map(dated.map(row => [row.id, row])).values()];
  let cumulative = unique.filter(row => row.at < start).length;
  const daily: { date: string; new_analyses: number; cumulative_analyses: number }[] = [];
  for (let day=0; day<14; day++) {
    const at = new Date(start);
    at.setDate(start.getDate() + day);
    const next = new Date(at);
    next.setDate(at.getDate() + 1);
    const count = unique.filter(row => row.at >= at && row.at < next).length;
    cumulative += count;
    daily.push({ date: dayKey(at), new_analyses: count, cumulative_analyses: cumulative });
  }
  return daily;
}

export function buildOutcomeEvidence(
  analyses: AnalysisSummary[],
  receipts: PrivatePublishedReceipt[],
  published: PublishedComment[],
  recommendations: Array<{analysisId: string; recommendationId: string; comment: string}>,
): { publishedCount: number; observedCount: number; positiveCount: number; weighted: EvidenceComment[] } {
  // A posting receipt is account-owned evidence. Never identify ownership from
  // a shared backend /my-comments row by itself.
  const analysisById = new Map(analyses.map(row => [row.id, row]));
  const validRecommendations = new Map(recommendations.map(r => [r.recommendationId, r]));
  const metrics = new Map(published.map(row => [row.video_id+':'+row.comment_id, row]));
  const items: EvidenceComment[] = [];
  const seen = new Set<string>();

  for (const receipt of receipts) {
    const rec = receipt.recommendation_id ? validRecommendations.get(receipt.recommendation_id) : undefined;
    if (!rec || !receipt.recommendation_id || seen.has(receipt.recommendation_id)) continue;
    const analysis = analysisById.get(rec.analysisId);
    if (!analysis) continue;
    seen.add(receipt.recommendation_id);
    const observed = metrics.get(receipt.video_id+':'+receipt.comment_id);
    // A missing/unavailable video/comment must never be scored as successful.
    const active = Boolean(observed && (observed.public_metric_status === 'active'
      || (!observed.public_metric_status && observed.status === 'active'))
      && observed.last_checked_at);
    const likes = active ? observed?.like_count ?? null : null;
    const replies = active ? observed?.reply_count ?? null : null;
    const measured = likes !== null || replies !== null;
    items.push({
      recommendationId: receipt.recommendation_id,
      analysisId: analysis.id,
      comment: receipt.comment,
      title: analysis.video_title || analysis.source_text,
      publishedAt: receipt.published_at,
      likes, replies, measured,
      positive: measured && ((likes ?? 0) + (replies ?? 0) > 0),
      weight: outcomeWeight(likes, replies),
      url: receipt.comment_url,
    });
  }
  items.sort((a,b)=> b.weight - a.weight || b.publishedAt.localeCompare(a.publishedAt));
  return {
    publishedCount: items.length,
    observedCount: items.filter(x=>x.measured).length,
    positiveCount: items.filter(x=>x.positive).length,
    weighted: items,
  };
}
