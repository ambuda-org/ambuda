import { normalizeHK } from '@/sanskrit-search';

describe('normalizeHK', () => {
  test('z → s', () => {
    expect(normalizeHK('ziva')).toBe('siva');
  });

  test('sh → s', () => {
    expect(normalizeHK('shiva')).toBe('siva');
  });

  test('aspiration removed', () => {
    expect(normalizeHK('kha')).toBe('ka');
    expect(normalizeHK('gha')).toBe('ga');
    expect(normalizeHK('cha')).toBe('ca');
    expect(normalizeHK('jha')).toBe('ja');
    expect(normalizeHK('Tha')).toBe('Ta');
    expect(normalizeHK('Dha')).toBe('Da');
    expect(normalizeHK('tha')).toBe('ta');
    expect(normalizeHK('dha')).toBe('da');
    expect(normalizeHK('pha')).toBe('pa');
    expect(normalizeHK('bha')).toBe('ba');
  });

  test('RR → R', () => {
    expect(normalizeHK('RR')).toBe('R');
  });

  test('lR → l', () => {
    expect(normalizeHK('lR')).toBe('l');
  });

  test('G, J, M → n', () => {
    expect(normalizeHK('aGga')).toBe('anga');
    expect(normalizeHK('paJca')).toBe('panca');
    expect(normalizeHK('saMskRtam')).toBe('sanskRtan');
  });

  test('m → n', () => {
    expect(normalizeHK('ram')).toBe('ran');
  });

  test('whitespace is stripped', () => {
    expect(normalizeHK('bhagavad gItA')).toBe(normalizeHK('bhagavadgItA'));
    expect(normalizeHK('rAma  carita')).toBe(normalizeHK('rAmacarita'));
  });

  test('mahAbhAratam matches normalized variants after lowercasing', () => {
    const norm = (s) => normalizeHK(s).toLowerCase();
    const canonical = norm('mahAbhAratam');
    expect(canonical).toBe('nahabaratan');
    expect(norm('mahabaratam')).toBe(canonical);
    expect(norm('mahabaratham')).toBe(canonical);
  });

  test('saMdeza variants all normalize the same', () => {
    const norm = (s) => normalizeHK(s).toLowerCase();
    const canonical = norm('saMdeza');
    expect(norm('sandeza')).toBe(canonical);
    expect(norm('sandesha')).toBe(canonical);
    expect(norm('saMdesha')).toBe(canonical);
    expect(norm('sandesa')).toBe(canonical);
  });

  test('space invariant: "bhagavad gItA" matches "bhagavadgItA"', () => {
    const norm = (s) => normalizeHK(s).toLowerCase();
    expect(norm('bhagavad gItA')).toBe(norm('bhagavadgItA'));
  });

  test('ee → i (casual long i)', () => {
    expect(normalizeHK('geeta')).toBe('gita');
    expect(normalizeHK('mahAbhAratam')).toBe(normalizeHK('mahAbhAratam'));
  });

  test('oo → u (casual long u)', () => {
    expect(normalizeHK('roopa')).toBe('rupa');
  });

  test('x → ks', () => {
    expect(normalizeHK('laxmi')).toBe('laksni');
  });

  test('ou → au (casual diphthong)', () => {
    expect(normalizeHK('koustubha')).toBe('kaustuba');
  });

  test('casual romanization: "bhagavad geeta" matches "bhagavadgItA"', () => {
    const norm = (s) => normalizeHK(s).toLowerCase();
    expect(norm('bhagavad geeta')).toBe(norm('bhagavadgItA'));
  });
});
