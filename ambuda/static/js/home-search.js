import { toHK, normalizeHK } from './sanskrit-search';

/**
 * Alpine component for the homepage search bar with fuzzy dropdown.
 * Expects a `items` binding: array of {title, slug}.
 */
export default (items) => ({
  query: '',
  results: [],
  selectedIndex: -1,
  open: false,
  entries: [],

  init() {
    if (items && items.length) {
      this._buildEntries(items);
    } else {
      fetch('/api/search-items')
        .then((r) => {
          if (!r.ok) throw new Error(r.status);
          return r.json();
        })
        .then((data) => this._buildEntries(data))
        .catch(() => {
          this.fallback = true;
        });
    }
  },

  fallback: false,

  _buildEntries(items) {
    this.entries = items.map((item) => {
      const text = item.title.toLowerCase();
      const norm = normalizeHK(toHK(item.title)).toLowerCase();
      const altTitleTexts = (item.alternate_titles || []).map((a) => a.toLowerCase());
      const altTitleNorms = (item.alternate_titles || []).map((a) =>
        normalizeHK(toHK(a)).toLowerCase(),
      );
      return { ...item, text, norm, altTitleTexts, altTitleNorms };
    });
  },

  /** True when the first character of the query is ASCII (roman input). */
  get useRoman() {
    return this.query.length > 0 && this.query.charCodeAt(0) < 128;
  },

  search() {
    if (!this.query) {
      this.results = [];
      this.open = false;
      return;
    }
    const q = this.query.toLowerCase();
    const qNorm = normalizeHK(toHK(this.query)).toLowerCase();
    this.results = this.entries
      .filter(
        (e) =>
          e.text.includes(q) ||
          e.norm.includes(qNorm) ||
          e.altTitleTexts.some((a) => a.includes(q)) ||
          e.altTitleNorms.some((a) => a.includes(qNorm)),
      )
      .map((e) => {
        // If the match is via an alternate title (not the main title), show it.
        let matchedAlt = null;
        if (!e.text.includes(q) && !e.norm.includes(qNorm)) {
          const idx = e.altTitleTexts.findIndex(
            (a, i) => a.includes(q) || e.altTitleNorms[i].includes(qNorm),
          );
          if (idx >= 0) matchedAlt = e.alternate_titles[idx];
        }
        return { ...e, matchedAlt };
      })
      .slice(0, 10);
    this.selectedIndex = -1;
    this.open = this.results.length > 0;
  },

  onKeydown(event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      if (this.open && this.selectedIndex >= 0) {
        this.go(this.results[this.selectedIndex].slug);
      } else if (this.open && this.results.length > 0) {
        this.go(this.results[0].slug);
      } else if (this.query) {
        window.location.href = '/search?q=' + encodeURIComponent(this.query);
      }
      return;
    }
    if (!this.open) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      this.selectedIndex = Math.min(this.selectedIndex + 1, this.results.length - 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
    } else if (event.key === 'Escape') {
      this.open = false;
    }
  },

  go(slug) {
    window.location.href = '/texts/' + slug + '/';
  },
});
