import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('../static/theme.js', import.meta.url), 'utf8');
function boot({ saved, dark = false, workspace = 'personal', blocked = false } = {}) {
  const data = new Map([['taskline-workspace', workspace], ['taskline-theme', saved]]);
  const listeners = {};
  const root = { dataset: {}, style: {}, lang: 'en' };
  const button = { setAttribute(key, value) { this[key] = value; } };
  const meta = { content: '' };
  const system = { matches: dark, addEventListener(event, fn) { this.change = fn; } };
  const window = {
    matchMedia: () => system,
    addEventListener(event, fn) { listeners[event] = fn; },
    dispatchEvent() {},
  };
  vm.runInNewContext(source, {
    window, Event: class {},
    document: { documentElement: root, querySelector: selector => selector === '#theme-toggle' ? button : meta },
    TasklineStorage: {
      getItem(key) { if (blocked) throw Error('Storage blocked'); return data.get(key); },
      setItem(key, value) { if (blocked) throw Error('Storage blocked'); data.set(key, value); },
      removeItem(key) { data.delete(key); },
    },
  });
  return { api: window.TasklineTheme, root, button, meta, system, data, listeners };
}

test('uses system appearance by default and responds to system changes', () => {
  const t = boot({ dark: true });
  assert.equal(t.root.dataset.theme, 'dark');
  assert.equal(t.root.style.colorScheme, 'dark');
  t.system.matches = false;
  t.system.change();
  assert.equal(t.root.dataset.theme, 'light');
});

test('saved appearance wins at boot; toggling persists across workspaces and reloads', () => {
  const t = boot({ saved: 'dark', workspace: 'work' });
  assert.equal(t.root.dataset.theme, 'dark');
  assert.equal(t.meta.content, '#141b24');
  t.api.setWorkspace('personal');
  assert.equal(t.meta.content, '#111a18');
  t.api.toggle();
  assert.equal(t.data.get('taskline-theme'), 'light');
  t.system.matches = true;
  t.system.change();
  assert.equal(t.root.dataset.theme, 'light');
  assert.equal(boot({ saved: t.data.get('taskline-theme'), dark: true }).root.dataset.theme, 'light');
});

test('accessible toggle localizes and synchronizes changes from another tab', () => {
  const t = boot();
  t.root.lang = 'ar';
  t.api.toggle();
  assert.equal(t.button['aria-label'], 'الوضع الداكن');
  assert.equal(t.button['aria-pressed'], 'true');
  assert.equal(t.button.title, 'التبديل إلى الوضع الفاتح');
  t.data.set('taskline-theme', 'light');
  t.listeners.storage({ key: 'taskline-theme' });
  assert.equal(t.button['aria-pressed'], 'false');
  t.data.delete('taskline-theme');
  t.system.matches = true;
  t.listeners.storage({ key: null });
  assert.equal(t.root.dataset.theme, 'dark');
});

test('invalid values and unavailable storage do not break the theme', () => {
  assert.equal(boot({ saved: 'invalid', dark: true }).root.dataset.theme, 'dark');
  const t = boot({ blocked: true });
  t.api.toggle();
  assert.equal(t.root.dataset.theme, 'dark');
});

test('theme bootstrap precedes CSS and deferred app scripts', () => {
  const html = readFileSync(new URL('../static/index.html', import.meta.url), 'utf8');
  assert.ok(html.indexOf('/theme.js?v=3') < html.indexOf('/styles.css'));
  assert.match(html, /<script src="\/theme.js\?v=3"><\/script>/);
});

test('settings can restore system appearance after a manual override', () => {
  const t = boot({ saved: 'light', dark: true });
  t.api.setPreference('system');
  assert.equal(t.api.preference(), 'system');
  assert.equal(t.root.dataset.theme, 'dark');
  assert.equal(t.data.has('taskline-theme'), false);
});

test('dark palettes have readable text, buttons and status badges (at least 4.5:1)', () => {
  const css = readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
  const blocks = [...css.matchAll(/html\[data-theme="dark"\](?:\[data-workspace="work"\])? \{([^}]+)\}/g)];
  const base = {};
  const luminance = hex => {
    const channels = hex.slice(1).match(/../g).map(value => parseInt(value, 16) / 255)
      .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
    return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
  };
  assert.equal(blocks.length, 2);
  for (const [, block] of blocks) {
    for (const [, token, hex] of block.matchAll(/--([\w-]+): (#[0-9a-f]{6});/g)) base[token] = hex;
    for (const [fg, bg] of [['ink', 'card'], ['muted', 'card'], ['muted', 'soft'], ['green', 'soft'],
      ['on-primary', 'green'], ['danger', 'danger-soft'], ['gold', 'gold-soft'], ['purple', 'purple-soft']]) {
      const values = [luminance(base[fg]), luminance(base[bg])].sort((a, b) => b - a);
      const ratio = (values[0] + .05) / (values[1] + .05);
      assert.ok(ratio >= 4.5, `${fg}/${bg}: ${ratio.toFixed(2)}`);
    }
  }
});
