/* global Sanscript */

/**
 * Convert a string from Devanagari to Harvard-Kyoto transliteration.
 * Returns the original string if Sanscript is not available.
 */
export function toHK(str) {
  if (!str || typeof Sanscript === 'undefined') return str;
  return Sanscript.t(str, 'devanagari', 'hk');
}

/**
 * Normalize an HK string for fuzzy matching by collapsing similar sounds.
 * Strips whitespace, then: sh→s, z→s, aspirate→plain, RR→R, lR→l, G/J/M/m→n.
 */
const NORM_RE = /\s+|sh|([kgcjTDtdpb])h|RR|lR|[zGJMm]/g;
const NORM_MAP = { sh: 's', RR: 'R', lR: 'l', z: 's', G: 'n', J: 'n', M: 'n', m: 'n' };

export function normalizeHK(str) {
  return str
    .replace(/ee/g, 'i')
    .replace(/oo/g, 'u')
    .replace(/ou/g, 'au')
    .replace(/x/g, 'ks')
    .replace(NORM_RE, (match, aspirate) => {
      if (aspirate) return aspirate;
      return NORM_MAP[match] || '';
    });
}

/**
 * A text matcher for Sanskrit text.
 */
export function createSearchMatcher(items, getText) {
  const entries = items.map((item) => {
    const original = getText(item);
    const text = original.toLowerCase();
    const hk = toHK(original).toLowerCase();
    return { item, text, hk };
  });

  return {
    filter(query) {
      if (!query) return items;
      const q = query.toLowerCase();
      return entries
        .filter((e) => e.text.includes(q) || e.hk.includes(q))
        .map((e) => e.item);
    },
  };
}
