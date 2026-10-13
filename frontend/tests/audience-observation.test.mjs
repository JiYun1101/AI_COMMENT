import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');

test('observed audience is an independent action, not blocked by LLM readiness', () => {
  const page = read('src/pages/ReactionPreviewPage.tsx');
  const api = read('src/api/client.ts');
  assert.match(page, /onClick=\{\(\) => void loadObserved\(\)\} disabled=\{!urlValid \|\| observing\}/);
  assert.match(page, /onClick=\{\(\) => void persistObserved\(\)\}/);
  assert.match(page, /observed\.comparison\.distribution\.map/);
  assert.match(page, /observed\.caveat/);
  assert.match(api, /\/audience\/observed/);
  assert.match(api, /\/audience\/observations/);
});

test('observed panel avoids artificial accuracy claims and keeps original blue accents', () => {
  const css = read('src/styles/reaction-preview.css');
  const page = read('src/pages/ReactionPreviewPage.tsx');
  assert.match(page, /예상 후보 ↔ 실제 댓글/);
  assert.match(page, /실제 반응 불러오기/);
  assert.match(page, /실측 스냅샷 저장/);
  assert.match(css, /audience-observation-panel/);
  assert.match(css, /var\(--brand-600\)/);
  assert.match(read('src/styles/tokens.css'), /--brand-500:\s*#2c6ef2;/);
});
