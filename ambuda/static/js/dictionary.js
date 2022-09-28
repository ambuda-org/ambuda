import {
  transliterateElement, transliterateHTMLString, $,
} from './core.ts';
import Routes from './routes';

const DICTIONARY_CONFIG_KEY = 'dictionary';

export default () => ({
  script: 'devanagari',
  source: 'mw',

  // (transient data)

  // Script value as stored on the <select> widget. We store this separately
  // from `script` since we currently need to know both fields in order to
  // transliterate.
  uiScript: null,
  query: '',

  init() {
    // URL settings take priority.
    this.loadSettingsFromURL();
    this.loadSettings();
    this.transliterate('devanagari', this.script);
  },

  /** Load source and query from the URL (if defined). */
  loadSettingsFromURL() {
    const { query, source } = Routes.parseDictionaryURL();
    this.query = query || this.query;
    this.source = source || this.source;
  },

  loadSettings() {
    const settingsStr = localStorage.getItem(DICTIONARY_CONFIG_KEY);
    if (settingsStr) {
      try {
        const settings = JSON.parse(settingsStr);
        this.script = settings.script || this.script;
        this.source = settings.source || this.source;
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
      source: this.source,
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

    const url = Routes.ajaxDictionaryQuery(this.source, this.query);
    const $container = $('#dict--response');
    const resp = await fetch(url);
    if (resp.ok) {
      const text = await resp.text();
      $container.innerHTML = transliterateHTMLString(text, this.script);

      const newURL = Routes.dictionaryQuery(this.source, this.query);
      window.history.replaceState({}, '', newURL);
    } else {
      $container.innerHTML = '<p>Sorry, this content is not available right now.</p>';
    }
  },

  transliterate(oldScript, newScript) {
    transliterateElement($('#dict--response'), oldScript, newScript);
  },
});
