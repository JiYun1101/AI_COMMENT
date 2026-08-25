import assert from 'node:assert/strict';
import test from 'node:test';

import { extractYouTubeVideoId, isValidYouTubeVideoUrl } from '../.test-dist/youtube.js';

const id = 'dQw4w9WgXcQ';

test('supports the same single-video URL shapes as the backend', () => {
  assert.equal(extractYouTubeVideoId(`https://www.youtube.com/watch?v=${id}`), id);
  assert.equal(extractYouTubeVideoId(`https://youtu.be/${id}?t=20`), id);
  assert.equal(extractYouTubeVideoId(`https://www.youtube.com/shorts/${id}`), id);
  assert.equal(extractYouTubeVideoId(`https://www.youtube.com/embed/${id}`), id);
  assert.equal(extractYouTubeVideoId(`https://www.youtube.com/live/${id}`), id);
});

test('rejects playlists, other hosts, and malformed values before submit', () => {
  assert.equal(isValidYouTubeVideoUrl('https://www.youtube.com/playlist?list=PL123'), false);
  assert.equal(isValidYouTubeVideoUrl(`https://example.com/watch?v=${id}`), false);
  assert.equal(isValidYouTubeVideoUrl('hello'), false);
});
