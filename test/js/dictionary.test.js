import { $ } from '@/core.ts';
import Dictionary from '@/dictionary';

const sampleHTML = `
<div>
  <div id="dict--response">
    <p lang="sa">padam</p>
  </div>
</div>
`;

window.Sanscript = {
  t: jest.fn((s, from, to) => `${s}:${to}`),
}

window.fetch = jest.fn(async (url) => {
  // Special URL so we can test server errors.
  if (url === '/api/dictionaries/mw/error') {
    return { ok: false }
  } else {
    const segments = url.split('/');
    const respText = segments.pop();
    const dict = segments.pop();
    return {
      ok: true,
      text: async () => `<div>fetched ${dict}:${respText}</div>`,
    }
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

test('saveSettings and loadSettings work as expected', () => {
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

test('loadSettings works if localStorage data is empty', () => {
  localStorage.setItem('dictionary', "{}");
  const d = Dictionary();
  d.loadSettings();
  expect(d.script).toBe('devanagari');
  expect(d.source).toBe('mw');
});

test('loadSettings works if localStorage data is corrupt', () => {
  localStorage.setItem('dictionary', "invalid JSON");
  const d = Dictionary();
  d.loadSettings();
  expect(d.script).toBe('devanagari');
  expect(d.source).toBe('mw');
});

test('updateSource updates config then fetches', async () => {
  const d = Dictionary();
  d.init();
  d.query = 'foo';
  expect(d.source).toBe('mw');

  d.source = 'apte';
  await d.updateSource();
  expect(d.source).toBe('apte');
  expect($('#dict--response').innerHTML).toBe('<div>fetched apte:foo</div>');
});

test('updateScript transliterates and updates settings', () => {
  const d = Dictionary();
  d.init();

  d.uiScript = 'kannada';
  d.updateScript();
  expect(d.script).toBe('kannada');
  expect($('#dict--response').textContent.trim()).toBe('padam:kannada');

  const d2 = Dictionary()
  d2.init();
  expect(d2.script).toBe('kannada');
});

test('searchDictionary fetches a response', async () => {
  const d = Dictionary();
  d.query = "saMskRtam";
  await d.searchDictionary();
  expect($('#dict--response').innerHTML).toBe('<div>fetched mw:saMskRtam</div>');
});

test('searchDictionary does nothing if query is empty', async () => {
  const d = Dictionary();
  await d.searchDictionary();
  expect($('#dict--response').innerHTML.trim()).toBe('<p lang="sa">padam</p>');
});

test('searchDictionary gracefully handles a server error', async () => {
  const d = Dictionary();
  d.query = 'error';
  await d.searchDictionary();
  expect($('#dict--response').innerHTML.trim()).toMatch(new RegExp('^<p>Sorry.*'));
});

test('searchFor fetches a response', async () => {
  const d = Dictionary();
  await d.searchFor("saMskRtam");
  expect($('#dict--response').innerHTML).toBe('<div>fetched mw:saMskRtam</div>');
});

test('addToSearchHistory adds the given query', async () => {
  const d = Dictionary();
  expect(d.history).toEqual([]);

  d.addToSearchHistory("deva");
  expect(d.history).toEqual(["deva"]);
});

test('addToSearchHistory reorders an existing word', async () => {
  const d = Dictionary();
  d.history = ["deva", "svarga"];
  d.addToSearchHistory("deva");
  expect(d.history).toEqual(["svarga", "deva"]);
});

test('addToSearchHistory flushes a word over capacity', async () => {
  const d = Dictionary();
  d.history = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"];
  d.addToSearchHistory("deva");
  expect(d.history).toEqual(["2", "3", "4", "5", "6", "7", "8", "9", "10", "deva"]);
});
