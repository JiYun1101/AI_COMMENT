import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parsePersonaRestrictions, formatPersonaRestrictions } from '../.test-dist/compactPersona.js';

const root = resolve(import.meta.dirname, '..');
const read = (p) => readFileSync(resolve(root, p), 'utf8');

test('a new persona is edited inside the same grid as preset cards', () => {
  const form = read('src/components/persona/CustomPersonaEditor.tsx');
  const page = read('src/pages/PersonaPage.tsx');
  const css = read('src/styles/persona.css');

  assert.match(form, /말투 · 자주 쓰는 말/);
  assert.match(form, /쓰지 않을 말 · 문장부호/);
  assert.match(form, /저장하고 사용/);
  assert.doesNotMatch(form, /<fieldset|말투 예시 한 문장/);
  assert.match(page, /<CustomPersonaEditor/);
  assert.match(page, /saveCustomPersona\(next\)/);
  assert.match(page, /removeCustomPersona\(id\)/);
  assert.match(page, /onClick=\{\(\) => choosePersona\(persona\.id\)\}/);
  assert.match(page, /persona-add-card/);
  assert.match(css, /\.persona-card\.persona-editor-card/);
  assert.match(css, /\.persona-card\.persona-add-card/);
});

test('user text prohibitions are parsed into effective server marks and phrases', () => {
  assert.deepEqual(
    parsePersonaRestrictions('레전드, !, ㅋㅋ, 이모지, 마침표 금지, 쉼표, ?'),
    { forbidden_marks: ['exclamation', 'laughter', 'emoji', 'period', 'comma', 'question'],
      prohibited_phrases: ['레전드'] },
  );
  assert.deepEqual(parsePersonaRestrictions('대박, 대박, ㅎㅎ, 느낌표 금지'), {
    forbidden_marks: ['laughter', 'exclamation'], prohibited_phrases: ['대박'],
  });
  assert.deepEqual(parsePersonaRestrictions(''), { forbidden_marks: [], prohibited_phrases: [] });
  assert.throws(() => parsePersonaRestrictions(Array.from({ length: 9 }, (_, i) => `word${i}`).join(', ')));
});

test('an existing user persona can be reformatted and edited without losing existing restrictions', () => {
  const persisted = {
    id: 'custom_12345678', name: '기존 페르소나', speech_style: '조용하게',
    recurring_phrases: ['갠적으로'], prohibited_phrases: ['과장'],
    forbidden_marks: ['emoji', 'question'], sample_comment: '괜찮음',
  };
  assert.equal(formatPersonaRestrictions(persisted), '이모지, ?, 과장');
  assert.deepEqual(parsePersonaRestrictions(formatPersonaRestrictions(persisted)), {
    forbidden_marks: ['emoji', 'question'], prohibited_phrases: ['과장'],
  });
});

test('personas remain stored locally and are passed to the recommendation API', () => {
  const store = read('src/utils/customPersonas.ts');
  const client = read('src/api/client.ts');
  assert.match(store, /MAX_CUSTOM_PERSONAS = 12/);
  assert.match(store, /validateCustomPersona/);
  assert.match(store, /ai-comment\.custom-personas\.v1/);
  assert.match(client, /custom_persona: request\.custom_persona/);
  assert.match(client, /getCustomPersona/);
});
