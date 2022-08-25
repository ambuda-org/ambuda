import { $ } from '@/core.ts';
import Dictionary from '@/dictionary';

const sampleHTML = `
<div>
  <div id="dict--response">
    <p lang="sa">granthaH</p>
  </div>
</div>
`;

window.Sanscript = {
  t: jest.fn((s, from, to) => `${s}:${to}`),
}

beforeEach(() => {
  document.write(sampleHTML);
  window.localStorage.clear();
});

test('Dictionary can be created', () => {
  const d = Dictionary()
  d.init();
});

test('saveSettings and loadSettings', () => {
  const d1 = Dictionary();
  d1.script = "test script";
  d1.source = "test source";
  d1.saveSettings();

  const d2 = Dictionary()
  expect(d2.script).toBe("devanagari");
  expect(d2.source).toBe("mw");

  d2.loadSettings();
  expect(d2.script).toBe("test script");
  expect(d2.source).toBe("test source");
});

test('searchDictionary with empty query does nothing', () => {
  const d = Dictionary();
  expect(d.query).toBe("");
  d.searchDictionary();
});

test('updateScript transliterates and updates settings', () => {
  const d = Dictionary();
  d.init();

  d.uiScript = 'kannada';
  d.updateScript();
  expect(d.script).toBe('kannada');
  expect($('#dict--response').textContent.trim()).toBe('granthaH:kannada');

  const d2 = Dictionary()
  d2.init();
  expect(d2.script).toBe('kannada');
});
