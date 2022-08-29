import { $ } from '@/core.ts';
import Proofer from '@/proofer';

const sampleHTML = `
<div>
  <textarea id="content"></textarea>
</div>
`;

// Can't modify existing `window.location` -- delete it so that we can mock it.
// (See beforeEach and the tests below.)
delete window.location;
window.IMAGE_URL = 'IMAGE_URL';
window.OpenSeadragon = (_) => ({
  addHandler: jest.fn((_, callback) => callback()),
  viewport: {
    getHomeZoom: jest.fn(() => 0.5),
    zoomTo: jest.fn((_) => {}),
  }
});
window.Sanscript = {
  // Preface `s` with a marker so that we can verify that we're using the right
  // selection range.
  t: jest.fn((s, from, to) => `:${s}:${to}`),
}
window.fetch = jest.fn(async (url) => {
  // Special URL so we can test server errors.
  if (url === '/api/ocr/error') {
    return { ok: false }
  } else {
    const segments = url.split('/');
    const page = segments.pop();
    return {
      ok: true,
      text: async () => `text for ${page}`,
    }
  }
});

beforeEach(() => {
  window.location = null;
  window.localStorage.clear();
  document.write(sampleHTML);
});

test('Proofer can be created', () => {
  const p = Proofer()
  p.init();

  expect(p.textZoom).toBe(1);
  expect(p.imageZoom).toBe(0.5);
});

test('saveSettings and loadSettings work as expected', () => {
  const oldProofer = Proofer()
  oldProofer.textZoom = "test text zoom";
  oldProofer.imageZoom = "test image zoom";
  oldProofer.layout = "side-by-side";
  oldProofer.fromScript = "test from script";
  oldProofer.toScript = "test to script";
  oldProofer.saveSettings();

  const p = Proofer()
  p.loadSettings();
  expect(p.textZoom).toBe("test text zoom");
  expect(p.imageZoom).toBe("test image zoom");
  expect(p.layout).toBe("side-by-side");
  expect(p.fromScript).toBe("test from script");
  expect(p.toScript).toBe("test to script");
});

test('loadSettings works if localStorage data is empty', () => {
  localStorage.setItem('proofing-editor', "{}");
  const p = Proofer();
  p.loadSettings();
  expect(p.textZoom).toBe(1);
  expect(p.layout).toBe('side-by-side');
});

test('loadSettings works if localStorage data is corrupt', () => {
  localStorage.setItem('proofing-editor', "invalid JSON");
  const p = Proofer();
  p.loadSettings();
  // No error -- OK
});

test('runOCR handles a valid server response', async () => {
  const p = Proofer();
  window.location = new URL("https://ambuda.org/proofing/my-project/my-page");
  await p.runOCR();
  expect($("#content").value).toBe('text for my-page');
});

test('runOCR handles an invalid server response', async () => {
  const p = Proofer();
  window.location = new URL("https://ambuda.org/proofing/error");
  await p.runOCR();
  expect($("#content").value).toBe('(server error)');
});

test('increaseImageZoom works and gets saved', () => {
  const p = Proofer()
  p.init();
  expect(p.imageZoom).toBe(0.5);

  p.increaseImageZoom();
  expect(p.imageZoom).toBe(0.6);

  const p2 = Proofer();
  p2.init();
  expect(p2.imageZoom).toBe(0.6);
});

test('decreaseImageZoom works and gets saved', () => {
  const p = Proofer()
  p.init();
  expect(p.imageZoom).toBe(0.5);

  p.decreaseImageZoom();
  expect(p.imageZoom).toBe(0.4);

  const p2 = Proofer();
  p2.init();
  expect(p2.imageZoom).toBe(0.4);
});

test('resetImageZoom works and gets saved', () => {
  const p = Proofer()
  p.init();
  p.imageZoom = 3;

  p.resetImageZoom();
  expect(p.imageZoom).toBe(0.5);
});

test('increaseTextSize works and gets saved', () => {
  const p = Proofer()
  p.init();
  expect(p.textZoom).toBe(1);

  p.increaseTextSize();
  expect(p.textZoom).toBe(1.2);

  const p2 = Proofer();
  expect(p2.textZoom).toBe(1);
  p2.loadSettings();
  expect(p2.textZoom).toBe(1.2);
});

test('decreaseTextSize works and gets saved', () => {
  const p = Proofer()
  expect(p.textZoom).toBe(1);

  p.decreaseTextSize();
  expect(p.textZoom).toBe(0.8);

  const p2 = Proofer();
  expect(p2.textZoom).toBe(1);
  p2.loadSettings();
  expect(p2.textZoom).toBe(0.8);
});

test('displaySideBySide works and gets saved', () => {
  const p = Proofer()
  p.layout = 'foo';

  p.displaySideBySide();
  expect(p.layout).toBe('side-by-side');

  const p2 = Proofer();
  p2.loadSettings();
  expect(p2.layout).toBe('side-by-side');
});

test('displayTopAndBottom works and gets saved', () => {
  const p = Proofer()
  p.displayTopAndBottom();

  const p2 = Proofer();
  expect(p2.layout).toBe('side-by-side');
  p2.loadSettings();
  expect(p2.layout).toBe('top-and-bottom');
});

test('transliterate works and saves settings', () => {
  const p = Proofer();
  const $text = $('#content');
  $text.value = 'Sanskrit (saMskRtam) text'
  $text.setSelectionRange(10, 19);

  p.fromScript = 'hk'
  p.toScript = 'iast';
  p.transliterate()

  expect($text.value).toBe('Sanskrit (:saMskRtam:iast) text')
});

function markupFixtures(text) {
  const p = Proofer();
  const $text = $('#content');
  $text.value = 'This is sample text.'
  $text.setSelectionRange(8, 14);
  return { p, $text };
}

test('markAsError works', () => {
  const {p, $text } = markupFixtures();
  p.markAsError()
  expect($text.value).toBe('This is <error>sample</error> text.')
});

test('markAsFix works', () => {
  const {p, $text } = markupFixtures();
  p.markAsFix()
  expect($text.value).toBe('This is <fix>sample</fix> text.')
});

test('markAsUnclear works', () => {
  const {p, $text } = markupFixtures();
  p.markAsUnclear()
  expect($text.value).toBe('This is <flag>sample</flag> text.')
});

test('markAsFootnoteNumber works', () => {
  const {p, $text } = markupFixtures();
  p.markAsFootnoteNumber()
  expect($text.value).toBe('This is [^sample] text.')
});

