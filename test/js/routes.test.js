import Routes from '@/routes';

test('ajaxDictionaryQuery', () => {
  expect(Routes.ajaxDictionaryQuery('mw', 'nara')).toBe('/api/dictionaries/mw/nara');
});

test('dictionaryQuery', () => {
  expect(Routes.dictionaryQuery('mw', 'nara')).toBe('/tools/dictionaries/mw/nara');
});

test('parseData', () => {
  expect(Routes.parseData('ramayana', '1.1')).toBe('/api/parses/ramayana/1.1');
});

test('getTextSlug', () => {
  Object.defineProperty(window, 'location', {
    value: {
      pathname: '/texts/ramayana/1.1',
    },
  });
  expect(Routes.getTextSlug()).toBe('ramayana');
});
