import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { attachLocalComparison, classifyIntent } from '../.test-dist/audienceComparison.js';

const empty = (total = 4) => ({
  video_id: 'dQw4w9WgXcQ',
  analysis_id: null,
  order: 'relevance',
  observed: {
    total,
    distribution: [
      { key: 'question', label: '질문', count: 1, percentage: 25 },
      { key: 'praise', label: '칭찬', count: 2, percentage: 50 },
      { key: 'other', label: '기타', count: 1, percentage: 25 },
    ],
  },
  expected: null,
  comparison: null,
  caveat: 'biased sample',
  examples: [], comments: [],
});

test('private Top-K generated comments compare locally without sending Supabase analysis ID', () => {
  const report = attachLocalComparison(empty(), [
    { comment: '언제 공개되나요?', type: 'question' },
    { comment: '좋은 설명 감사합니다', type: 'empathy' },
  ]);
  assert.equal(report.expected?.total, 2);
  assert.equal(report.expected?.distribution.find(x => x.key === 'question')?.percentage, 50);
  assert.equal(report.comparison?.method, 'client_private_top_k_vs_public_comment_sample');
  assert.equal(report.comparison?.distribution.find(x => x.key === 'question')?.delta_percentage_points, -25);
  assert.equal(report.comparison?.distribution.find(x => x.key === 'praise')?.delta_percentage_points, 0);
  assert.match(report.comparison?.warning || '', /정확도/);
});

test('do not invent an observed comparison without observations, or replace server comparison', () => {
  const noObservations = attachLocalComparison(empty(0), [{ comment: '가격이 궁금해요', type: 'general' }]);
  assert.equal(noObservations.expected?.total, 1);
  assert.equal(noObservations.comparison, null);
  const server = empty();
  server.expected = { total: 1, distribution: [] };
  assert.equal(attachLocalComparison(server, [{ comment: '괜찮아요', type: 'general' }]), server);
});

test('frontend intent classification matches server priority cases', () => {
  assert.equal(classifyIntent('광고가 사기 같아요', 'empathy'), 'risk');
  assert.equal(classifyIntent('얼마인가요?', 'question'), 'purchase');
  assert.equal(classifyIntent('이해가 안 돼요', 'general'), 'confusion');
  assert.equal(classifyIntent('언제 올라오나요?', 'general'), 'question');
  assert.equal(classifyIntent('정말 감사합니다', 'empathy'), 'praise');
  assert.equal(classifyIntent('공백이 아닌 평범한 말', 'general'), 'other');
  assert.equal(classifyIntent('  ', 'question'), 'other');
});

test('reaction preview uses final recommended Top-K, and private snapshot omits private analysis id', () => {
  const read = path => readFileSync(resolve(import.meta.dirname, '..', path), 'utf8');
  const page = read('src/pages/ReactionPreviewPage.tsx');
  const api = read('src/api/client.ts');
  assert.match(page, /return response\.recommendations\.filter/);
  assert.match(page, /attachLocalComparison\(report, response\.recommendations\)/);
  const snapshot = api.slice(api.indexOf('export async function saveAudienceSnapshot'), api.indexOf('export async function listAudienceSnapshots'));
  assert.match(snapshot, /analysisId && !cachedAccount\(\)/);
});
