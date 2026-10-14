import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const file = (path) => readFileSync(resolve(root, path), 'utf8');

test('browser snapshots preserve the original model score and 24h/7d readings', () => {
  const ledger = file('src/utils/publishedLedger.ts');
  assert.match(ledger, /predicted_score: row\.predicted_score \?\?/);
  assert.match(ledger, /likes_24h: row\.likes_24h \?\?/);
  assert.match(ledger, /likes_7d: row\.likes_7d \?\?/);
  assert.match(ledger, /last_checked_at: row\.last_checked_at \?\?/);
  assert.match(ledger, /previous\?\.predicted_score/);
});

test('server performance exports require explicit action and keep portable backup format', () => {
  const page = file('src/pages/MyCommentsPage.tsx');
  const api = file('src/api/client.ts');
  assert.match(page, /서버 원본·성과 JSON 백업/);
  assert.match(api, /my-comments\/export/);
  assert.match(api, /ai-comment-server-/);
});

test('caption evidence is optional, time aligned and not described as frame analysis', () => {
  const page = file('src/pages/RecommendPage.tsx');
  const moments = file('src/components/recommend/VideoMomentsPanel.tsx');
  assert.match(page, /<VideoMomentsPanel/);
  assert.match(moments, /영상 자막 타임라인/);
  assert.match(moments, /화면 분석 전 단계/);
  assert.match(moments, /getVideoCaptionMoments/);
});
