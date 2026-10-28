import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const read = (file) => readFileSync(resolve(root, file), 'utf8');

test('Google OAuth redirect is absolute even when preview API uses a same-origin /api proxy', () => {
  const api = read('src/api/client.ts');
  assert.match(api, /new URL\([\s\S]*?\$\{API_BASE\}\/youtube\/oauth\/callback/);
  assert.match(api, /window\.location\.origin/);
  assert.match(api, /'X-YouTube-OAuth-Redirect-URI': YOUTUBE_OAUTH_REDIRECT_URI/);
  assert.equal(
    new URL('/api/youtube/oauth/callback', 'https://ai-comment-presentation-20261028.onrender.com').toString(),
    'https://ai-comment-presentation-20261028.onrender.com/api/youtube/oauth/callback',
  );
});

test('OAuth UI cannot start without private server pairing and does not mask HTTP 401 as YouTube disconnected', () => {
  const page = read('src/pages/AccountPage.tsx');
  assert.match(page, /if \(verified\.connected\) \{[\s\S]*?await getYouTubeOAuthStatus\(\)/);
  assert.match(page, /if \(!token\) \{[\s\S]*?setServerStatus\('disconnected'\)/);
  assert.match(page, /if \(serverStatus !== 'connected'\)/);
  assert.match(page, /disabled=\{oauthBusy \|\| serverStatus !== 'connected'\}/);
  assert.match(page, /서버 관리자 인증 필요 · YouTube 연결 상태 미확인/);
  assert.match(page, /이메일 회원 로그인 및 YouTube Data API Key로는 이 인증을 대신할 수 없습니다/);
  assert.match(page, /health\.auth\?\.pairing_available/);
  assert.match(page, /현재 서버에서는 초대 코드 발급 기능이 비활성화돼 있습니다/);
  assert.match(page, /disabled=\{serverBusy \|\| pairingAvailable === false/);

});
