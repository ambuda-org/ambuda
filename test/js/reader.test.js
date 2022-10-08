import { $ } from '@/core.ts';
import Reader, { Layout } from '@/reader';

const sampleHTML = `
<body>
  <div id="text--content">
    <p lang="sa">granthaH</p>
  </div>
  <div id="parse--response"></div>
  <form id="dict--form">
    <input type="text" name="q"></input>
  </form>
  <div id="sidebar"><span lang="sa">padam</span> English</div>

  <script id="payload" type="application/json">
  {
    "text_title": "Sample Text",
    "section_title": "Section 1",
    "prev_url": null,
    "next_url": "/texts/sample-text/2",
    "blocks": [
      { "slug": "1.1", "mula": "<s-lg>verse 1.1</s-lg>" },
      { "slug": "1.2", "mula": "<s-lg>verse 1.2</s-lg>" }
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
// Mocks for all API requests.
window.fetch = jest.fn(async (url) => {
  const mapping = {
    '/api/texts/sample-text/2': {
      json: async () => ({
        "text_title": "Sample Text",
        "section_title": "Section 2",
        "prev_url": "/texts/sample-text/1",
        "next_url": "/texts/sample-text/3",
        "blocks": [
          { "slug": "2.1", "mula": "<s-lg>verse 2.1</s-lg>" },
          { "slug": "2.2", "mula": "<s-lg>verse 2.2</s-lg>" },
        ]
      })
    },
    "/api/parses/sample-text/1.1": {
      text: async() => "<p>parse for 1.1</p>",
    },
    "/api/dictionaries/mw/padam": {
      text: async () => "<p>entry:padam</p>",
    },
  };

  if (url in mapping) {
    return { ok: true, ...mapping[url] };
  } else {
    return { ok: false };
  }
});

beforeEach(() => {
  window.location = new URL('https://ambuda.org/texts/sample-text/1');
  window.localStorage.clear();
  document.write(sampleHTML);
});

test('Reader can be created', () => {
  const r = Reader()
  r.init();
});

// Settings

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

// Utility functions

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

// Browser history

test('onPopHistoryState works as expected', () => {
  const r = Reader();
  r.data = 'initial data';

  const e = { state: { data: 'data' }};
  r.onPopHistoryState(e);

  expect(r.data).toBe('data');
});

test('onPopHistoryState is a no-op if there is no state', () => {
  const r = Reader();
  r.data = 'initial data';

  const e = { state: null };
  r.onPopHistoryState(e);

  expect(r.data).toBe('initial data');
});

// Ajax calls

test('fetchSection sets properties correctly', async () => {
  const r = Reader();
  r.init();

  await r.fetchSection("/texts/sample-text/2");
  expect(r.data).toEqual({
    "text_title": "Sample Text",
    "section_title": "Section 2",
    "prev_url": "/texts/sample-text/1",
    "next_url": "/texts/sample-text/3",
    "blocks": [
      { "slug": "2.1", "mula": "<s-lg>verse 2.1</s-lg>" },
      { "slug": "2.2", "mula": "<s-lg>verse 2.2</s-lg>" },
    ]
  });
});

test("fetchSection doesn't throw an error on a bad URL", async () => {
  window.location = new URL('https://ambuda.org/texts/sample-text/error');

  const r = Reader();
  r.init();

  await r.fetchSection();
  expect(r.data.blocks).toEqual([
    { "slug": "1.1", "mula": "<s-lg>verse 1.1</s-lg>" },
    { "slug": "1.2", "mula": "<s-lg>verse 1.2</s-lg>" },
  ]);
});

test("searchDictionary works with a valid source and query", async () => {
  const r = Reader();
  r.dictQuery = "padam";
  r.dictSources = ["mw"];

  await r.searchDictionary();
  expect(r.dictionaryResponse).toMatch("entry:padam");
});

test("searchDictionary shows an error if the word can't be found", async () => {
  const r = Reader();
  r.dictQuery = "unknown";
  r.dictSources = ["mw"];

  await r.searchDictionary();
  expect(r.dictionaryResponse).toMatch("Sorry");
});

test("searchDictionary is a no-op otherwise", async () => {
  const r = Reader();

  await r.searchDictionary();
  expect(r.dictionaryResponse).toBe(null);
});

test("fetchBlockParse works on a normal case", async () => {
  window.location = new URL('https://ambuda.org/texts/sample-text/1');

  const r = Reader();
  await r.fetchSection();

  const [html, ok] = await r.fetchBlockParse("1.1")
  expect(html).toBe("<p>parse for 1.1</p>");
  expect(ok).toBe(true);
});

test("fetchBlockParse shows an error if the word can't be found", async () => {
  window.location = new URL('https://ambuda.org/texts/sample-text/1');

  const r = Reader();
  await r.fetchSection();

  const [html, ok] = await r.fetchBlockParse("unknown")
  expect(html).toMatch("Sorry");
  expect(ok).toBe(false);
});

// `parseLayout` logic

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

test('hideParse works as expected', () => {
  const r = Reader();
  const b = { showParse: true };

  r.hideParse(b);
  expect(b.showParse).toBe(false);
});

// Click handlers

test('onClickBlock fetches and displays parse data', async () => {
  const r = Reader();
  r.init();
  await r.onClickBlock("1.1");

  expect(r.data.blocks[0].parse).toBe("<p>parse for 1.1</p>");
  expect(r.data.blocks[0].showParse).toBe(true);
});


test('onClickBlock toggles if parse data already exists', async () => {
  const r = Reader();
  r.init();
  await r.onClickBlock("1.1");
  r.data.blocks[0].showParse = false;

  r.onClickBlock("1.1");
  expect(r.data.blocks[0].showParse).toBe(true);
});

test("onClickBlock shows an error if the data doesn't exist.", async () => {
  const r = Reader();
  r.init();

  await r.onClickBlock("1.2");
  expect(r.sidebarErrorMessage).toMatch('Sorry');
});

// Dropdown handlers

test('toggleSourceSelector works', () => {
  const r = Reader();
  r.showDictSourceSelector = false;

  r.toggleSourceSelector();
  expect(r.showDictSourceSelector).toBe(true);

  r.toggleSourceSelector();
  expect(r.showDictSourceSelector).toBe(false);
});

test('onClickOutsideOfSourceSelector toggles if visible', async () => {
  const r = Reader();
  r.showDictSourceSelector = true;
  r.dictionaryResponse = null;

  await r.onClickOutsideOfSourceSelector();
  expect(r.showDictSourceSelector).toBe(false);
});

test('onClickOutsideOfSourceSelector is a no-op otherwise', async () => {
  const r = Reader();
  r.showDictSourceSelector = false;

  await r.onClickOutsideOfSourceSelector();
  expect(r.showDictSourceSelector).toBe(false);
});
