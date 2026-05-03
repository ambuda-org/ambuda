import { toHK, normalizeHK } from './sanskrit-search';

const norm = (s) => normalizeHK(toHK(s || '')).toLowerCase();

/**
 * Reusable Alpine component: input + dropdown + fuzzy search with
 * Devanagari/Roman matching. Use as `x-data="searchablePicker(items, opts)"`.
 *
 * `items` is an array of objects. `opts` keys:
 *   labelKey: property name to display and match against (default 'label')
 *   valueKey: property name to use as the selected value (default 'value')
 *   extraKey: optional secondary property to also match against (e.g., a code)
 *   initialValue: initial selected value
 *   placeholder: input placeholder
 */
export default (items, options = {}) => {
  const labelKey = options.labelKey || 'label';
  const valueKey = options.valueKey || 'value';
  const { extraKey } = options;
  const { initialValue } = options;
  const placeholder = options.placeholder || '';

  return {
    items,
    placeholder,
    open: false,
    sel: 0,
    query: '',
    selectedValue: initialValue ?? '',
    selectedLabel: '',

    init() {
      const v = String(this.selectedValue ?? '');
      const initial = this.items.find((it) => String(it[valueKey]) === v);
      this.selectedLabel = initial ? String(initial[labelKey] ?? '') : '';
    },

    /** What the visible <input> displays. While open, show what they're
     *  typing (empty after focus). When closed, show the selection. */
    display() {
      return this.open ? this.query : this.selectedLabel;
    },

    filtered() {
      if (!this.query) return this.items;
      const q = this.query.toLowerCase();
      const qNorm = norm(this.query);
      return this.items.filter((item) => {
        const label = String(item[labelKey] || '').toLowerCase();
        const labelNorm = norm(item[labelKey]);
        const extra = extraKey ? String(item[extraKey] || '').toLowerCase() : '';
        return label.includes(q) || labelNorm.includes(qNorm) || extra.includes(q);
      });
    },

    pick(item) {
      if (!item) return;
      this.selectedValue = item[valueKey];
      this.selectedLabel = String(item[labelKey] ?? '');
      this.query = '';
      this.open = false;
      this.sel = 0;
    },

    onFocus() {
      this.open = true;
      this.query = '';
      this.sel = 0;
    },

    onClickAway() {
      this.open = false;
      this.query = '';
    },

    onInput(value) {
      this.query = value;
      this.sel = 0;
      this.open = true;
    },

    onKeydown(e) {
      const items = this.filtered();
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        this.sel = Math.min(this.sel + 1, items.length - 1);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        this.sel = Math.max(this.sel - 1, 0);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (items[this.sel]) this.pick(items[this.sel]);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        this.open = false;
        this.query = '';
      }
    },
  };
};
