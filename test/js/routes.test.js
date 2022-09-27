import Routes from '@/routes';

beforeEach(() => {
  // I was not able to redefine the property after the first definition.
  // Instead, define it once then use simple assignment in each test.
  Object.defineProperty(window, 'location', {
    value: { pathname: '' },
  });
});

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
  window.location.pathname = '/texts/ramayana/1.1';
  expect(Routes.getTextSlug()).toBe('ramayana');
});

test('parseDictionaryURL returns fields with valid URL', () => {
  window.location.pathname = '/tools/dictionaries/apte/deva',
  expect(Routes.parseDictionaryURL()).toEqual({ source: "apte", query: "deva" });
});

test('parseDictionaryURL returns nulls with invalid URL', () => {
  window.location.pathname = '/tools/dictionaries/',
  expect(Routes.parseDictionaryURL()).toEqual({ source: null, query: null });
});
