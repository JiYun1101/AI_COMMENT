import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');

test('Material 3 styling is loaded after all existing feature styles', () => {
  const main = read('src/main.tsx');
  assert.match(main, /import '\.\/styles\/material3\.css';/);
  assert.ok(main.indexOf("import './styles/material3.css';") > main.indexOf("import './styles/engagement.css';"));
});

test('Material tonal colors and component states use shared CSS tokens', () => {
  const tokens = read('src/styles/tokens.css');
  const theme = read('src/styles/material3.css');
  assert.match(tokens, /--brand-500:\s*#2c6ef2;/);
  assert.match(theme, /--md-primary-container:/);
  assert.match(theme, /\.side-item\.active\s*\{/);
  assert.match(theme, /\.persona-card\.active\s*\{/);
  assert.match(theme, /:focus-visible/);
  assert.match(theme, /prefers-reduced-motion:\s*reduce/);
  assert.match(theme, /max-width:\s*760px/);
  assert.match(theme, /\.side-section\s*\{[\s\S]*?overflow-x:\s*auto;/);
});

test('the verified brand logo remains bundled; Figma source is not a runtime dependency', () => {
  const sidebar = read('src/components/layout/Sidebar.tsx');
  const packageJson = JSON.parse(read('package.json'));
  assert.match(sidebar, /ai-comment-brand-verified\.png/);
  assert.ok(!Object.keys(packageJson.dependencies ?? {}).some((name) => /material-ui|@mui|figma/.test(name)));
});

test('original AI_COMMENT brand and grayscale palette is preserved exactly', () => {
  const tokens = read('src/styles/tokens.css');
  const theme = read('src/styles/material3.css');
  const colors = {
    '--brand-50': '#eef4ff',
    '--brand-100': '#dbe6ff',
    '--brand-200': '#b7ceff',
    '--brand-300': '#8aafff',
    '--brand-400': '#5a8bfa',
    '--brand-500': '#2c6ef2',
    '--brand-600': '#1f57cf',
    '--brand-700': '#1846a6',
    '--brand-800': '#143a85',
    '--brand-900': '#0f2b64',
    '--neutral-50': '#f7f8fa',
    '--neutral-100': '#f1f3f5',
    '--neutral-150': '#e8ebef',
    '--neutral-200': '#dde1e6',
    '--neutral-300': '#c1c7cf',
    '--neutral-500': '#6b7481',
    '--neutral-900': '#0f141c',
    '--tag-question': '#2c6ef2',
  };
  for (const [token, expected] of Object.entries(colors)) {
    const line = tokens.split('\n').find((item) => item.trim().startsWith(token + ':'));
    assert.equal(line?.trim(), token + ': ' + expected + ';', token + ' should match the original palette');
  }
  const semanticRoles = [
    '--md-surface-dim: var(--neutral-50);',
    '--md-surface-container: var(--neutral-100);',
    '--md-primary-container: var(--brand-50);',
    '--md-on-primary-container: var(--brand-700);',
    '--md-outline-variant: var(--neutral-200);',
  ];
  for (const role of semanticRoles) assert.ok(theme.includes(role), role);
  assert.doesNotMatch(theme, /#(?:faf9fc|f3f0f7|ece6f2|e9dff3|463061|e2dbe8)\b/i);
});
