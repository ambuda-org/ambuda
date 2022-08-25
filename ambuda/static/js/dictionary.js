import {
  transliterateElement, transliterateHTMLString, $, Server,
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
    this.loadSettings();
    this.transliterate('devanagari', this.script);
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
        console.error(error);
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

  setSource(value) {
    this.source = value;
    this.saveSettings();
    this.searchDictionary(this.query);
  },
  updateScript() {
    this.transliterate(this.script, this.uiScript);
    this.script = this.uiScript;
    this.saveSettings();
  },

  searchDictionary() {
    if (!this.query) {
      return;
    }

    const url = Routes.ajaxDictionaryQuery(this.source, this.query);
    const $container = $('#dict--response');
    Server.getText(
      url,
      (resp) => {
        $container.innerHTML = transliterateHTMLString(resp, this.script);
        window.history.replaceState({}, '', Routes.dictionaryQuery(this.source, this.query));
      },
      () => {
        $container.innerHTML = '<p>Sorry, this content is not available right now.</p>';
      },
    );
  },

  transliterate(oldScript, newScript) {
    transliterateElement($('#dict--response'), oldScript, newScript);
  },
});
