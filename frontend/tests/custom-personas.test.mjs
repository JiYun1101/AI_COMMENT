import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
const read = (p) => readFileSync(resolve(root, p), 'utf8');

test('custom persona editor exposes phrases, voice, sample and punctuation constraints', () => {
  const form = read('src/components/persona/CustomPersonaEditor.tsx');
  const page = read('src/pages/PersonaPage.tsx');
  assert.match(form, /주로 사용하는 말투/);
  assert.match(form, /자주 쓰는 말/);
  assert.match(form, /사용하지 않을 단어/);
  assert.match(form, /사용하지 않을 문장부호/);
  assert.match(form, /말투 예시 한 문장/);
  assert.match(page, /saveCustomPersona\(draft\)/);
  assert.match(page, /removeCustomPersona\(id\)/);
  assert.match(page, /<CustomPersonaEditor/);
  assert.match(page, /onClick=\{\(\) => choosePersona\(persona\.id\)\}/);
});

test('browser persona store is bounded and protects against broken records', () => {
  const store = read('src/utils/customPersonas.ts');
  const client = read('src/api/client.ts');
  assert.match(store, /MAX_CUSTOM_PERSONAS = 12/);
  assert.match(store, /validateCustomPersona/);
  assert.match(store, /ai-comment\.custom-personas\.v1/);
  assert.match(client, /custom_persona: request\.custom_persona/);
  assert.match(client, /getCustomPersona/);
});

test('phrase editor retains empty lines while typing', () => {
  const form = read('src/components/persona/CustomPersonaEditor.tsx');
  assert.match(form, /return value\.split\(/);
  assert.doesNotMatch(form, /return value\.split\([^;]+\.filter\(Boolean\)/);
});
