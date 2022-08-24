/* global Alpine, Sanscript */

/**
 * Application code for our Sanskrit reading environment.
 *
 * The reading environment supports several user preferences, including script,
 * font size, and layout features for secondary content like parse data.
 *
 * As with our other applications, we prefer storing application state in
 * markup in accordance with HATEOAS. Where this is cumbersome, we instead
 * store application state within the object we export further below.
 *
 * NOTE: our migration to Alpine is in progress, and much of this file includes
 * legacy code from our older vanilla JS approach. We will migrate this code to
 * Alpine over time.
 */

import {
  transliterateElement, transliterateHTMLString, transliterateSanskritBlob, $, Server,
} from './core.ts';
import Routes from './routes';

/* Legacy code
 * ===========
 * Future PRs will migrate this code to Alpine.
 */

const Dictionary = (() => {
  function fetch(version, query, contentScript, callback) {
    $('#dict--form input[name=q]').value = query;

    const url = Routes.ajaxDictionaryQuery(version, query);
    const $container = $('#dict--response');
    Server.getText(
      url,
      (resp) => {
        $container.innerHTML = transliterateHTMLString(resp, contentScript);
        if (callback) {
          callback();
        }
      },
      () => {
        $container.innerHTML = '<p>Sorry, this content is not available right now.</p>';
      },
    );
  }

  return { fetch };
})();

const ParseLayer = (() => {
  function getBlockSlug(blockID) {
    // Slice to remove text XML id.
    return blockID.split('.').slice(1).join('.');
  }

  function showParsedBlock(blockID, contentScript, callback) {
    const blockSlug = getBlockSlug(blockID);
    const $container = $('#parse--response');
    const textSlug = Routes.getTextSlug();

    const $block = $(`#${blockID.replaceAll('.', '\\.')}`);

    if ($block.classList.contains('has-parsed')) {
      // Text has already been parsed. Show it if necessary.
      $block.classList.add('show-parsed');
      return;
    }
    $block.classList.add('has-parsed');

    // Fetch parsed data.
    const url = Routes.parseData(textSlug, blockSlug);
    Server.getText(
      url,
      (resp) => {
        const parsedNode = document.createElement('div');
        parsedNode.classList.add('parsed');
        parsedNode.innerHTML = transliterateSanskritBlob(resp, contentScript);
        $block.appendChild(parsedNode);

        const link = document.createElement('a');
        link.className = 'text-sm text-zinc-400 hover:underline js--source';
        link.href = '#';
        link.innerHTML = '<span class=\'shown-side-by-side\'>Hide</span><span class=\'hidden-side-by-side\'>Show original</span>';
        parsedNode.firstChild.appendChild(link);

        $block.classList.add('show-parsed');
      },
      () => {
        $block.classList.remove('has-parsed');
        $container.innerHTML = '<p>Sorry, this content is not available right now. (Server error)</p>';
        callback();
      },
    );
  }

  return { showParsedBlock, getBlockSlug };
})();

/* Alpine code
 * ===========
 * Future PRs will merge the legacy code above into the application below.
 */

/**
 * Switch the script used in the reader.
 */
function switchScript(oldScript, newScript) {
  const $textContent = $('#text--content');
  if ($textContent) {
    transliterateElement($textContent, oldScript, newScript);
  }
  const $content = $('#sidebar');
  if ($content) {
    transliterateElement($content, oldScript, newScript);
  }
}

const READER_CONFIG_KEY = 'reader';
export default () => ({
  // Text size for body text in the reader.
  fontSize: 'md:text-xl',
  // Script for Sanskrit text in the reader.
  script: 'devanagari',
  // How to display parse data to the user.
  parseLayout: 'in-place',
  // The dictionary version to use.
  dictVersion: 'mw',

  // (transient data)

  // Script value as stored on the <select> widget. We store this separately
  // from `script` since we currently need to know both fields in order to
  // transliterate.
  uiScript: null,
  // Text in the dictionary search field. This field is visible only on wide
  // screens.
  dictQuery: '',
  // If true, show the sidebar.
  showSidebar: false,

  init() {
    this.loadSettings();
    switchScript('devanagari', this.script);

    // Sync UI with application state. See comments on `uiScript` for details.
    this.uiScript = this.script;

    // Allow sidebar to be shown. (We add `hidden` by default so that the
    // sidebar doesn't display while JS is loading.)
    $('#sidebar').classList.remove('hidden');
  },

  // Parse application settings from local storage.
  loadSettings() {
    const settingsStr = localStorage.getItem(READER_CONFIG_KEY);
    if (settingsStr) {
      try {
        const settings = JSON.parse(settingsStr);
        this.fontSize = settings.fontSize || this.fontSize;
        this.script = settings.script || this.script;
        this.parseLayout = settings.parseLayout || this.parseLayout;
        this.dictVersion = settings.dictVersion || this.dictVersion;
      } catch (error) {
        console.error(error);
      }
    }
  },

  // Save application settings to local storage.
  saveSettings() {
    const settings = {
      fontSize: this.fontSize,
      script: this.script,
      parseLayout: this.parseLayout,
      dictVersion: this.dictVersion,
    };
    localStorage.setItem(READER_CONFIG_KEY, JSON.stringify(settings));
  },

  setScript() {
    switchScript(this.script, this.uiScript);
    this.script = this.uiScript;
    this.saveSettings();
  },

  // Generic click handler for multiple objects in the reader.
  onClick(e) {
    // Parsed word: show details for this word.
    const $word = e.target.closest('s-w');
    if ($word) {
      this.showWordPanel($word);
      return;
    }
    // "Hide parse" link: hide the displayed parse.
    if (e.target.closest('.js--source')) {
      const $block = e.target.closest('s-block');
      $block.classList.remove('show-parsed');
      return;
    }
    // Block: show parse data for this block.
    const $block = e.target.closest('s-block');
    if ($block) {
      ParseLayer.showParsedBlock($block.id, this.script, () => {
        this.showSidebar = true;
      });
    }
  },

  // Show information for a clicked word.
  showWordPanel($word) {
    const lemma = $word.getAttribute('lemma');
    const form = $word.textContent;
    const parse = $word.getAttribute('parse');
    this.dictQuery = Sanscript.t(lemma, 'slp1', this.script);

    Dictionary.fetch(this.dictVersion, this.dictQuery, this.script, () => {
      this.setSidebarWord(form, lemma, parse);
      this.showSidebar = true;
    });
  },

  // Display a specific word in the sidebar.
  setSidebarWord(form, lemma, parse) {
    const niceForm = Sanscript.t(form, 'slp1', this.script);
    const niceLemma = Sanscript.t(lemma, 'slp1', this.script);
    const html = `
    <header>
      <h1 class="text-xl" lang="sa">${niceForm}</h1>
      <p class="mb-8"><span lang="sa">${niceLemma}</span> ${parse}</p>
    </header>`;
    $('#parse--response').innerHTML = html;
  },

  // Search a word in the dictionary and display the results to the user.
  submitDictionaryQuery() {
    if (!this.dictQuery) return;
    Dictionary.fetch(this.dictVersion, this.dictQuery, this.script);
  },
});
