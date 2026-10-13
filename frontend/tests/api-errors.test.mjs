import assert from 'node:assert/strict';
import test from 'node:test';
import { apiErrorMessage, networkErrorMessage } from '../.test-dist/apiErrors.js';

test('network failures are actionable instead of Failed to fetch', () => {
  assert.match(networkErrorMessage(new TypeError('Failed to fetch'), '오류'), /서버에 연결하지 못했습니다/);
});
test('read-only requests distinguish an expired request', () => {
  assert.match(networkErrorMessage(Object.assign(new Error('aborted'), { name: 'AbortError' }), '오류'), /시간이 초과/);
});
test('server startup and rate limits are described clearly', () => {
  assert.match(apiErrorMessage(503, 'Service unavailable', '실패'), /서버가 일시적으로/);
  assert.match(apiErrorMessage(429, null, '실패'), /요청 한도/);
});
test('authorization errors provide a route to settings', () => {
  assert.match(apiErrorMessage(401, null, '실패'), /연결 설정/);
});
test('FastAPI validation error arrays are translated safely', () => {
  const error = [{ loc: ['body', 'top_k'], msg: 'Input should be greater than 0', type: 'value_error' }];
  assert.match(apiErrorMessage(422, error, '실패'), /입력값/);
  assert.doesNotMatch(apiErrorMessage(422, error, '실패'), /\[object Object\]/);
});
test('server error details and page HTML are not directly displayed for 500 errors', () => {
  assert.match(apiErrorMessage(500, '<html>internal</html>', '실패'), /서버 처리 중 오류/);
});
