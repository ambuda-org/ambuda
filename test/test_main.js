QUnit.module('URL', () => {
  QUnit.test('route', (assert) => {
    const eq = assert.equal.bind(assert);
    eq(URL.ajaxDictionaryQuery('mw', 'nara'), '/api/dictionaries/mw/nara');
    eq(URL.dictionaryQuery('mw', 'nara'), '/tools/dictionaries/mw/nara');
    eq(URL.parseData('ramayanam', '1.1.1'), '/api/parses/ramayanam/1.1.1');
  });
});

QUnit.module('ParseLayer', () => {
  QUnit.test('getBlockSlug', (assert) => {
    assert.equal(ParseLayer.getBlockSlug('R.1.1.1'), '1.1.1');
  });
});
