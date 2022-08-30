function sortAscending(field) {
  return (a, b) => (a.dataset[field] < b.dataset[field] ? -1 : 1);
}

function sortDescending(field) {
  return (a, b) => (a.dataset[field] < b.dataset[field] ? 1 : -1);
}

export default (defaultField) => ({
  // The sort field. Initialize this in `x-init`.
  field: defaultField,
  // The order ("asc" or "desc"). Initialize this in `x-init`.
  order: 'asc',

  sort() {
    const orderFn = this.order === 'asc' ? sortAscending : sortDescending;
    const { list } = this.$refs;
    [...list.children]
      .sort(orderFn(this.field))
      .forEach((node) => list.appendChild(node));
  },
});
