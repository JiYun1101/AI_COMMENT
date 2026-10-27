import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const read = path => readFileSync(resolve(import.meta.dirname, '..', path), 'utf8');

test('shared server metrics are distinct from a logged-in member private history', () => {
  const view = read('src/components/dashboard/ModelDataProgressPanel.tsx');
  assert.match(view, /회원별 Supabase 비공개 분석은 포함하지 않습니다/);
  assert.match(view, /getStoredApiAccessToken\(\)/);
  assert.match(view, /to="\/account\/connect"/);
  const publicDashboard = read('src/pages/DashboardPage.tsx');
  assert.match(publicDashboard, /<ModelDataProgressPanel \/>/);
});

test('reaction preview readiness includes the response model when making recommendations', () => {
  const view = read('src/pages/ReactionPreviewPage.tsx');
  assert.match(view, /!health\.model\.ready/);
  assert.match(view, /!health\.storage\.ready/);
});
