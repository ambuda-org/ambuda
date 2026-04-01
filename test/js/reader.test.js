import { $ } from '@/core.ts';
import Reader, { toAksharas } from '@/reader';

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
    "section_title": "Sample Section",
    "prev_url": null,
    "next_url": "/texts/sample-text/2",
    "blocks": [
      { "slug": "1.1", "mula": "<s-lg>verse 1</s-lg>" },
      { "slug": "1.2", "mula": "<s-lg>verse 2</s-lg>" }
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
  schemes: { devanagari: {}, hk: {}, iast: {}, kannada: {} },
};

// Mock history.replaceState/pushState to avoid SecurityError in jsdom.
const origReplaceState = history.replaceState;
const origPushState = history.pushState;
history.replaceState = jest.fn();
history.pushState = jest.fn();
// Mocks for all API requests.
window.fetch = jest.fn(async (url) => {
  const mapping = {
    '/api/texts/sample-text/1': {
      json: async () => ({
        "text_title": "Sample Text",
        "section_title": "Sample Section",
        "prev_url": null,
        "next_url": "/texts/sample-text/2",
        "blocks": [
          { "slug": "1.1", "mula": "<s-lg>verse 1</s-lg>" },
          { "slug": "1.2", "mula": "<s-lg>verse 2</s-lg>" },
        ]
      })
    },
    "/api/parses/sample-text/1.1": {
      text: async() => "<p>parse for 1.1</p>",
    },
    "/api/dictionaries/mw/padam?script=devanagari": {
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
  window.localStorage.clear();
  document.write(sampleHTML);
});

test('Reader can be created', () => {
  window.location = new URL('https://ambuda.org/texts/sample-text/1');
  const r = Reader()
  r.$root = { dataset: { script: 'devanagari' } };
  r.$nextTick = (fn) => fn();
  r.init();
});

test('saveSettings and loadSettings work as expected', () => {
  const oldReader = Reader()
  oldReader.fontSize = "test font size";
  oldReader.saveSettings();

  const r = Reader()
  r.loadSettings();
  expect(r.fontSize).toBe("test font size");
});

test('loadSettings works if localStorage data is empty', () => {
  localStorage.setItem('reader', "{}");
  const r = Reader();
  r.loadSettings();
  expect(r.fontSize).toBe('md:text-xl');
  expect(r.dictSources).toEqual(['mw']);
});

test('loadSettings works if localStorage data is corrupt', () => {
  localStorage.setItem('reader', "invalid JSON");
  const r = Reader();
  r.loadSettings();
  // No error -- OK
});

// Ajax calls

test("searchDictionary works with a valid source and query", async () => {
  const r = Reader();
  r.dictQuery = "padam";
  r.dictSources = ["mw"];
  r.userScript = "devanagari";

  await r.searchDictionary();
  expect(r.dictionaryResponse).toMatch("entry:padam");
});

test("searchDictionary shows an error if the word can't be found", async () => {
  const r = Reader();
  r.dictQuery = "unknown";
  r.dictSources = ["mw"];
  r.userScript = "devanagari";

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
  const [html, ok] = await r.fetchBlockParse("1.1")
  expect(html).toBe("<p>parse for 1.1</p>");
  expect(ok).toBe(true);
});

test("fetchBlockParse shows an error if the word can't be found", async () => {
  window.location = new URL('https://ambuda.org/texts/sample-text/1');

  const r = Reader();
  const [html, ok] = await r.fetchBlockParse("unknown")
  expect(html).toMatch("Sorry");
  expect(ok).toBe(false);
});

// Click handlers

test('onClickBlock populates analyzeData and opens sidebar', async () => {
  window.location = new URL('https://ambuda.org/texts/sample-text/1');

  // Update mock to return HTML with <s-w> elements
  const origFetch = window.fetch;
  window.fetch = jest.fn(async (url) => {
    if (url === '/api/parses/sample-text/1.1') {
      return {
        ok: true,
        text: async () => '<s-lg><s-w lemma="dharma" parse="noun, masculine nominative singular">dharma</s-w> <s-w lemma="kzetra" parse="noun, neuter locative singular">kzetre</s-w></s-lg>',
      };
    }
    return { ok: false };
  });

  const r = Reader();
  r.$root = { dataset: { script: 'devanagari' } };
  r.$nextTick = (fn) => fn();
  r.init();
  await r.onClickBlock("1.1");

  expect(r.analyzeData.blockSlug).toBe("1.1");
  expect(r.analyzeData.words).toHaveLength(2);
  expect(r.analyzeData.words[0].lemma).toBe("dharma");
  expect(r.analyzeData.words[0].parse).toBe("noun, masculine nominative singular");
  expect(r.sidebarTab).toBe('analyze');
  expect(r.showSidebar).toBe(true);

  window.fetch = origFetch;
});

test('onClickBlock uses cached words on repeat click', async () => {
  window.location = new URL('https://ambuda.org/texts/sample-text/1');

  const origFetch = window.fetch;
  let fetchCount = 0;
  window.fetch = jest.fn(async (url) => {
    if (url === '/api/parses/sample-text/1.1') {
      fetchCount += 1;
      return {
        ok: true,
        text: async () => '<s-lg><s-w lemma="test" parse="noun">test</s-w></s-lg>',
      };
    }
    return { ok: false };
  });

  const r = Reader();
  r.$root = { dataset: { script: 'devanagari' } };
  r.$nextTick = (fn) => fn();
  r.init();
  await r.onClickBlock("1.1");
  expect(fetchCount).toBe(1);

  // Second click should use cache, not fetch again.
  await r.onClickBlock("1.1");
  expect(fetchCount).toBe(1);
  expect(r.analyzeData.blockSlug).toBe("1.1");

  window.fetch = origFetch;
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

// toAksharas
// ==========

test('toAksharas splits simple consonant+vowel aksharas', () => {
  expect(toAksharas('कका')).toEqual(['क', 'का']);
});

test('toAksharas keeps anusvara with its akshara', () => {
  expect(toAksharas('सं')).toEqual(['सं']);
});

test('toAksharas keeps visarga with its akshara', () => {
  expect(toAksharas('कः')).toEqual(['कः']);
});

test('toAksharas keeps conjuncts (virama+consonant) together', () => {
  expect(toAksharas('ज्ञा')).toEqual(['ज्ञा']);
});

test('toAksharas keeps triple conjuncts together', () => {
  expect(toAksharas('स्त्र')).toEqual(['स्त्र']);
});

test('toAksharas keeps trailing virama (halant) attached', () => {
  expect(toAksharas('क्')).toEqual(['क्']);
});

test('toAksharas splits independent vowels into separate aksharas', () => {
  expect(toAksharas('अइ')).toEqual(['अ', 'इ']);
});

test('toAksharas treats spaces as separate units', () => {
  expect(toAksharas('क ख')).toEqual(['क', ' ', 'ख']);
});

test('toAksharas treats punctuation as separate units', () => {
  expect(toAksharas('क।')).toEqual(['क', '।']);
});

test('toAksharas treats digits as separate units', () => {
  expect(toAksharas('०१')).toEqual(['०', '१']);
});

test('toAksharas handles non-Devanagari text as individual characters', () => {
  expect(toAksharas('abc')).toEqual(['a', 'b', 'c']);
});

test('toAksharas handles a realistic word: dharmakSetre', () => {
  expect(toAksharas('धर्मक्षेत्रे')).toEqual(['ध', 'र्म', 'क्षे', 'त्रे']);
});

test('toAksharas handles vowel sign + anusvara together', () => {
  expect(toAksharas('कां')).toEqual(['कां']);
});

test('toAksharas returns empty array for empty string', () => {
  expect(toAksharas('')).toEqual([]);
});
