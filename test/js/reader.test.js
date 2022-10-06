import { $ } from '@/core.ts';
import Reader, { Layout, getBlockSlug } from '@/reader';

const sampleHTML = `
<body>
  <div id="text--content">
    <p lang="sa">granthaH</p>
  </div>
  <form id="dict--form">
    <input type="text" name="q"></input>
  </form>
  <div id="sidebar"><span lang="sa">padam</span> English</div>

  <script id="payload" type="application/json">
  {
    "blocks": [
      { "id": "1", "mula": "<s-lg>verse 1</s-lg>" }
    ]
  }
  </script>
</body>
`;

// Can't modify existing `window.location` -- delete it so that we can mock it.
// (See beforeEach and the tests below.)
delete window.location;

window.IMAGE_URL = 'IMAGE_URL';
window.Sanscript = {
  t: jest.fn((s, from, to) => `${s}:${to}`),
}
window.fetch = jest.fn(async (url) => {
  if (url === '/api/texts/sample-text/error') {
    return { ok: false };
  }
  if (url === '/api/texts/sample-text/1') {
    return {
      ok: true,
      json: async () => ({
          blocks: [
            { id: "1.1", mula: "text for 1.1" },
            { id: "1.2", mula: "text for 1.2" },
          ],
      })
    }
  }
});

beforeEach(() => {
  window.localStorage.clear();
  document.write(sampleHTML);
});

test('Reader can be created', () => {
  const r = Reader()
  r.init();
});

test('saveSettings and loadSettings work as expected', () => {
  const oldReader = Reader()
  oldReader.fontSize = "test font size";
  oldReader.script = "test script";
  oldReader.parseLayout = "test parse layout";
  oldReader.saveSettings();

  const r = Reader()
  r.loadSettings();
  expect(r.fontSize).toBe("test font size");
  expect(r.script).toBe("test script");
  expect(r.parseLayout).toBe("test parse layout");
});

test('loadSettings works if localStorage data is empty', () => {
  localStorage.setItem('reader', "{}");
  const r = Reader();
  r.loadSettings();
  expect(r.fontSize).toBe('md:text-xl');
  expect(r.script).toBe('devanagari');
  expect(r.parseLayout).toBe('in-place');
  expect(r.dictSources).toEqual(['mw']);
});

test('loadSettings works if localStorage data is corrupt', () => {
  localStorage.setItem('reader', "invalid JSON");
  const r = Reader();
  r.loadSettings();
  // No error -- OK
});

test('loadAjax sets properties correctly', async () => {
  window.location = new URL('https://ambuda.org/texts/sample-text/1');

  const r = Reader();
  await r.loadAjax();
  expect(r.blocks).toEqual([
    { id: "1.1", mula: "text for 1.1" },
    { id: "1.2", mula: "text for 1.2" },
  ]);
});

test("loadAjax doesn't throw an error on a bad URL", async () => {
  window.location = new URL('https://ambuda.org/texts/sample-text/error');

  const r = Reader();
  await r.loadAjax();
  expect(r.blocks).toEqual([]);
});

test('transliterateHTML transliterates with the current script', () => {
  const r = Reader();
  r.script = 'kannada';
  expect(r.transliterateHTML('<div>test</div>')).toBe('<div>test:kannada</div>');
});

test('transliterateStr transliterates with the current script', () => {
  const r = Reader();
  r.script = 'kannada';
  expect(r.transliterateStr('test')).toBe('test:kannada');
  expect(r.transliterateStr('')).toBe('');
});

test('getBlockSlug works', () => {
  expect(getBlockSlug('A.1.1')).toBe('1.1');
  expect(getBlockSlug('A.1')).toBe('1');
  expect(getBlockSlug('A.all')).toBe('all');
});

// Layout tests

test('CSS for parse layout is as expected', () => {
  const r = Reader();

  r.parseLayout = Layout.InPlace;
  expect(r.getMulaClasses()).toBe('');
  expect(r.getParseLayoutTogglerText()).toBe('Show original');
  expect(r.getParseLayoutClasses()).toMatch('');

  expect(r.showBlockMula({ showParse: false })).toBe(true);
  expect(r.getBlockClasses({ showParse: false })).toMatch('pointer');

  expect(r.showBlockMula({ showParse: true })).toBe(false);
  expect(r.getBlockClasses({ showParse: true })).toBe('');

  r.parseLayout = Layout.SideBySide;
  expect(r.getMulaClasses()).toBe('mr-4');
  expect(r.getParseLayoutTogglerText()).toBe('Hide parse');
  expect(r.getParseLayoutClasses()).toMatch('3xl');

  expect(r.showBlockMula({ showParse: false })).toBe(true);
  expect(r.getBlockClasses({ showParse: false })).toMatch('pointer');

  expect(r.showBlockMula({ showParse: true })).toBe(true);
  expect(r.getBlockClasses({ showParse: true })).toMatch('flex');
});

// Sidebar tests

test('toggleSourceSelector works', () => {
  const r = Reader();
  r.showDictSourceSelector = false;

  r.toggleSourceSelector();
  expect(r.showDictSourceSelector).toBe(true);

  r.toggleSourceSelector();
  expect(r.showDictSourceSelector).toBe(false);
});
