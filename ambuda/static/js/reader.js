/* global Alpine */

/**
 * Application code for our Sanskrit reading environment.
 *
 * Our reading environment displays Sanskrit text with various rich features:
 *
 * - script, font size, and basic layout preferences
 * - padaccheda with word-by-word parse data
 * - dictionary search across a variety of standard dictionaries
 *
 *
 * # Design
 *
 * The reader is essentialy a single-page application (SPA) implemented in
 * Alpine. Certain components, such as text blocks and dictionary entries,
 * are rendered on the server and returned as HTML blobs.
 *
 *
 * # Technical terms
 *
 * - mula: the original verse (mūlam)
 * - slug: human-readable ID that appears in the URL.
 */

import { $ } from './core.ts';
import Routes from './routes';

export function getBlockSlug(blockID) {
  // Slice to remove text XML id.
  return blockID.split('.').slice(1).join('.');
}

/**
 * Split Devanagari text into aksharas (syllabic units).
 *
 * An akshara starts with a base character (vowel or consonant), absorbs any
 * virama+consonant conjuncts and combining marks, and may end with a bare
 * virama (halant). Non-Devanagari characters become individual tokens.
 */
export function toAksharas(text) {
  // akshara:    base (virama+consonant | combining)* virama?
  // base:       [\u0904-\u0939\u093D\u0950\u0958-\u0961\u0970-\u097F]
  // consonant:  [\u0915-\u0939\u0958-\u095F]
  // combining:  [\u0900-\u0903\u093C\u093E-\u094C\u094E-\u094F\u0951-\u0957\u0962-\u0963]
  return text.match(/[\u0904-\u0939\u093D\u0950\u0958-\u0961\u0970-\u097F](?:\u094D[\u0915-\u0939\u0958-\u095F]|[\u0900-\u0903\u093C\u093E-\u094C\u094E-\u094F\u0951-\u0957\u0962-\u0963])*\u094D?|[\s\S]/g) || [];
}

const READER_CONFIG_KEY = 'reader';

