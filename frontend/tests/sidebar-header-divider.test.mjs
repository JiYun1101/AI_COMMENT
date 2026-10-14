import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const read = (p) => readFileSync(resolve(root, p), 'utf8');

test('sidebar logo divider uses the shared home page top-bar height', () => {
  const header = read('src/components/layout/Header.tsx');
  const styles = read('src/styles/material3.css');
  assert.match(header, /className="app-header"/);
  assert.doesNotMatch(header, /ResizeObserver|getBoundingClientRect/);
  assert.match(styles, /--app-shell-top-height:\\s*128px/);
  assert.match(styles, /height:\\s*var\\(--app-shell-top-height\\)/);
  assert.match(styles, /height:\\s*calc\\(var\\(--app-shell-top-height\\)\\s*-\\s*18px\\)/);
  assert.match(styles, /\\.sidebar \\.brand\\.brand-button::after\\s*\\{/);
  assert.match(styles, /background:\\s*var\\(--md-outline-variant\\)/);
  assert.match(styles, /pointer-events:\\s*none/);
});

test('divider alignment changes only the desktop layout and keeps the logo lifted', () => {
  const styles = read('src/styles/material3.css');
  const sidebar = read('src/components/layout/Sidebar.tsx');
  assert.match(styles, /@media \(min-width: 761px\) \{/);
  assert.match(styles, /@media \(min-width: 761px\) and \(max-width: 1020px\)/);
  assert.match(styles, /--sidebar-inline-padding:\s*10px/);
  assert.match(styles, /\.sidebar \.brand-uploaded-logo,[\s\S]*?top:\s*-14px;/);
  assert.match(sidebar, /className="brand brand-button" onClick=\{\(\) => navigate\('\/'\)\}/);
  assert.match(read('src/styles/tokens.css'), /--brand-500:\s*#2c6ef2;/);
});
