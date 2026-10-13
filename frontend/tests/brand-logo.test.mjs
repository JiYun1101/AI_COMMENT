import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');

test('sidebar and about page use the same verified image and fallback', () => {
  const sidebar = readFileSync(resolve(root, 'src/components/layout/Sidebar.tsx'), 'utf8');
  const about = readFileSync(resolve(root, 'src/pages/AboutPage.tsx'), 'utf8');

  for (const [name, source] of [['sidebar', sidebar], ['about page', about]]) {
    assert.match(source, /ai-comment-brand-verified\.png/, name + ' should import verified logo');
    assert.match(source, /src=\{brandLogo\}/, name + ' should use bundled logo');
    assert.match(source, /onError=\{\(\) => setLogoFailed\(true\)\}/, name + ' needs an error fallback');
    assert.match(source, /className="brand-fallback"/, name + ' should have a fallback label');
  }

  assert.doesNotMatch(sidebar, /ai-comment-brand\.webp/, 'broken unverified WebP must not be used');
});

test('verified logo has valid PNG signature and positive dimensions', () => {
  const file = readFileSync(resolve(root, 'src/assets/ai-comment-brand-verified.png'));
  assert.equal(file.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
  assert.equal(file.subarray(12, 16).toString('ascii'), 'IHDR');
  assert.ok(file.readUInt32BE(16) > 0);
  assert.ok(file.readUInt32BE(20) > 0);
});
