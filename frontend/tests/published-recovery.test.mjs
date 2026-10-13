import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');

test('publishing saves browser receipts and merges with server rows', () => {
  const api = read('src/api/client.ts');
  const util = read('src/utils/publishedLedger.ts');
  assert.match(api, /backUpPostedComment\(posted, request\.recommendation_id, mode\)/);
  assert.match(api, /backUpServerComments\(response\.items\)/);
  assert.match(api, /mergePostedBackup\(response, mode\)/);
  assert.match(util, /localStorage\.setItem/);
  assert.match(util, /local_only: true/);
  assert.match(util, /exportPostedBackup/);
});

test('recovery screen retains the data but requires server OAuth verification', () => {
  const page = read('src/pages/MyCommentsPage.tsx');
  const client = read('src/api/client.ts');
  assert.match(page, /restoreFromYouTube/);
  assert.match(page, /importPostedBackup/);
  assert.match(page, /브라우저 백업/);
  assert.match(client, /my-comments\/recover/);
});

test('publish UI warns if persistence failed even when YouTube succeeded', () => {
  const page = read('src/pages/RecommendPage.tsx');
  assert.match(page, /posted\.tracked/);
  assert.match(page, /posted\.browser_backup_saved/);
});
