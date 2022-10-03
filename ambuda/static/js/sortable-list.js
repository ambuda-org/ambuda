function sortAscending(field) {
  return (a, b) => (a.dataset[field] < b.dataset[field] ? -1 : 1);
}

function sortDescending(field) {
  return (a, b) => (a.dataset[field] < b.dataset[field] ? 1 : -1);
}

/**
 * A simple sortable table.
 *
 * FIXME: this class is a kludge of data in markup (through data- attributes)
 * and data in JS (through `this.data`). If we need to add more features here,
 * clean it up properly first.
 */
export default (defaultField) => ({
  // The sort field. Initialize this in `x-data`.
  field: defaultField,
  // The query to filter by. If empty, use all data.
  query: '',
  // The order of the sort ("asc" or "desc").
  order: 'asc',
  // The keys to display.
  displayed: new Set(),
  // A simplified representation of the project data.
  data: [],

  init() {
    const { list } = this.$refs;
    this.data = [...list.children].map((x) => ({
      key: x.dataset.key,
      // Store title in lowercase to support case-insensitive searching
      title: x.dataset.title.toLowerCase(),
    }));
    // Collect all keys in `this.displayed`.
    this.displayed = new Set([...list.children].map((x) => x.dataset.key));
  },

  /** Filter the list by the user's query string. */
  filter() {
    if (!this.query) return;

    const query = this.query.toLowerCase();
    // toLowerCase for case-insensitive matching.
    const newKeys = this.data
          .filter((x) => x.title.includes(query))
          .map((x) => x.key);
    this.displayed = new Set(newKeys);
  },

  /** Sort the filtered list by field `this.field` in order `this.order`. */
  sort() {
    const orderFn = this.order === 'asc' ? sortAscending : sortDescending;
    const { list } = this.$refs;
    [...list.children]
      .sort(orderFn(this.field))
      .forEach((node) => list.appendChild(node));
  },
});
