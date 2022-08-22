import Proofer from '@/proofer';

test('Proofer can be created', () => {
  const p = Proofer()
});

test('saveSettings and loadSettings', () => {
  const oldProofer = Proofer()
  oldProofer.textZoom = "test text zoom";
  oldProofer.imageZoom = "test image zoom";
  oldProofer.layout = "test layout";
  oldProofer.saveSettings();

  const p = Proofer()
  p.loadSettings();
  expect(p.textZoom).toBe("test text zoom");
  expect(p.imageZoom).toBe("test image zoom");
  expect(p.layout).toBe("test layout");
});
