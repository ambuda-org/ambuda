import Proofer from '@/proofer';

window.IMAGE_URL = 'IMAGE_URL';
window.OpenSeadragon = (_) => ({
  addHandler: jest.fn((_, callback) => callback()),
  viewport: {
    getHomeZoom: jest.fn(() => 0.5),
    zoomTo: jest.fn((_) => {}),
  }
});

beforeEach(() => {
  window.localStorage.clear();
});

test('Proofer can be created', () => {
  const p = Proofer()
  p.init();

  expect(p.textZoom).toBe(1);
  expect(p.imageZoom).toBe(0.5);
});

test('saveSettings and loadSettings', () => {
  const oldProofer = Proofer()
  oldProofer.textZoom = "test text zoom";
  oldProofer.imageZoom = "test image zoom";
  oldProofer.layout = "side-by-side";
  oldProofer.saveSettings();

  const p = Proofer()
  p.loadSettings();
  expect(p.textZoom).toBe("test text zoom");
  expect(p.imageZoom).toBe("test image zoom");
  expect(p.layout).toBe("side-by-side");
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
