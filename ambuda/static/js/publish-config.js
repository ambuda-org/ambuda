import routes from './routes';
import { toHK, normalizeHK } from './sanskrit-search';

const DIACRITICS = {
  ś: 'sh',
  Ś: 'Sh',
  ṣ: 'sh',
  Ṣ: 'Sh',
  ā: 'a',
  Ā: 'A',
  ī: 'i',
  Ī: 'I',
  ū: 'u',
  Ū: 'U',
  ṛ: 'r',
  Ṛ: 'R',
  ṝ: 'r',
  Ṝ: 'R',
  ñ: 'n',
  Ñ: 'N',
  ṅ: 'n',
  Ṅ: 'N',
  ṇ: 'n',
  Ṇ: 'N',
  ṃ: 'm',
  Ṃ: 'M',
  ḥ: 'h',
  Ḥ: 'H',
  ṭ: 't',
  Ṭ: 'T',
  ḍ: 'd',
  Ḍ: 'D',
  ḷ: 'l',
  Ḷ: 'L',
};

const DIACRITICS_RE = new RegExp(`[${Object.keys(DIACRITICS).join('')}]`, 'g');

export function titleToSlug(str) {
  if (!str) return '';
  let s = toHK(str) || str;
  // HK nasals: G (ṅ) → n, J (ñ) → n, M (ṃ) → m before pavarga/zavarsa, else n
  s = s.replace(/G/g, 'n').replace(/J/g, 'n');
  s = s.replace(/M(?=[pbhzSs])/g, 'm').replace(/M/g, 'n');
  // HK uses z for ś and S for ṣ — replace before lowercasing
  s = s.replace(/z/g, 'sh').replace(/S/g, 'sh');
  s = s.toLowerCase();
  s = s.replace(DIACRITICS_RE, (ch) => DIACRITICS[ch] || ch);
  s = s.replace(/[^a-z0-9]+/g, '-');
  s = s.replace(/^-+|-+$/g, '');
  return s;
}

function createPicker(field, component, {
  getItems, displayValue, match, onSelect,
}) {
  const k = (suffix) => `_${field}_${suffix}`;

  return {
    displayValue(entry) {
      return entry[k('query')] !== undefined ? entry[k('query')] : displayValue(component, entry);
    },
    open(entry) {
      entry[k('open')] = true;
      entry[k('query')] = '';
      entry[k('sel')] = 0;
    },
    close(entry) {
      entry[k('open')] = false;
      entry[k('query')] = undefined;
    },
    search(entry, value) {
      entry[k('query')] = value;
      entry[k('sel')] = 0;
    },
    keydown(entry, e) {
      const items = this.filtered(entry);
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        entry[k('sel')] = Math.min((entry[k('sel')] || 0) + 1, items.length - 1);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        entry[k('sel')] = Math.max((entry[k('sel')] || 0) - 1, 0);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        this.select(entry, items[entry[k('sel')] || 0]);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        this.close(entry);
      }
    },
    filtered(entry) {
      const query = (entry[k('query')] || '').toLowerCase();
      const items = getItems(component);
      if (!query) return items;
      return items.filter((item) => match(item, query));
    },
    select(entry, item) {
      if (!item) return;
      onSelect(entry, item);
      this.close(entry);
    },
  };
}

