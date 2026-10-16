import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const read = (p) => readFileSync(resolve(root, p), 'utf8');

test('account connection explains stale 401 and offers safe reset', () => {
  const page = read('src/pages/AccountPage.tsx');
  assert.match(page, /유효한 API 키\|X-API-Key\|401/);
  assert.match(page, /이전 서버 인증 초기화/);
  assert.match(page, /setStoredApiAccessToken\(''\)/);
  assert.match(page, /YouTube 계정·댓글 기록·브라우저 백업을 삭제하지 않습니다/);
  assert.match(page, /setServerError\(expiredCredential/);
});

test('published history links invalid auth to a reconnect screen', () => {
  const page = read('src/pages/MyCommentsPage.tsx');
  assert.match(page, /서버 연결 다시 하기/);
  assert.match(page, /navigate\('\/account\/connect'\)/);
  assert.match(page, /X-API-Key\|서버 인증\|401/);
});

test('Korean Takeout parser is available in deployed source; uploaded data must not be rewritten', () => {
  const parser = read('src/utils/takeoutComments.ts');
  assert.match(parser, /동영상id/);
  assert.match(parser, /댓글id/);
  assert.match(parser, /videoIndex/);
  assert.match(parser, /normalizeVideoId/);
});
