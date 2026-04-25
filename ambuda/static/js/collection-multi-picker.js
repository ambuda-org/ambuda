import { toHK, normalizeHK } from './sanskrit-search';

const norm = (s) => normalizeHK(toHK(s || '')).toLowerCase();

/**
 * Alpine component for a multi-select collection picker with chips +
 * Devanagari/Roman fuzzy search. Use as
 * `x-data="collectionMultiPicker(items, initialIds)"`.
 *
 * `items` is an array of {id, title, parent} objects.
 */
export default (items, initialIds = []) => {
  const indexed = items.map((c) => ({
    ...c,
    _searchTitle: String(c.title || '').toLowerCase(),
    _searchTitleNorm: norm(c.title),
    _searchParent: c.parent ? String(c.parent).toLowerCase() : '',
    _searchParentNorm: c.parent ? norm(c.parent) : '',
    _label: c.parent ? `${c.parent} → ${c.title}` : c.title,
  }));

  return {
    items: indexed,
    selectedIds: [...initialIds],
    query: '',
    open: false,

    label(id) {
      const c = this.items.find((it) => it.id === id);
      return c ? c._label : `#${id}`;
    },

    filtered() {
      const q = this.query.toLowerCase();
      const qNorm = norm(this.query);
      return this.items.filter((c) => {
        if (this.selectedIds.includes(c.id)) return false;
        if (!this.query) return true;
        return (
          c._searchTitle.includes(q) ||
          c._searchTitleNorm.includes(qNorm) ||
          c._searchParent.includes(q) ||
          c._searchParentNorm.includes(qNorm)
        );
      });
    },

    add(id) {
      if (!this.selectedIds.includes(id)) this.selectedIds.push(id);
      this.query = '';
    },

    remove(id) {
      this.selectedIds = this.selectedIds.filter((x) => x !== id);
    },

    onClickAway() {
      this.open = false;
    },
  };
};
