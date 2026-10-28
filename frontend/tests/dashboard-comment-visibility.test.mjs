import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');

test('dashboard CSV table comment cell does not inherit global .content flex styles', () => {
  const component = read('src/components/dashboard/DataTable.tsx');
  assert.match(component, /<td className="dashboard-comment-cell">\{row\.comment\}<\/td>/);
  assert.doesNotMatch(component, /<td className="content">/);
  assert.match(component, /<div className="dashboard-table-scroll"/);
});

test('dashboard comment text wraps and narrow layouts can horizontally scroll the table', () => {
  const css = read('src/styles/app.css');
  assert.match(css, /\.dashboard-table-scroll\s*\{[^}]*overflow-x:\s*auto;/);
  assert.match(css, /\.dashboard-comments-table\s*\{[^}]*min-width:\s*1320px;/);
  const match = css.match(/\.dashboard-comments-table td\.dashboard-comment-cell\s*\{([^}]+)\}/);
  assert.ok(match);
  assert.match(match[1], /white-space:\s*normal;/);
  assert.match(match[1], /overflow-wrap:\s*anywhere;/);
  assert.doesNotMatch(match[1], /max-width:\s*0;/);
  assert.doesNotMatch(match[1], /text-overflow:\s*ellipsis;/);
});
