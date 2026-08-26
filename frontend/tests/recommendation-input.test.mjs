import assert from 'node:assert/strict';
import test from 'node:test';

import { isRecommendationInputReady } from '../.test-dist/recommendationInput.js';

test('manual input can submit without a YouTube preview', () => {
  assert.equal(
    isRecommendationInputReady({
      mode: 'manual',
      urlValid: false,
      manualLength: 5,
      previewReady: false,
      previewLoading: false,
    }),
    true,
  );
});

test('valid URL waits for preview completion before submit', () => {
  assert.equal(
    isRecommendationInputReady({
      mode: 'url',
      urlValid: true,
      manualLength: 0,
      previewReady: false,
      previewLoading: true,
    }),
    false,
  );
  assert.equal(
    isRecommendationInputReady({
      mode: 'url',
      urlValid: true,
      manualLength: 0,
      previewReady: false,
      previewLoading: false,
    }),
    false,
  );
  assert.equal(
    isRecommendationInputReady({
      mode: 'url',
      urlValid: true,
      manualLength: 0,
      previewReady: true,
      previewLoading: false,
    }),
    true,
  );
});
