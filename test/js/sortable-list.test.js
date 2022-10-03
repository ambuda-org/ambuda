import { $ } from '@/core.ts';
import SortableList from '@/sortable-list';

const sampleHTML = `
<ul>
  <li data-key="a" data-bar="3" data-title="Title A">A</li>
  <li data-key="b" data-bar="1" data-title="Title B">B</li>
  <li data-key="c" data-bar="2" data-title="Title C">C</li>
</ul>
`;

beforeEach(() => {
  document.write(sampleHTML);
});

function getText(list) {
  return [...list.children].map(x => x.textContent);
}

test('SortableList can be created', () => {
  const s = SortableList('key');
  s.$refs = { list: document.querySelector('ul') };
  expect(s.field).toBe('key');
  expect(s.order).toBe('asc');
  assert

  const results = getText(s.$refs.list);
  expect(results).toEqual(['A', 'B', 'C']);
});

test('filter', () => {
  const s = SortableList('key');
  s.$refs = { list: document.querySelector('ul') };

  s.field = 'bar';
  s.order = 'desc'
  s.sort();

  const results = getText(s.$refs.list);
  expect(results).toEqual(['A', 'C', 'B']);
});

test('sort ascending', () => {
  const s = SortableList('key');
  s.$refs = { list: document.querySelector('ul') };

  s.field = 'bar';
  s.sort();

  const results = getText(s.$refs.list);
  expect(results).toEqual(['B', 'C', 'A']);
});


test('sort descending', () => {
  const s = SortableList('key');
  s.$refs = { list: document.querySelector('ul') };

  s.field = 'bar';
  s.order = 'desc'
  s.sort();

  const results = getText(s.$refs.list);
  expect(results).toEqual(['A', 'C', 'B']);
});
