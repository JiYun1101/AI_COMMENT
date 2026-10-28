import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const file = (name) => readFileSync(resolve(import.meta.dirname,'..',name),'utf8');

test('account connection health is retried during Render Free cold start', () => {
  const account = file('src/pages/AccountPage.tsx');
  assert.match(account, /await waitForHealthyBackend\(\(attempt\) => \{/);
  assert.match(account, /setApiRetryAttempt\(attempt\)/);
  assert.match(account, /API 서버 다시 확인/);
  assert.match(account, /setApiRetryKey\(\(value\) => value \+ 1\)/);
  assert.match(account, /Render 백엔드 재기동 확인 중/);
});

test('missing or rejected admin session is NOT a public API outage', () => {
  const account = file('src/pages/AccountPage.tsx');
  const check = account.slice(account.indexOf('const checkConnection = async'),account.indexOf('void checkConnection();'));
  assert.ok(check.indexOf('await waitForHealthyBackend') < check.indexOf('verifyServerConnection(token)'));
  assert.match(check, /const token = getStoredApiAccessToken\(\)/);
  assert.match(check, /if \(!token\)/);
  assert.match(check, /setServerStatus\('disconnected'\)/);
  assert.match(account, /API 서버 온라인/);
  assert.match(account, /관리자 인증 미연결 \(일반 API와 별개\)/);
});

test('only read-only health preflight retries; no repeated admin pairing POST', () => {
  const account = file('src/pages/AccountPage.tsx');
  const pairing = account.slice(account.indexOf('const pairServer = async'), account.indexOf('const saveServerToken'));
  assert.match(pairing, /await waitForHealthyBackend\(\)/);
  assert.equal((pairing.match(/await connectServerWithCode\(pairingCode\)/g) || []).length,1);
});
