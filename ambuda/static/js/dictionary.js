import {
  transliterateElement, transliterateHTMLString, $,
} from './core.ts';
import Routes from './routes';

// The key to use when storing the dictionary config in local storage.
const DICTIONARY_CONFIG_KEY = 'dictionary';
// The maximum number of queries to keep in `this.history`.
const HISTORY_SIZE = 10;

export default () => ({
  // The script to use for Sanskrit text.
  script: 'devanagari',
  // The dictionary sources to use.
  sources: ['mw'],

  // (transient data)

  // Script value as stored on the <select> widget. We store this separately
  // from `script` since we currently need to know both fields in order to
  // transliterate.
  uiScript: null,
  // The current query.
  query: '',
  // The user's search history, from least to most recent.
  history: [],
  // If true, show the source selection widget.
  showSourceSelector: false,

  init() {
    // URL settings take priority.
    this.loadSettingsFromURL();
    this.loadSettings();
    this.transliterate('devanagari', this.script);
  },

  /** Load source and query from the URL (if defined). */
  loadSettingsFromURL() {
    const { query, sources } = Routes.parseDictionaryURL();
    this.query = query || this.query;
    this.sources = sources || this.sources;
  },

  loadSettings() {
    const settingsStr = localStorage.getItem(DICTIONARY_CONFIG_KEY);
    if (settingsStr) {
      try {
        const settings = JSON.parse(settingsStr);
        this.script = settings.script || this.script;
        this.sources = settings.sources || this.sources;
        this.uiScript = this.script;
      } catch (error) {
        // Old settings are invalid -- rewrite with valid values.
        this.saveSettings();
      }
    }
  },

  saveSettings() {
    const settings = {
      script: this.script,
      sources: this.sources,
    };
    localStorage.setItem(DICTIONARY_CONFIG_KEY, JSON.stringify(settings));
  },

  async updateSource() {
    this.saveSettings();
    // Return the promise so we can await it in tests.
    return this.searchDictionary(this.query);
  },

  updateScript() {
    this.transliterate(this.script, this.uiScript);
    this.script = this.uiScript;
    this.saveSettings();
  },

  async searchDictionary() {
    if (!this.query) {
      return;
    }

    const url = Routes.ajaxDictionaryQuery(this.sources, this.query);
    const $container = $('#dict--response');
    const resp = await fetch(url);

    if (resp.ok) {
      const text = await resp.text();
      $container.innerHTML = transliterateHTMLString(text, this.script);
      // Update search history after the fetch so that the history widget
      // renders in sync with the main content.
      this.addToHistory(this.query);

      const newURL = Routes.dictionaryQuery(this.sources, this.query);
      window.history.replaceState({}, '', newURL);
    } else {
      $container.innerHTML = '<p>Sorry, this content is not available right now.</p>';
      this.addToHistory(this.query);
    }
  },

  // Search with the given query.
  async searchFor(q) {
    this.query = q;
    // Return the promise so we can await it in tests.
    return this.searchDictionary();
  },

  /** Add the given query to our current search history. */
  addToHistory(query) {
    // If the query is already in the history, remove it.
    this.history = this.history.filter((x) => x !== query).concat(query);

    if (this.history.length > HISTORY_SIZE) {
      this.history.shift();
    }
  },

  /** Clear the search history. */
  clearHistory() {
    this.history = [];
  },

  /** Toggle the source selection widget's visibility. */
  toggleSourceSelector() {
    this.showSourceSelector = !this.showSourceSelector;
  },

  /** Close the source selection widget and re-run the query as needed. */
  onClickOutsideOfSourceSelector() {
    // NOTE: With our current bindings, this method will run *every* time we
    // click outside of the selector even if the selector is not open. If the
    // selector is not visible, this method is best left as a no-op.
    if (this.showSourceSelector) {
      this.searchDictionary();
      this.showSourceSelector = false;
    }
  },

  transliterate(oldScript, newScript) {
    transliterateElement($('#dict--response'), oldScript, newScript);
  },
});
