/* global transliterateElement, Sidebar, Preferences, Alpine, ParseLayer,
   Sanscript, Dictionary, $ */

function switchScript(oldScript, newScript) {
  const $textContent = $('#text--content');
  if ($textContent) {
    transliterateElement($textContent, oldScript, newScript);
  }

  Sidebar.transliterate(oldScript, newScript);
}

const READER_CONFIG_KEY = 'reader';
const Reader = () => ({
  fontSize: 'md:text-xl',
  script: 'devanagari',
  parseLayout: 'in-place',

  init() {
    this.loadSettings();
    switchScript('devanagari', this.script);
  },
  loadSettings() {
    const settingsStr = localStorage.getItem(READER_CONFIG_KEY);
    if (settingsStr) {
      try {
        const settings = JSON.parse(settingsStr);
        this.fontSize = settings.fontSize || this.fontSize;
        this.script = settings.script || this.script;
        this.parseLayout = settings.parseLayout || this.parseLayout;

        // To support legacy code.
        // FIXME: remove this once the migration is complete.
        Preferences.contentScript = settings.script;
      } catch (error) {
        // console.error(error);
      }
    }
  },
  saveSettings() {
    const settings = {
      fontSize: this.fontSize,
      script: this.script,
      parseLayout: this.parseLayout,
    };
    localStorage.setItem(READER_CONFIG_KEY, JSON.stringify(settings));
  },
  setFontSize(value) {
    this.fontSize = value;
    this.saveSettings();
  },
  setScript(value) {
    const oldScript = this.script;
    this.script = value;
    this.saveSettings();

    switchScript(oldScript, this.script);
  },
  setParseLayout(value) {
    this.parseLayout = value;
    this.saveSettings();
  },
  onClick(e) {
    // word
    const $word = e.target.closest('s-w');
    if ($word) {
      this.showWordPanel($word);
      return;
    }
    // "hide parse" link
    if (e.target.closest('.js--source')) {
      const $block = e.target.closest('s-block');
      $block.classList.remove('show-parsed');
      return;
    }
    // block
    const $block = e.target.closest('s-block');
    if ($block) {
      ParseLayer.showParsedBlock($block.id);
    }
  },
  showWordPanel($word) {
    const lemma = $word.getAttribute('lemma');
    const form = $word.textContent;
    const parse = $word.getAttribute('parse');

    const version = Preferences.dictVersion;
    const query = Sanscript.t(lemma, 'slp1', this.script);

    Dictionary.fetch(version, query, () => {
      Sidebar.setCurrentWord(form, lemma, parse);
      Sidebar.show();
    });
  },
});

window.addEventListener('alpine:init', () => {
  Alpine.data('reader', Reader);
});
