import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');

test('browser backup comments are included when requesting public metrics', () => {
  const page = read('src/pages/MyCommentsPage.tsx');
  assert.match(page, /next\.items\.filter\(\(item\) => item\.local_only \|\| serverError\)/);
  assert.match(page, /lookupPublicCommentMetrics/);
  assert.match(page, /storePublicMetricResponse/);
  assert.match(page, /applySavedPublicMetrics/);
});

test('local metrics retain the original comment receipt and measure on read-only route', () => {
  const util = read('src/utils/publicMetricsBackup.ts');
  const ledger = read('src/utils/publishedLedger.ts');
  const client = read('src/api/client.ts');
  assert.match(util, /localStorage\.setItem/);
  assert.match(util, /Never overwrite newer authenticated server measurements/);
  assert.match(client, /\/my-comments\/public-metrics/);
  assert.match(client, /withRuntimeKeys/);
  assert.match(ledger, /local_only: true/);
});

test('missing 24h and 7d milestones are not fabricated for offline receipts', () => {
  const page = read('src/pages/MyCommentsPage.tsx');
  assert.match(page, /item\.local_only && item\.hours_since_publish >= threshold/);
  assert.match(page, /기준 기록 없음/);
});