export default () => ({

  // User settings
  // -------------
  // Persistent user-specific data that we store in localStorage.

  // Text size for body text.
  fontSize: 'md:text-xl',
  textWidth: 'md:max-w-xl',
  // The dictionary sources to use when fetching.
  dictSources: ['mw'],
  sidebarWidth: 512,
  userScript: 'devanagari',

  // Server data
  // -----------
  // Text or dictionary data fetched from the server.

  data: {
    text_title: null,
    section_title: null,
    section_slug: null,
    blocks: [],
    prev_url: null,
    next_url: null,
  },

  // The current dictionary response.
  dictionaryResponse: null,
  // The current grammar (kosha) response.
  grammarResponse: null,
  // Grammar detail (dhatu/krt) fragment loaded inline.
  grammarDetailResponse: null,
  // Analysis of a word clicked by the user.
  wordAnalysis: { form: null, lemma: null, parse: null },
  analyzeData: {
    blockSlug: null, words: [], error: null, loading: false,
  },
  // Active sub-tab within the word-detail view ('meaning' or 'grammar').
  wordDetailTab: 'meaning',

  // Transient data
  // --------------
  // Internal application data that manages the application state.

  // If true, show the sidebar.
  showSidebar: true,
  sidebarTab: null,
  // Help banner for new users.
  showHelpBanner: !localStorage.getItem('reader-help-dismissed'),
  // Text in the dictionary search field.
  dictQuery: '',
  // If true, show the dictionary selection widget.
  showDictSourceSelector: false,
  sectionSlug: null,
  // Enabled inline translations, keyed by translation slug.
  // Value is the fetched data { [blockSlug]: html } or `true` while loading.
  enabledTranslations: {},

  init() {
    this.loadSettings();
    this.userScript = this.$root.dataset.script || 'devanagari';
    this.data = JSON.parse(document.getElementById('payload').textContent);
    this.sectionSlug = this.data.section_slug;

    window.history.replaceState({ sectionSlug: this.sectionSlug }, '', window.location.href);
    window.addEventListener('popstate', (e) => this.onPopState(e));
    this.$nextTick(() => this.insertSoftHyphensInDOM());
  },

  /** Load user settings from local storage. */
  loadSettings() {
    const settingsStr = localStorage.getItem(READER_CONFIG_KEY);
    if (settingsStr) {
      try {
        const settings = JSON.parse(settingsStr);
        this.fontSize = settings.fontSize || this.fontSize;
        this.textWidth = settings.textWidth || this.textWidth;
        this.dictSources = settings.dictSources || this.dictSources;
        this.sidebarWidth = settings.sidebarWidth || this.sidebarWidth;
        if (settings.showSidebar !== undefined) this.showSidebar = settings.showSidebar;
      } catch (error) {
        // Old settings are invalid -- rewrite with valid values.
        this.saveSettings();
      }
    }
  },

  /** Save user settings to local storage. */
  saveSettings() {
    const settings = {
      fontSize: this.fontSize,
      textWidth: this.textWidth,
      dictSources: this.dictSources,
      sidebarWidth: this.sidebarWidth,
      showSidebar: this.showSidebar,
    };
    localStorage.setItem(READER_CONFIG_KEY, JSON.stringify(settings));
  },

  async changeScript(newScript) {
    await fetch(`/script/${newScript}`);
    this.userScript = newScript;

    this.dictionaryResponse = null;
    this.wordAnalysis = { form: null, lemma: null, parse: null };
    this.analyzeData = {
      blockSlug: null, words: [], error: null, loading: false,
    };

    const resp = await fetch(`/api/texts/${Routes.getTextSlug()}/${this.sectionSlug}`);
    if (!resp.ok) return;
    this.data = await resp.json();
    this.$nextTick(() => this.insertSoftHyphensInDOM());
    this.refreshTranslations();
  },

  insertSoftHyphensInDOM() {
    function walk(node) {
      if (node.nodeType === Node.TEXT_NODE) {
        node.nodeValue = toAksharas(node.nodeValue).join('\u00AD');
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        node.childNodes.forEach((child) => walk(child));
      }
    }
    document.querySelectorAll('s-p').forEach(walk);
  },

  refreshTranslations() {
    Object.keys(this.enabledTranslations).forEach((slug) => {
      this.fetchTranslation(slug);
    });
  },

  async navigateToSection(url, pushState) {
    try {
      const resp = await fetch(`/api${url}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const newData = await resp.json();

      this.data = newData;
      this.sectionSlug = newData.section_slug;

      if (pushState) {
        window.history.pushState({ sectionSlug: this.sectionSlug }, '', url);
      }

      const title = newData.section_title
        ? `${newData.text_title} ${newData.section_title} | Ambuda`
        : `${newData.text_title} | Ambuda`;
      document.title = title;

      const textPanel = document.querySelector('article > div');
      if (textPanel) textPanel.scrollTop = 0;

      this.$nextTick(() => this.insertSoftHyphensInDOM());
      this.refreshTranslations();
    } catch {
      window.location.href = url;
    }
  },

  goToPrev() {
    if (this.data.prev_url) {
      this.navigateToSection(this.data.prev_url, true);
    }
  },

  goToNext() {
    if (this.data.next_url) {
      this.navigateToSection(this.data.next_url, true);
    }
  },

  navigateToTocEntry(url) {
    this.navigateToSection(url, true);
  },

  onPopState(event) {
    const slug = event.state?.sectionSlug;
    if (slug && slug !== this.sectionSlug) {
      this.navigateToSection(window.location.pathname, false);
    }
  },

  /** Query the dictionary and populate the sidebar. */
  async searchDictionary() {
    if (!this.dictQuery || this.dictSources.length === 0) {
      return;
    }
    const baseUrl = Routes.ajaxDictionaryQuery(this.dictSources, this.dictQuery);
    const url = `${baseUrl}?script=${this.userScript}`;
    const resp = await fetch(url);
    if (resp.ok) {
      this.dictionaryResponse = await resp.text();
    } else {
      this.dictionaryResponse = '<p>Sorry, this content is not available right now.</p>';
    }
  },

  async fetchGrammar(form, lemma, parse) {
    const url = Routes.ajaxBharatiGrammar(form, lemma, parse);
    const resp = await fetch(url);
    if (resp.ok) {
      this.grammarResponse = await resp.text();
    } else {
      this.grammarResponse = '<p>No grammar data available.</p>';
    }
  },

  async onClickGrammar(e) {
    const dhatuEl = e.target.closest('[data-grammar-dhatu]');
    if (dhatuEl) {
      e.preventDefault();
      const spec = dhatuEl.dataset.grammarDhatu;
      const url = `/api/bharati/dhatu/${encodeURIComponent(spec)}`;
      const resp = await fetch(url);
      this.grammarDetailResponse = resp.ok
        ? await resp.text()
        : '<p>Could not load root data.</p>';
      return;
    }

    const krtEl = e.target.closest('[data-grammar-krt]');
    if (krtEl) {
      e.preventDefault();
      const value = krtEl.dataset.grammarKrt;
      const url = `/api/bharati/krt/${encodeURIComponent(value)}`;
      const resp = await fetch(url);
      this.grammarDetailResponse = resp.ok
        ? await resp.text()
        : '<p>Could not load suffix data.</p>';
    }
  },

  async fetchBlockParse(blockSlug) {
    const url = Routes.parseData(Routes.getTextSlug(), blockSlug);
    let resp;
    try {
      resp = await fetch(url);
    } catch {
      return [null, false];
    }

    if (resp.ok) {
      const html = await resp.text();
      return [html, true];
    }
    if (resp.status === 404) {
      return ['<p>Sorry, we don\'t have an analysis for this text.</p>', false];
    }
    return ['<p>Sorry, this content is not available right now. (Server error)</p>', false];
  },

  // Click handlers
  // ==============

  /** Generic click handler for multiple objects in the reader. */
  async onClick(e) {
    const $word = e.target.closest('s-w');
    if ($word) {
      this.onClickWord($word);
      return;
    }

    if (e.target.closest('button, a')) {
      return;
    }

    const $block = e.target.closest('s-block');
    if ($block) {
      this.onClickBlock($block.dataset.slug);
    }
  },

  async onClickBlock(blockSlug) {
    const block = this.data.blocks.find((b) => b.slug === blockSlug);

    if (block.analyzeWords) {
      this.analyzeData = { blockSlug, words: block.analyzeWords, error: null };
      this.sidebarTab = 'analyze';
      this.showSidebar = true;
      return;
    }

    // Show sidebar immediately with loading state
    this.analyzeData = {
      blockSlug, words: [], error: null, loading: true,
    };
    this.sidebarTab = 'analyze';
    this.showSidebar = true;

    const [html, ok] = await this.fetchBlockParse(blockSlug);
    if (ok) {
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const words = Array.from(doc.querySelectorAll('s-w'), (el) => ({
        form: el.textContent,
        lemma: el.getAttribute('lemma'),
        parse: el.getAttribute('parse'),
      }));
      block.analyzeWords = words;
      this.analyzeData = { blockSlug, words, error: null };
    } else {
      this.analyzeData = { blockSlug: null, words: [], error: html };
    }
  },

  lookupAnalyzeWord(word) {
    this.dictQuery = word.lemma;
    this.wordAnalysis = { form: word.form, lemma: word.lemma, parse: word.parse };
    this.wordDetailTab = 'meaning';
    this.grammarDetailResponse = null;
    this.sidebarTab = 'word-detail';
    this.searchDictionary();
    this.fetchGrammar(word.form, word.lemma, word.parse);
  },

  async onClickWord($word) {
    const form = $word.textContent;
    const lemma = $word.getAttribute('lemma');
    const parse = $word.getAttribute('parse');

    this.dictQuery = lemma;
    await this.searchDictionary();

    this.wordAnalysis = { form, lemma, parse };
    this.sidebarTab = 'lookup';
    this.showSidebar = true;
  },

  // Dropdown handlers
  // =================

  /** Toggle the source selection widget's visibility. */
  toggleSourceSelector() {
    this.showDictSourceSelector = !this.showDictSourceSelector;
  },

  /** Close the source selection widget and re-run the query as needed. */
  onClickOutsideOfSourceSelector() {
    // NOTE: With our current bindings, this method will run *every* time we
    // click outside of the selector even if the selector is not open. If the
    // selector is not visible, this method is best left as a no-op.
    if (this.showDictSourceSelector) {
      this.saveSettings();
      this.searchDictionary();
      this.showDictSourceSelector = false;
    }
  },

  startResizeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const DEFAULT_W = 512;
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';

    const onMouseMove = (e) => {
      const w = window.innerWidth - e.clientX;
      const maxW = Math.floor(window.innerWidth * 0.75);
      const halfW = Math.floor(window.innerWidth * 0.5);
      let snapped = w;
      if (Math.abs(w - DEFAULT_W) < 20) snapped = DEFAULT_W;
      else if (Math.abs(w - halfW) < 20) snapped = halfW;
      this.sidebarWidth = Math.max(280, Math.min(maxW, snapped));
      sidebar.style.width = `${this.sidebarWidth}px`;
    };

    const onMouseUp = () => {
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      this.saveSettings();
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  },

  // Translation handlers
  // ====================

  async toggleTranslation(slug) {
    if (this.enabledTranslations[slug]) {
      delete this.enabledTranslations[slug];
    } else {
      this.enabledTranslations[slug] = true;
      await this.fetchTranslation(slug);
    }
  },

  async fetchTranslation(slug) {
    const url = `/api/translations/${slug}/${this.sectionSlug}`;
    try {
      const resp = await fetch(url);
      if (resp.ok) {
        this.enabledTranslations[slug] = await resp.json();
      } else {
        delete this.enabledTranslations[slug];
      }
    } catch {
      delete this.enabledTranslations[slug];
    }
  },

  translationsFor(blockSlug) {
    return Object.entries(this.enabledTranslations)
      .filter(([, data]) => data && typeof data === 'object' && data[blockSlug])
      .map(([slug, data]) => ({ slug, html: data[blockSlug] }));
  },

  // Help banner handlers
  // ====================

  dismissHelpBanner() {
    this.showHelpBanner = false;
    localStorage.setItem('reader-help-dismissed', '1');
  },

  openSettingsFromBanner() {
    this.dismissHelpBanner();
    this.showSidebar = true;
    this.sidebarTab = 'settings';
    this.saveSettings();
  },

  // Bookmark handlers
  // =================

  /** Toggle a bookmark on a text block. */
  async toggleBookmark(blockSlug, event) {
    event.preventDefault();
    event.stopPropagation();

    try {
      const resp = await fetch('/api/bookmarks/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ block_slug: blockSlug }),
      });

      if (!resp.ok) {
        const error = await resp.json();
        if (resp.status === 401) {
          alert('Please log in to bookmark verses'); // eslint-disable-line no-alert
        } else {
          alert(`Failed to toggle bookmark: ${error.error || 'Unknown error'}`); // eslint-disable-line no-alert
        }
      }
    } catch {
      alert('Failed to toggle bookmark'); // eslint-disable-line no-alert
    }
  },
});
