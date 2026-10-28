import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const src = (path) => readFileSync(resolve(import.meta.dirname, '..', path), 'utf8');

test('guest history is bounded and browser-only, separately scoped from RLS account history', () => {
  const guest = src('src/utils/browserAnalysisHistory.ts');
  assert.match(guest, /const MAX_ITEMS = 40/);
  assert.match(guest, /localStorage\.setItem/);
  assert.match(guest, /saveGuestBrowserAnalysis/);
  assert.match(guest, /listGuestBrowserAnalyses/);
  const client=src('src/api/client.ts');
  assert.match(client, /if \(!signedIn\) \{/);
  assert.match(client, /saveGuestBrowserAnalysis\(response, request\)/);
  assert.match(client, /if \(cachedAccount\(\)\) return listPrivateAnalyses/);
  assert.match(client, /if \(cachedAccount\(\)\) return getPrivateAnalysis/);
  assert.match(client, /getGuestBrowserAnalysis\(analysisId\)/);
});

test('dashboard visibly marks browser-only source and separate observed outcomes', () => {
  const panel=src('src/components/dashboard/ModelDataProgressPanel.tsx');
  assert.match(panel, /isBrowserGuest/);
  assert.match(panel, /이 브라우저에 보관된 최근 분석/);
  assert.match(panel, /다른 기기와 자동 동기화되지 않습니다/);
  assert.match(panel, /listPrivatePublishedReceipts/);
  assert.match(panel, /공개 반응 확인/);
  assert.match(panel, /모델 가중치를 자동/);
});
