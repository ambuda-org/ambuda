import {
  transliterateElement, transliterateHTMLString, $,
} from './core.ts';
import Routes from './routes';

export default () => ({
  // The script to use for Sanskrit text.
  script: 'devanagari',
  // The user's query.
  query: '',

  init() {
    this.transliterate('devanagari', this.script);
  },

  transliterate(oldScript, newScript) {
    transliterateElement($('#dict--response'), oldScript, newScript);
  },

  async analyzeQuery() {
    const query = this.query.trim();

    if (!query) {
      return;
    }

    const $container = $('#bharati-response');
    const url = Routes.ajaxBharatiQuery(query);
    const resp = await fetch(url);

    if (resp.ok) {
      const text = await resp.text();
      $container.innerHTML = transliterateHTMLString(text, this.script);
    }
  },
});
