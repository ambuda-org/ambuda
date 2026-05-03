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
 * Single-pass replacement using a combined regex and lookup table.
 */
const _NORM_MAP = {
  ee: 'i',
  oo: 'u',
  ou: 'au',
  x: 'ks',
  ' ': '',
  sh: 's',
  z: 's',
  kh: 'k',
  gh: 'g',
  ch: 'c',
  jh: 'j',
  Th: 'T',
  Dh: 'D',
  th: 't',
  dh: 'd',
  ph: 'p',
  bh: 'b',
  RR: 'R',
  lR: 'l',
  G: 'n',
  J: 'n',
  M: 'n',
  m: 'n',
};
const _NORM_RE = new RegExp(
  Object.keys(_NORM_MAP)
    .sort((a, b) => b.length - a.length)
    .join('|'),
  'g',
);

export function normalizeHK(str) {
  return str.replace(_NORM_RE, (m) => _NORM_MAP[m]);
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
