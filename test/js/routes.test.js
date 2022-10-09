import Routes from '@/routes';

beforeEach(() => {
  // I was not able to redefine the property after the first definition.
  // Instead, define it once then use simple assignment in each test.
  Object.defineProperty(window, 'location', {
    value: { pathname: '' },
  });
});

test('ajaxDictionaryQuery', () => {
  const sources = ['apte', 'mw'];
  expect(Routes.ajaxDictionaryQuery(sources, 'nara')).toBe('/api/dictionaries/apte,mw/nara');
});

test('dictionaryQuery', () => {
  const sources = ['apte', 'mw'];
  expect(Routes.dictionaryQuery(sources, 'nara')).toBe('/tools/dictionaries/apte,mw/nara');
});

test('parseData', () => {
  expect(Routes.parseData('ramayana', '1.1')).toBe('/api/parses/ramayana/1.1');
});

test('getTextSlug', () => {
  window.location.pathname = '/texts/ramayana/1.1';
  expect(Routes.getTextSlug()).toBe('ramayana');
});

test('parseDictionaryURL returns fields with a valid single-source URL', () => {
  window.location.pathname = '/tools/dictionaries/apte/deva',
  expect(Routes.parseDictionaryURL()).toEqual({ sources: ["apte"], query: "deva" });
});

test('parseDictionaryURL returns fields with a valid multi-source URL', () => {
  window.location.pathname = '/tools/dictionaries/apte,mw/deva',
  expect(Routes.parseDictionaryURL()).toEqual({ sources: ["apte", "mw"], query: "deva" });
});

test('parseDictionaryURL returns nulls with an invalid URL', () => {
  window.location.pathname = '/tools/dictionaries/',
  expect(Routes.parseDictionaryURL()).toEqual({ sources: null, query: null });
});
