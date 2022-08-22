import Reader from '@/reader';

test('Reader can be created', () => {
  const r = Reader()
});

test('init', () => {
  const r = Reader()
  r.init();

  expect(r.script).toBe(r.uiScript);
});

test('saveSettings and loadSettings', () => {
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
