import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const read = file => readFileSync(resolve(root, file), 'utf8');

test('recommendation page retries read-only health after cold start and exposes retry button', () => {
  const page = read('src/pages/RecommendPage.tsx');
  assert.match(page, /const \[healthRetryKey, setHealthRetryKey\]/);
  assert.match(page, /const checkHealth = async \(attempt: number\)/);
  assert.match(page, /const health = await getHealth\(\)/);
  assert.match(page, /if \(attempt < 4\)/);
  assert.match(page, /window\.setTimeout\(\(\) => \{/);
  assert.match(page, /onClick=\{\(\) => setHealthRetryKey\(\(value\) => value \+ 1\)\}/);
  assert.match(page, /서버 다시 확인/);
  assert.match(page, /백엔드 연결 확인이 실패했습니다:/);
  assert.match(page, /if \(cancelled\) return/);
  assert.match(page, /window\.clearTimeout\(retryTimer\)/);
  assert.match(page, /waitForHealthyBackend\(/);
  assert.match(page, /preparingRecommendation=/);
});

test('health reconnection must never auto-repeat YouTube publishing or LLM generation', () => {
  const page = read('src/pages/RecommendPage.tsx');
  const block = page.slice(page.indexOf('const checkHealth = async'), page.indexOf('}, [healthRetryKey]'));
  assert.doesNotMatch(block, /await recommend\(|await publishYouTubeComment\(|startYouTubeOAuth\(/);
  assert.equal((block.match(/await getHealth\(\)/g) || []).length, 1);
  const readiness = read('src/utils/readiness.ts');
  assert.match(readiness, /추천 서비스 상태를 확인할 수 없습니다/);
});

test('Render cold-start preflight only retries GET and manual mode works without YouTube API', () => {
  const page = read('src/pages/RecommendPage.tsx');
  const api = read('src/api/client.ts');
  const composer = read('src/components/recommend/Composer.tsx');
  assert.match(page, /useState<Mode>\('manual'\)/);
  assert.match(page, /await waitForHealthyBackend\(/);
  assert.match(page, /await recommend\(/);
  assert.ok(page.indexOf('await waitForHealthyBackend') < page.indexOf('await recommend('));
  const preflight = api.slice(api.indexOf('export async function waitForHealthyBackend'), api.indexOf('export async function recommend'));
  assert.match(preflight, /await getHealth\(\)/);
  assert.doesNotMatch(preflight, /await recommend\(|await publishYouTubeComment\(/);
  assert.match(composer, /서버 연결 확인 중/);
});
