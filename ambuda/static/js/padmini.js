import {
  transliterateElement, transliterateHTMLString, $,
} from './core.ts';
import Routes from './routes';

// The key to use when storing the dictionary config in local storage.
const PADMINI_CONFIG_KEY = 'padmini';
// The maximum number of queries to keep in `this.history`.
const HISTORY_SIZE = 10;

export default () => ({
  // TODO: autodetect
  inputScript: 'hk',
  outputScript: 'devanagari',
  // The dictionary sources to use.
  dictionaries: ['mw'],

  // The current query.
  query: '',
  // The user's search history, from least to most recent.
  history: [],

  // If true, show the settings modal window.
  isSettingsModalVisible: false,

  init() {
    this.loadSettings();
    this.loadDefaults();

    this.$watch('inputScript', () => this.saveSettings());
    this.$watch('outputScript', () => this.saveSettings());
    this.$watch('dictionaries', () => this.saveSettings());
  },

  loadSettings() {
    const settingsStr = localStorage.getItem(PADMINI_CONFIG_KEY);
    if (settingsStr) {
      try {
        const settings = JSON.parse(settingsStr);
        this.inputScript = settings.inputScript || this.inputScript;
        this.outputScript = settings.outputScript || this.outputScript;
        this.dictionaries = settings.dictionaries || this.dictionaries;
      } catch (error) {
        // Old settings are invalid -- rewrite with valid values.
        this.saveSettings();
      }
    }
  },

  /** Load model defaults received from the server as a JSON blob. */
  loadDefaults() {
    if (window.PADMINI_DEFAULTS) {
        this.query = window.PADMINI_DEFAULTS.query;
    }
  },

  saveSettings() {
    const settings = {
      inputScript: this.inputScript,
      outputScript: this.outputScript,
      dictionaries: this.dictionaries,
    };
    localStorage.setItem(PADMINI_CONFIG_KEY, JSON.stringify(settings));
  },

  // Event handlers
 
  onClick(e) { 
    const rawHref = e.target.href;
    if (rawHref && rawHref.includes("/padmini/search/")) {
      const query = rawHref.split("/").pop();
      if (query) {
        e.preventDefault();
        const newHref = Routes.padminiQuery(query, this.dictionaries);
        window.location.href = newHref;
      }
    }
  },

  // Settings modal

  showSettingsModal() {
    this.isSettingsModalVisible = true;
  },

  hideSettingsModal() {
    this.isSettingsModalVisible = false;
  },

  runQuery() {
    console.log("runquery", this.query);
    const url = Routes.padminiQuery(this.query, this.dictionaries);
    window.location.href = url;
  }
});
