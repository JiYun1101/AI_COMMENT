import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');

test('the shared sidebar logo navigates home, not to About', () => {
  const sidebar = read('src/components/layout/Sidebar.tsx');
  assert.match(sidebar, /className="brand brand-button" onClick=\{\(\) => navigate\('\/'\)\}/);
  assert.match(sidebar, /aria-label="AI_COMMENT 메인 페이지로 이동"/);
  assert.doesNotMatch(sidebar, /className="brand brand-button" onClick=\{\(\) => navigate\('\/about'\)\}/);
});

test('the logo in the About page also takes the user home', () => {
  const about = read('src/pages/AboutPage.tsx');
  assert.match(about, /className="about-brand" onClick=\{\(\) => navigate\('\/'\)\}/);
  assert.match(about, /className="about-enter" onClick=\{\(\) => navigate\('\/'\)\}/);
});

test('About action precedes the rightmost account control in the shared header', () => {
  const header = read('src/components/layout/Header.tsx');
  const right = header.indexOf('className="hd-right"');
  const about = header.indexOf('className="hd-about-link"', right);
  const account = header.indexOf('className="avatar-persona-wrap"', right);
  assert.ok(right >= 0 && about > right && account > about);
  assert.match(header, /onClick=\{\(\) => navigate\('\/about'\)\}/);
  assert.match(header, />\s*About\s*<\/button>/);
  assert.match(read('src/App.tsx'), /<Route path="\/about" element=\{<AboutPage \/>\}/);
});

test('the sidebar logo is raised without moving the sidebar menu or changing brand colors', () => {
  const theme = read('src/styles/material3.css');
  const tokens = read('src/styles/tokens.css');
  assert.match(theme, /\.sidebar \.brand-uploaded-logo,[\s\S]*?\.sidebar \.brand-fallback\s*\{\s*position: relative;\s*top: -14px;/);
  assert.match(theme, /\.hd-about-link:hover\s*\{/);
  assert.match(theme, /\.hd-about-link \{ min-height: 36px;/);
  assert.match(tokens, /--brand-500:\s*#2c6ef2;/);
  assert.match(read('src/components/layout/Sidebar.tsx'), /ai-comment-brand-verified\.png/);
});
