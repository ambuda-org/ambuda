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

window.fetch = jest.fn(async (url) => {
  return {
    ok: true,
    text: async () => '<div>response</div>',
  }
});

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

test('searchDictionary fetches a response', async () => {
  const d = Dictionary();
  d.query = "saMskRtam";
  await d.searchDictionary();
  expect($('#dict--response').innerHTML).toBe('<div>response</div>');
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
