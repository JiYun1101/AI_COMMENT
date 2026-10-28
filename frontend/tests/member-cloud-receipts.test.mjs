import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const read = path => readFileSync(resolve(root, path), 'utf8');

test('member cloud receipt backup is owner-authenticated and never uses service role keys', () => {
  const code = read('src/api/account.ts');
  assert.match(code, /savePrivatePublishedReceipts\(/);
  assert.match(code, /listPrivatePublishedReceipts\(/);
  assert.match(code, /'ai_comment_published_receipts'/);
  assert.match(code, /'\?on_conflict=user_id,comment_id'/);
  assert.match(code, /user_id: owner/);
  assert.match(code, /'Bearer ' \+ access/);
  assert.doesNotMatch(code, /service_role_key|supabase_service_role/i);
});

test('real YouTube publication is never repeated on failed cloud backup', () => {
  const code = read('src/api/client.ts');
  const publish = code.slice(code.indexOf('export async function publishYouTubeComment('),
    code.indexOf('export interface AuthenticatedYouTubeIdentity'));
  assert.match(publish, /const posted = await requestJson<YouTubeCommentPublishResponse>/);
  assert.match(publish, /backUpPostedComment\(posted/);
  assert.match(publish, /await savePrivatePublishedReceipts\(/);
  assert.match(publish, /catch \(error\) \{[\s\S]*cloudSaved = false/);
  assert.match(publish, /cloud_backup_saved: cloudSaved/);
  assert.equal((publish.match(/\/youtube\/comments/g) || []).length, 1);
  assert.match(read('src/pages/RecommendPage.tsx'), /YouTube 댓글 게시 자체는 성공했습니다\. 다시 게시하지 마세요/);
});

test('cloud receipts never automatically restore server YouTube tracking or OAuth tokens', () => {
  const code = read('src/pages/MyCommentsPage.tsx');
  assert.match(code, /Supabase에 게시 기록 백업/);
  assert.match(code, /내 계정 클라우드 백업 가져오기/);
  assert.match(code, /importPostedBackup\(records\.map/);
  assert.match(code, /서버에 다시 추적하려면 YouTube 계정 본인 인증이 필요합니다/);
  const auth = read('src/api/account.ts');
  const backupCode = auth.slice(auth.indexOf('export interface PrivatePublishedReceipt'));
  assert.doesNotMatch(backupCode, /oauth_token|refresh_token|client_secret|DATABASE_URL/);
});
