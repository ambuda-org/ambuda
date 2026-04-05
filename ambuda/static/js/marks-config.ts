export interface InlineMarkConfig {
  name: string;
  emoji: string;
  label: string;
  className: string;
  group: string;
  excludes?: string;
}

// Keep in sync with ambuda/utils/project_structuring.py::InlineType
export const INLINE_MARKS: InlineMarkConfig[] = [
  {
    name: 'error',
    emoji: '⛔',
    label: 'Error',
    className: 'pm-error',
    group: 'general',
    excludes: 'fix',
  },
  {
    name: 'fix',
    emoji: '✅',
    label: 'Fix',
    className: 'pm-fix',
    group: 'general',
    excludes: 'error',
  },
  {
    name: 'flag',
    emoji: '?',
    label: 'Unclear',
    className: 'pm-flag',
    group: 'general',
  },
  {
    name: 'ref',
    emoji: '🦶',
    label: 'Footnote number',
    className: 'pm-ref',
    group: 'general',
    excludes: '_',
  },
  {
    name: 'stage',
    emoji: '🎬',
    label: 'Stage direction',
    className: 'pm-stage',
    group: 'plays',
    excludes: 'speaker',
  },
  {
    name: 'speaker',
    emoji: '📣',
    label: 'Speaker',
    className: 'pm-speaker',
    group: 'plays',
    excludes: 'stage',
  },
  {
    name: 'chaya',
    emoji: '🌒',
    label: 'Chaya',
    className: 'pm-chaya',
    group: 'plays',
    excludes: 'speaker',
  },
  {
    name: 'prakrit',
    emoji: '☀️',
    label: 'Prakrit',
    className: 'pm-prakrit',
    group: 'plays',
    excludes: 'speaker',
  },
  {
    name: 'bold',
    emoji: 'B',
    label: 'Term (bold)',
    className: 'pm-bold',
    group: 'advanced',
  },
  {
    name: 'italic',
    emoji: 'I',
    label: 'Term (italic)',
    className: 'pm-italic',
    group: 'advanced',
  },
  {
    name: 'note',
    emoji: '📝',
    label: 'Internal note',
    className: 'pm-note',
    group: 'advanced',
    excludes: '_',
  },
  {
    name: 'add',
    emoji: '+',
    label: 'Added in source',
    className: 'pm-add',
    group: 'advanced',
  },
  {
    name: 'ellipsis',
    emoji: '\u2026',
    label: 'Omitted in source',
    className: 'pm-ellipsis',
    group: 'advanced',
  },
  {
    name: 'delete',
    emoji: '🗑',
    label: 'Deleted in source',
    className: 'pm-delete',
    group: 'advanced',
  },
  {
    name: 'quote',
    emoji: '💬',
    label: 'Quote',
    className: 'pm-quote',
    group: 'advanced',
  },
];

export const MARK_GROUPS = [
  { key: 'general', label: 'general' },
  { key: 'plays', label: 'plays' },
  { key: 'advanced', label: 'advanced' },
];

export type MarkName = typeof INLINE_MARKS[number]['name'];

export function getAllMarkNames(): string[] {
  return INLINE_MARKS.map((m) => m.name);
}
