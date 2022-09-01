import { $ } from '@/core.ts';
import SortableList from '@/sortable-list';

const sampleHTML = `
<ul>
  <li data-foo="a" data-bar="3">A</li>
  <li data-foo="b" data-bar="1">B</li>
  <li data-foo="c" data-bar="2">C</li>
</ul>
`;

beforeEach(() => {
  document.write(sampleHTML);
});

function getText(list) {
  return [...list.children].map(x => x.textContent);
}

test('SortableList can be created', () => {
  const s = SortableList('foo');
  s.$refs = { list: document.querySelector('ul') };
  expect(s.field).toBe('foo');
  expect(s.order).toBe('asc');

  const results = getText(s.$refs.list);
  expect(results).toEqual(['A', 'B', 'C']);
});

test('sort ascending', () => {
  const s = SortableList('foo');
  s.$refs = { list: document.querySelector('ul') };

  s.field = 'bar';
  s.sort();

  const results = getText(s.$refs.list);
  expect(results).toEqual(['B', 'C', 'A']);
});


test('sort descending', () => {
  const s = SortableList('foo');
  s.$refs = { list: document.querySelector('ul') };

  s.field = 'bar';
  s.order = 'desc'
  s.sort();

  const results = getText(s.$refs.list);
  expect(results).toEqual(['A', 'C', 'B']);
});
