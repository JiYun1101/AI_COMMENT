import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
const read = (file) => readFileSync(resolve(root, file), 'utf8');

test('browser pairing verifies limited session before persisting', () => {
  const code = read('src/api/client.ts');
  const fn = code.slice(code.indexOf('export async function connectServerWithCode'));
  assert.match(fn, /pairing_code: code\.trim\(\)/);
  assert.match(fn, /verifyServerConnection\(result\.access_token\)/);
  assert.match(fn, /setStoredApiAccessToken\(result\.access_token\)/);
  assert.ok(fn.indexOf('verifyServerConnection(result.access_token)') < fn.indexOf('setStoredApiAccessToken(result.access_token)'));
});

test('user explicitly confirms invitation, and URL fragment is scrubbed', () => {
  const page = read('src/pages/AccountPage.tsx');
  assert.match(page, /new URLSearchParams\(window\.location\.hash/);
  assert.match(page, /window\.history\.replaceState/);
  assert.match(page, /onClick=\{\(\) => void pairServer\(\)\}/);
  assert.match(page, /서버 연결하기/);
  assert.match(page, /API 서버 온라인/);
  assert.match(page, /관리자 인증 미연결/);
  assert.match(page, /await waitForHealthyBackend\(/);
  assert.match(read('src/api/client.ts'), /return await getHealth\(\)/);
  assert.match(page, /인증 확인 후 저장/);
});
