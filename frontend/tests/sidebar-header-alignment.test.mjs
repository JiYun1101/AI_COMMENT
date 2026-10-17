import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const source = (file) => readFileSync(resolve(root, file), 'utf8');

test('logo and header use the same stable desktop height on every route', () => {
  const css = source('src/styles/material3.css');
  const header = source('src/components/layout/Header.tsx');

  assert.match(css, /\.app\s*\{\s*--app-shell-top-height:\s*128px/);
  assert.match(css, /\.app-header\s*\{[^}]*height:\s*var\(--app-shell-top-height\)/s);
  assert.match(css, /\.sidebar \.brand\.brand-button\s*\{[^}]*height:\s*calc\(var\(--app-shell-top-height\) - 18px\)/s);
  assert.match(css, /\.sidebar \.brand\.brand-button::after\s*\{[^}]*bottom:\s*0/s);
  assert.doesNotMatch(css, /var\(--app-header-height/, 'sidebar must not depend on the varying title/subtitle height');
  assert.doesNotMatch(header, /ResizeObserver|setProperty\('--app-header-height'\)/);
  assert.match(header, /className="app-header"/);
});

test('the logo never jumps vertically on hover; mobile keeps its own layout', () => {
  const css = source('src/styles/brand-logo.css');
  const layout = source('src/styles/material3.css');
  const sidebar = source('src/components/layout/Sidebar.tsx');

  assert.match(css, /\.brand-uploaded-logo\s*\{[^}]*width:\s*218px/s);
  assert.doesNotMatch(css, /transform:\s*translateY/);
  assert.match(layout, /@media \(max-width: 760px\)/);
  assert.match(layout, /@media \(min-width: 761px\)/);
  assert.match(sidebar, /className="brand brand-button"/);
});
