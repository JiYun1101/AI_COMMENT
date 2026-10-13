import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');

test('My Activity raw copy is parsed locally and verified by YouTube before a database write', () => {
  const parser = read('src/utils/myActivityPaste.ts');
  const page = read('src/pages/MyCommentsPage.tsx');
  const client = read('src/api/client.ts');
  assert.match(parser, /에 남긴 댓글/);
  assert.match(parser, /Set<string>/);
  assert.match(page, /parsePastedMyActivity\(pastedActivity\)/);
  assert.match(page, /recoverFromPastedActivity\(records\)/);
  assert.match(page, /등록합니다/);
  assert.match(client, /\/my-comments\/recover\/activity/);
  assert.match(client, /withYouTubeOAuth\(withRuntimeKeys/);
});

test('recovery is opt-in, bound to personal OAuth and shows missing matches', () => {
  const page = read('src/pages/MyCommentsPage.tsx');
  assert.match(page, /accountMode !== 'personal'/);
  assert.match(page, /이전 댓글 찾아서 추적/);
  assert.match(page, /activityResult\.failed/);
  assert.match(page, /activityResult\.reasons\.map/);
  assert.match(page, /search/i);
});