export default () => ({
  config: { publish: [] },
  showJSON: false,
  filterHelpOpen: false,
  fields: [],
  languageLabels: window.LANGUAGE_LABELS || {},
  authors: window.AUTHOR_NAMES || [],
  newAuthorOpen: false,
  newAuthorName: '',
  allCollections: window.ALL_COLLECTIONS || [],
  allLanguages: null,
  pickers: {},

  init() {
    this.pickers = {
      lang: createPicker('lang', this, {
        getItems: (c) => {
          c.allLanguages ||= Object.entries(c.languageLabels)
            .map(([code, label]) => ({ code, label }));
          return c.allLanguages;
        },
        displayValue: (c, entry) => c.languageLabels[entry.language] || entry.language,
        match: (opt, query) => opt.label.toLowerCase().includes(query) || opt.code.includes(query),
        onSelect: (entry, opt) => { entry.language = opt.code; },
      }),
      author: createPicker('author', this, {
        getItems: (c) => c.authors,
        displayValue: (c, entry) => entry.author || '',
        match: (name, query) => {
          const lower = name.toLowerCase();
          return lower.includes(query) || toHK(name).toLowerCase().startsWith(query);
        },
        onSelect: (entry, name) => { entry.author = name; },
      }),
    };
    this.generateFieldsFromSchema();
    this.config = { publish: window.PUBLISH_CONFIG };
    this.config.publish.forEach((entry) => {
      this.fields.forEach((f) => {
        if (!(f.name in entry)) entry[f.name] = this.getDefaultValue(f);
      });
      entry.expanded = false;
    });
    this.allCollections.forEach((c) => {
      c._titleLower = c.title.toLowerCase();
      c._titleNorm = normalizeHK(toHK(c.title)).toLowerCase();
      c._parentLower = c.parent ? c.parent.toLowerCase() : '';
      c._parentNorm = c.parent ? normalizeHK(toHK(c.parent)).toLowerCase() : '';
    });
  },

  generateFieldsFromSchema() {
    const schema = window.PUBLISH_CONFIG_SCHEMA || {};
    const properties = schema.properties || {};
    const required = schema.required || [];
    const defs = schema.$defs || {};

    const fieldMetadata = {
      title: { placeholder: 'e.g., Rāmāyaṇa', description: 'Display title for the text' },
      slug: { placeholder: 'e.g., ramayana', description: 'Unique identifier for the text' },
      target: { placeholder: 'e.g., (page 1 10)', description: 'S-expression filter for block selection' },
      author: { placeholder: 'e.g., Vālmīki', description: 'Author of the work' },
      language: { placeholder: 'Search languages...', description: 'Primary language of the text' },
      parent_slug: { placeholder: 'e.g., ramayana', description: 'Slug of the parent text (for translations/commentaries)' },
    };

    const fieldOrder = ['title', 'slug', 'target', 'author', 'language', 'parent_slug'];
    const labels = { target: 'Filter' };
    const configFields = new Set(['target']);

    this.fields = fieldOrder
      .filter((name) => properties[name])
      .map((name) => {
        const prop = properties[name];
        let { type } = prop;
        let enumValues = prop.enum;

        if (prop.$ref) {
          const resolved = defs[prop.$ref.replace('#/$defs/', '')] || {};
          type ||= resolved.type;
          enumValues ||= resolved.enum;
        }
        if (prop.anyOf) {
          const nonNull = prop.anyOf.find((t) => t.type !== 'null');
          if (nonNull) { type = nonNull.type; enumValues = nonNull.enum; }
        }

        const meta = fieldMetadata[name] || {};
        return {
          name,
          label: labels[name] || this.titleCase(name),
          type,
          required: required.includes(name),
          enum: enumValues,
          placeholder: meta.placeholder || '',
          description: prop.description || meta.description || '',
          group: configFields.has(name) ? 'config' : 'text',
        };
      });
  },

  addAuthor() {
    const name = (this.newAuthorName || '').trim();
    if (!name) return;
    if (!this.authors.includes(name)) {
      this.authors.push(name);
      this.authors.sort();
    }
    this.newAuthorName = '';
    this.newAuthorOpen = false;
  },

  // -- Collections --

  collectionLabel(id) {
    const coll = this.allCollections.find((c) => c.id === id);
    if (!coll) return `#${id}`;
    return coll.parent ? `${coll.parent} → ${coll.title}` : coll.title;
  },

  filteredCollections(entry) {
    const query = (entry._coll_query || '').toLowerCase();
    const selected = entry.collection_ids || [];
    if (!query) {
      return this.allCollections.filter((c) => !selected.includes(c.id));
    }
    const qNorm = normalizeHK(toHK(query)).toLowerCase();
    return this.allCollections.filter((c) => {
      if (selected.includes(c.id)) return false;
      if (c._titleLower.includes(query) || c._titleNorm.includes(qNorm)) return true;
      if (c._parentLower
          && (c._parentLower.includes(query) || c._parentNorm.includes(qNorm))) {
        return true;
      }
      return false;
    });
  },

  addCollection(entry, id) {
    if (!entry.collection_ids) entry.collection_ids = [];
    if (!entry.collection_ids.includes(id)) {
      entry.collection_ids.push(id);
    }
  },

  removeCollection(entry, id) {
    if (!entry.collection_ids) return;
    entry.collection_ids = entry.collection_ids.filter((cid) => cid !== id);
  },

  // -- Auto-slug --

  onTitleInput(entry) {
    if (entry.slugManual) return;
    entry.slug = titleToSlug(entry.title);
  },

  onSlugInput(entry) {
    entry.slugManual = true;
  },

  // -- Slug validation --

  isDuplicateSlug(entry) {
    if (!entry.slug) return false;
    return this.config.publish.some((other) => other !== entry && other.slug === entry.slug);
  },

  hasDuplicateSlugs() {
    return this.config.publish.some((entry) => this.isDuplicateSlug(entry));
  },

  // -- Utilities --

  titleCase(str) {
    return str.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  },

  getDefaultValue(field) {
    if (field.type === 'boolean') return false;
    if (field.type === 'number' || field.type === 'integer') return null;
    return '';
  },

  getConfigLabel(entry) {
    if (entry.title && entry.slug) return `${entry.title} (${entry.slug})`;
    return entry.title || entry.slug || 'New config';
  },

  isEntryEmpty(entry) {
    return this.fields.every((f) => {
      const v = entry[f.name];
      return v === '' || v === null || v === undefined || v === false;
    });
  },

  addPublishEntry() {
    const newEntry = { expanded: true };
    this.fields.forEach((f) => { newEntry[f.name] = this.getDefaultValue(f); });
    this.config.publish.push(newEntry);
  },

  clonePublishEntry(index) {
    const source = this.config.publish[index];
    const clone = { ...JSON.parse(JSON.stringify(source)), _expanded: true };
    clone.title = '';
    clone.slug = '';
    clone.target = '';
    this.config.publish.splice(index + 1, 0, clone);
  },

  removePublishEntry(index) {
    const entry = this.config.publish[index];
    if (this.isEntryEmpty(entry) || window.confirm('Remove this configuration?')) {
      this.config.publish.splice(index, 1);
    }
  },

  getPreviewUrl(textSlug) {
    if (!textSlug) return '#';
    return routes.publishProjectText(window.PROJECT_SLUG, textSlug);
  },

  generateJSON() {
    const cleaned = this.config.publish.map((entry) => {
      const clean = {};
      this.fields.forEach((f) => {
        const v = entry[f.name];
        if (f.required || (v !== '' && v !== null && v !== undefined)) clean[f.name] = v;
      });
      if (entry.collection_ids && entry.collection_ids.length > 0) {
        clean.collection_ids = entry.collection_ids;
      }
      return clean;
    });
    return JSON.stringify(cleaned, null, 2);
  },

  copyJSON() {
    navigator.clipboard.writeText(this.generateJSON())
      .then(() => alert('Copied to clipboard!'))
      .catch((err) => console.error('Copy failed:', err));
  },

  submitForm(event) {
    if (this.hasDuplicateSlugs()) {
      alert('Please fix duplicate slugs before saving.');
      return;
    }
    this.$refs.hiddenConfig.value = this.generateJSON();
    event.target.submit();
  },
});
