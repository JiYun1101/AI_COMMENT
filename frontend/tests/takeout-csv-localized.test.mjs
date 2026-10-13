import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseTakeoutCommentsCsv } from '../.test-dist/takeoutComments.js';

test('Korean Google Takeout columns with embedded JSON and padded video ID', () => {
  // Synthetic fixture shaped like the user's Korean-language export.
  const csv = [
    '\uFEFF댓글 ID,채널 ID,댓글 생성 타임스탬프,가격,동영상 ID,댓글 텍스트',
    'Ugy000001,UCexample,2026-10-13T08:40:00+00:00,0,abcdefghijk,"{""text"":""영상이 재밌네요""}"',
    'Ugy000002,UCexample,2026-10-13T08:41:00+00:00,0," -y-j-uwrLDg","{""text"":""어제 봤음""}"',
    'Ugy000001,UCexample,2026-10-13T08:40:00+00:00,0,abcdefghijk,"{""text"":""중복""}"',
  ].join('\r\n');

  assert.deepEqual(parseTakeoutCommentsCsv(csv), [
    { commentId: 'Ugy000001', videoId: 'abcdefghijk' },
    { commentId: 'Ugy000002', videoId: '-y-j-uwrLDg' },
  ]);
});

test('previous English columns still work', () => {
  const csv = 'Comment ID,Video ID\nUgy000003,abcdefghijk\n';
  assert.deepEqual(parseTakeoutCommentsCsv(csv), [
    { commentId: 'Ugy000003', videoId: 'abcdefghijk' },
  ]);
});

test('localized video URL headers and invalid entries are handled', () => {
  const csv = [
    '댓글 아이디,동영상 URL',
    'Ugy000004,https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'Ugy000005,not-valid',
  ].join('\n');
  assert.deepEqual(parseTakeoutCommentsCsv(csv), [
    { commentId: 'Ugy000004', videoId: 'dQw4w9WgXcQ' },
  ]);
});

test('does not invent IDs for non-Takeout CSV', () => {
  assert.throws(() => parseTakeoutCommentsCsv('댓글 텍스트,날짜\n가을 좋다,2026-10-07'), /댓글 ID·동영상 ID/);
});
