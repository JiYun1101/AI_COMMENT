import assert from 'node:assert/strict';
import test from 'node:test';
import { getRecommendationReadinessMessage } from '../.test-dist/readiness.js';

const ready = {
  model: { ready: true },
  llm: { ready: true },
  youtube: { configured: true },
  storage: { ready: true },
};

test('manual mode does not require YouTube API configuration', () => {
  const health = { ...ready, youtube: { configured: false } };
  assert.equal(getRecommendationReadinessMessage(health, false, 'manual'), null);
});

test('url mode requires YouTube API configuration', () => {
  const health = { ...ready, youtube: { configured: false } };
  assert.match(getRecommendationReadinessMessage(health, false, 'url'), /YouTube API/);
});

test('model and LLM readiness block recommendation before submit', () => {
  assert.match(
    getRecommendationReadinessMessage({ ...ready, model: { ready: false } }, false, 'manual'),
    /반응 예측 모델/,
  );
  assert.match(
    getRecommendationReadinessMessage({ ...ready, llm: { ready: false } }, false, 'manual'),
    /LLM 설정/,
  );
});

test('health request failure blocks recommendation with a connection message', () => {
  assert.match(getRecommendationReadinessMessage(null, true, 'manual'), /백엔드 연결/);
});
