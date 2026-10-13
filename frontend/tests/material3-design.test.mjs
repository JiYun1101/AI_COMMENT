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
  assert.match(tokens, /--brand-500:\s*#76559f;/);
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
