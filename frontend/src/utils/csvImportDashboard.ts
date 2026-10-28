import { outcomeWeight } from './analysisEvidence';

export interface CsvOwnerRow {
  video_id: string;
  comment_id: string;
  comment: string;
  comment_url: string | null;
  published_at: string;
  verified_channel_id: string;
}
export interface CsvObservedRow {
  video_id: string;
  comment_id: string;
  like_count: number | null;
  reply_count: number | null;
  status: 'pending' | 'active' | 'missing';
  last_checked_at: string | null;
  public_metric_status?: 'active' | 'unavailable';
}
export interface CsvEvidenceRow extends CsvOwnerRow {
  likes: number | null;
  replies: number | null;
  measured: boolean;
  weight: number;
}
export function buildCsvImportDashboard(
  imports: CsvOwnerRow[],
  observations: CsvObservedRow[],
): {
  imported: number;
  measured: number;
  reacted: number;
  likes: number;
  replies: number;
  items: CsvEvidenceRow[];
} {
  const observed = new Map(observations.map(row=>[row.video_id+':'+row.comment_id,row]));
  const unique = new Map(imports.map(row=>[row.video_id+':'+row.comment_id,row]));
  const items: CsvEvidenceRow[] = [...unique.values()].map(row=>{
    const metric = observed.get(row.video_id+':'+row.comment_id);
    // A deleted/unavailable comment or an unrefreshed backend record is not
    // evidence of positive engagement, even if stale counts remain cached.
    const verified = metric?.public_metric_status === 'active'
      || (!metric?.public_metric_status && metric?.status === 'active' && Boolean(metric.last_checked_at));
    const likes = verified ? metric?.like_count ?? null : null;
    const replies = verified ? metric?.reply_count ?? null : null;
    const measured = likes !== null || replies !== null;
    return {
      ...row, likes, replies, measured,
      weight: outcomeWeight(likes,replies),
    };
  });
  items.sort((a,b)=>Number(b.measured)-Number(a.measured) || b.weight-a.weight || b.published_at.localeCompare(a.published_at));
  return {
    imported: items.length,
    measured: items.filter(x=>x.measured).length,
    reacted: items.filter(x=>x.measured && (x.likes ?? 0)+(x.replies ?? 0)>0).length,
    likes: items.reduce((sum,x)=>sum+(x.likes ?? 0),0),
    replies: items.reduce((sum,x)=>sum+(x.replies ?? 0),0),
    items,
  };
}
