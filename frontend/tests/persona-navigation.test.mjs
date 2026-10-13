import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');

test('persona sidebar item navigates directly, regardless of parent page handler', () => {
  const sidebar = readFileSync(resolve(root, 'src/components/layout/Sidebar.tsx'), 'utf8');
  const app = readFileSync(resolve(root, 'src/App.tsx'), 'utf8');
  const dashboard = readFileSync(resolve(root, 'src/pages/DashboardPage.tsx'), 'utf8');

  assert.match(sidebar, /label="페르소나"[^\n]+onClick=\{\(\) => go\('\/persona'\)\}/);
  assert.doesNotMatch(sidebar, /label="페르소나"[^\n]+onClick=\{\(\) => onNav\('persona'\)\}/);
  assert.match(sidebar, /const go = \(path: string\) => \{/);
  assert.match(sidebar, /navigate\(path\);/);
  assert.match(app, /<Route path="\/persona" element=\{<PersonaPage \/>\}/);
  assert.match(dashboard, /<Sidebar current="dashboard" onNav=\{handleNav\} \/>/);
});

test('persona options still persist their selection', () => {
  const page = readFileSync(resolve(root, 'src/pages/PersonaPage.tsx'), 'utf8');
  assert.match(page, /onClick=\{\(\) => choosePersona\(persona\.id\)\}/);
  assert.match(page, /setSelectedPersona\(id\);/);
});
