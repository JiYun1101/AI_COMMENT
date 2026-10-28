import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const source = readFileSync(resolve(import.meta.dirname, '../src/api/client.ts'), 'utf8');

test('non-JSON rate-limited proxy response has actionable retry guidance', () => {
  const errors = source.slice(source.indexOf('async function getErrorMessage'), source.indexOf('async function requestJson'));
  assert.match(errors, /if \(res\.status === 429\)/);
  assert.match(errors, /res\.headers\.get\('Retry-After'\)/);
  assert.match(errors, /요청이 일시적으로 제한됐습니다 \(429\)/);
  assert.match(errors, /중복 호출을 피해주세요/);
  assert.match(errors, /Render 무료 서버·프록시 또는 외부 API/);
});

test('do not auto-repeat generation or YouTube posts after 429', () => {
  const requestBlock = source.slice(source.indexOf('async function requestJson'), source.indexOf('export async function getHealth'));
  assert.match(requestBlock, /await fetch\(url, init\)/);
  assert.doesNotMatch(requestBlock, /setTimeout|while\s*\(|for\s*\(/);
});
