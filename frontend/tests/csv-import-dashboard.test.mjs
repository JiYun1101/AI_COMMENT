import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { buildCsvImportDashboard } from '../.test-dist/csvImportDashboard.js';

const root=resolve(import.meta.dirname,'..');
const read=(name)=>readFileSync(resolve(root,name),'utf8');
const base = {
  video_id: 'abcdefghijk', comment_id: 'c-1', comment:'기존 본인 댓글',
  comment_url:'https://www.youtube.com/watch?v=abcdefghijk&lc=c-1',
  published_at:'2026-10-10T11:00:00Z',verified_channel_id:'owner',
};
const second={...base, comment_id:'c-2',comment:'두 번째 댓글'};
test('CSV imports are deduplicated and never counted as generated recommendations',()=>{
  const result=buildCsvImportDashboard([base,base,second],[]);
  assert.equal(result.imported,2);
  assert.equal(result.measured,0);
  assert.equal(result.likes,0);
  assert.equal(result.replies,0);
  assert.equal(result.items[0].weight,1);
});
test('only active, observed public engagement affects historical comment weights',()=>{
  const result=buildCsvImportDashboard([base,second],[
    {video_id:base.video_id,comment_id:base.comment_id,like_count:11,reply_count:2,status:'active',last_checked_at:'2026-10-28T08:00:00Z',public_metric_status:'active'},
    {video_id:second.video_id,comment_id:second.comment_id,like_count:999,reply_count:500,status:'active',last_checked_at:'2026-10-28T08:00:00Z',public_metric_status:'unavailable'}
  ]);
  assert.equal(result.imported,2);
  assert.equal(result.measured,1);
  assert.equal(result.reacted,1);
  assert.equal(result.likes,11);
  assert.equal(result.replies,2);
  assert.ok(result.items[0].weight > 1 && result.items[0].weight <=3);
  assert.equal(result.items[1].weight,1);
});
test('unrefreshed backend records and null engagement remain unmeasured',()=>{
  const missing=buildCsvImportDashboard([base],[
    {video_id:base.video_id,comment_id:base.comment_id,like_count:5,reply_count:2,status:'active',last_checked_at:null}
  ]);
  assert.equal(missing.measured,0);
  const zero=buildCsvImportDashboard([base],[
    {video_id:base.video_id,comment_id:base.comment_id,like_count:0,reply_count:0,status:'active',last_checked_at:'2026-10-28T08:00:00Z'}
  ]);
  assert.equal(zero.measured,1);
  assert.equal(zero.reacted,0);
  assert.equal(zero.items[0].weight,1);
});
test('CSV source requires server verified rows, never raw uploaded CSV IDs',()=>{
  const page=read('src/pages/MyCommentsPage.tsx');
  const ledger=read('src/utils/takeoutImportLedger.ts');
  assert.match(page,/saveVerifiedTakeoutImports\(result\.items, result\.owner_channel_id\)/);
  assert.match(page,/importPostedBackup\(result\.items\.map/);
  assert.match(ledger,/verified_channel_id/);
  assert.match(ledger,/cachedAccount\(\)\?\.id/);
  assert.doesNotMatch(page,/saveVerifiedTakeoutImports\(records/);
});
test('dashboard explicitly separates Takeout comments from AI recommendations',()=>{
  const panel=read('src/components/dashboard/ImportedCsvCommentsPanel.tsx');
  const dashboard=read('src/pages/DashboardPage.tsx');
  assert.match(dashboard,/<ImportedCsvCommentsPanel \/>/);
  assert.match(panel,/기존 댓글은 AI 추천 생성 횟수나 학습 데이터 수에 합산하지 않습니다/);
  assert.match(panel,/Google Takeout CSV/);
  assert.match(panel,/getStoredYouTubeApiKey/);
  assert.match(panel,/lookupPublicCommentMetrics/);
  assert.match(panel,/과거 CSV에는 AI 추천 ID가 없으므로/);
});
