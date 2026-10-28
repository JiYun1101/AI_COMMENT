import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { analysisGrowth, outcomeWeight, buildOutcomeEvidence } from '../.test-dist/analysisEvidence.js';

const analysis = {
  id:'a_one', source_type:'manual', source_text:'AI 에이전트 개발',
  video_title:null, created_at:'2026-10-27T08:00:00.000Z',
  recommendation_count:2,
};

test('14-day trend uses persisted unique analyses, including historical baseline', () => {
  const days=analysisGrowth([analysis,analysis,{...analysis,id:'a_old',created_at:'2026-10-01T00:00:00Z'}],new Date('2026-10-28T13:00:00Z'));
  assert.equal(days.length,14);
  assert.equal(days.at(-1).cumulative_analyses,2);
  assert.equal(days.reduce((sum,x)=>sum+x.new_analyses,0),1);
  assert.equal(days[0].cumulative_analyses,1);
});

test('published recommendation needs owner receipt; posting alone is NOT a success signal', () => {
  const recs=[{analysisId:'a_one',recommendationId:'r_one',comment:'관련 내용이 잘 정리됐네요'}];
  const receipt={video_id:'abcdefghijk', comment_id:'comment_123',comment:'관련 내용이 잘 정리됐네요',comment_url:'https://youtube.com',published_at:'2026-10-27T10:00:00Z',recommendation_id:'r_one'};
  const withoutReceipt=buildOutcomeEvidence([analysis],[],[],recs);
  assert.equal(withoutReceipt.publishedCount,0);
  const posted=buildOutcomeEvidence([analysis],[receipt],[],recs);
  assert.equal(posted.publishedCount,1);
  assert.equal(posted.observedCount,0);
  assert.equal(posted.positiveCount,0);
  assert.equal(posted.weighted[0].weight,1);

  const measured=buildOutcomeEvidence([analysis],[receipt],[],recs,[{
    video_id:'abcdefghijk',comment_id:'comment_123',status:'active',like_count:7,reply_count:2,
  }]);
  assert.equal(measured.publishedCount,1);
  assert.equal(measured.observedCount,1);
  assert.equal(measured.positiveCount,1);
  assert.ok(measured.weighted[0].weight>1);
  assert.ok(measured.weighted[0].weight<=3);
});

test('unavailable public counters do not count as observed success', () => {
  const recs=[{analysisId:'a_one',recommendationId:'r_one',comment:'comment'}];
  const receipt={video_id:'abcdefghijk',comment_id:'comment_123',comment:'comment',comment_url:null,published_at:'2026-10-27T10:00:00Z',recommendation_id:'r_one'};
  const evidence=buildOutcomeEvidence([analysis],[receipt],[],recs,[{
    video_id:'abcdefghijk',comment_id:'comment_123',status:'unavailable',like_count:99,reply_count:4,
  }]);
  assert.equal(evidence.observedCount,0);
  assert.equal(evidence.positiveCount,0);
  assert.equal(evidence.weighted[0].weight,1);
});

test('weights are bounded with logarithmic returns and show zero-measured baseline', () => {
  assert.equal(outcomeWeight(null,null),1);
  assert.equal(outcomeWeight(0,0),1);
  assert.ok(outcomeWeight(1,0)>1);
  assert.ok(outcomeWeight(1,1)>outcomeWeight(1,0));
  assert.equal(outcomeWeight(100000,10000),3);
});

test('dashboard renders history, account-scoped receipts, and evidence without claiming auto retrain', () => {
  const dir=resolve(import.meta.dirname,'..');
  const panel=readFileSync(resolve(dir,'src/components/dashboard/ModelDataProgressPanel.tsx'),'utf8');
  const page=readFileSync(resolve(dir,'src/pages/RecommendPage.tsx'),'utf8');
  assert.match(panel,/getPrivateAnalysisOverview/);
  assert.match(panel,/listPrivatePublishedReceipts/);
  assert.match(panel,/분석 기록이 쌓이는 흐름/);
  assert.match(panel,/실제 선택·게시 댓글의 성과 가중치/);
  assert.match(panel,/모델 가중치를 자동/);
  assert.match(panel,/\/\?analysis=/);
  assert.match(page,/new URLSearchParams\(location\.search\)/);
});
