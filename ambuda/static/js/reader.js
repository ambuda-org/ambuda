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
  transliterateElement, transliterateHTMLString, $,
} from './core.ts';
import Routes from './routes';

/* Legacy code
 * ===========
 * Future PRs will migrate this code to Alpine.
 */

async function searchDictionary(sources, query, contentScript) {
  $('#dict--form input[name=q]').value = query;

  const url = Routes.ajaxDictionaryQuery(sources, query);
  const $container = $('#dict--response');
  const resp = await fetch(url);
  if (resp.ok) {
    const text = await resp.text();
    $container.innerHTML = transliterateHTMLString(text, contentScript);
  } else {
    // FIXME: add i18n support
    $container.innerHTML = '<p>Sorry, this content is not available right now.</p>';
  }
}

function getBlockSlug(blockID) {
  // Slice to remove text XML id.
  return blockID.split('.').slice(1).join('.');
}

async function showParsedBlock(block, contentScript, onFailure) {
  if (block.parse) {
    // Parse has already been fetched. Toggle state.
    block.showParse = !block.showParse;
    return;
  }

  const blockSlug = getBlockSlug(block.id);
  const textSlug = Routes.getTextSlug();
  const url = Routes.parseData(textSlug, blockSlug);

  // Fetch parsed data.
  let resp;
  try {
    resp = await fetch(url);
  } catch (e) {
    return;
  }

  if (resp.ok) {
    const rawText = await resp.text();
    const text = transliterateHTMLString(rawText, contentScript);
    block.parse = text;
    block.showParse = true;
  } else {
    const $container = $('#parse--response');
    // FIXME: add i18n support
    $container.innerHTML = '<p>Sorry, this content is not available right now. (Server error)</p>';
    onFailure();
  }
}

/* Alpine code
 * ===========
 * Future PRs will merge the legacy code above into the application below.
 */

/**
 * Switch the script used in the reader.
 */
function switchScript(oldScript, newScript) {
  if (oldScript === newScript) return;

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

  // User preferences
  // ----------------

  // Text size for body text in the reader.
  fontSize: 'md:text-xl',
  // Script for Sanskrit text in the reader.
  script: 'devanagari',
  // How to display parse data to the user.
  parseLayout: 'in-place',
  // The dictionary sources to use when fetching.
  dictSources: ['mw'],

  // AJAX data
  // ---------
  blocks: [],

  // Transient data
  // --------------

  // Script value as stored on the <select> widget. We store this separately
  // from `script` since we currently need to know both fields in order to
  // transliterate.
  uiScript: null,
  // If true, show the sidebar.
  showSidebar: false,

  // Text in the dictionary search field. This field is visible only on wide
  // screens.
  dictQuery: '',
  // If true, show the dictionary selection widget.
  showDictSourceSelector: false,

  init() {
    this.loadSettings();
    switchScript('devanagari', this.script);

    // Sync UI with application state. See comments on `uiScript` for details.
    this.uiScript = this.script;

    // Allow sidebar to be shown. (We add `hidden` by default so that the
    // sidebar doesn't display while JS is loading. Alpine's show/hide seems
    // not to work if the element has this class hidden, which is why we don't
    // just use "this.showSidebar = true" here.)
    const $sidebar = $('#sidebar');
    if ($sidebar) {
      $sidebar.classList.remove('hidden');
    }

    this.loadAjax();
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
        this.dictSources = settings.dictSources || this.dictSources;
      } catch (error) {
        // Old settings are invalid -- rewrite with valid values.
        this.saveSettings();
      }
    }
  },

  // Save application settings to local storage.
  saveSettings() {
    const settings = {
      fontSize: this.fontSize,
      script: this.script,
      parseLayout: this.parseLayout,
      dictSources: this.dictSources,
    };
    localStorage.setItem(READER_CONFIG_KEY, JSON.stringify(settings));
  },

  async loadAjax() {
    const url = '/api/texts/json/kumarasambhavam/1';
    const resp = await fetch(url);
    if (resp.ok) {
      const json = await resp.json();
      console.log(json.blocks);
      this.blocks = json.blocks;
    } else {
      console.log("unhandled exception");
    }
  },

  updateScript() {
    switchScript(this.script, this.uiScript);
    this.script = this.uiScript;
    this.saveSettings();
  },

  getParseLayoutClasses() {
    if (this.parseLayout === 'side-by-side') {
      return 'md:max-w-3xl';
    } else {
      return 'md:max-w-lg ';
    }
  },
  getBlockClasses(b) {
    if (b.showParse) {
      if (this.parseLayout === 'side-by-side') {
        return 'flex flex-wrap justify-between w-max';
      }
    } else {
      return 'cursor-pointer';
    }
  },
  getParseLayoutTogglerText() {
    if (this.parseLayout === 'side-by-side') {
      return 'Hide parse';
    } else {
      return 'Show original';
    }
  },
  getMulaClasses() {
    if (this.parseLayout === 'side-by-side') {
      return 'mr-4';
    }
    return '';
  },


  showBlockMula(b) {
    // in-place --> showParse
    // otherwise --> true
    if (this.parseLayout === 'in-place') {
      return !b.showParse;
    }
    return true;
  },

  // Generic click handler for multiple objects in the reader.
  async onClick(e) {
    // Don't run e.preventDefault by default, as the user might be clicking an
    // actual link.

    // Parsed word: show details for this word.
    const $word = e.target.closest('s-w');
    if ($word) {
        console.log('1');
      this.showWordPanel($word);
      return;
    }

    // "Hide parse" link: hide the displayed parse.
    if (e.target.closest('.js--source')) {
        console.log('2');
      e.preventDefault();
      const $block = e.target.closest('s-block');
      $block.classList.remove('show-parsed');
      return;
    }
    // Block: show parse data for this block.
    const $block = e.target.closest('s-block');
    if ($block) {
        console.log('3');
      const block = this.blocks.find((b) => b.id == $block.id);
      showParsedBlock(block, this.script, () => {
        this.showSidebar = true;
      });
    }
  },

  // Show information for a clicked word.
  async showWordPanel($word) {
    const lemma = $word.getAttribute('lemma');
    const form = $word.textContent;
    const parse = $word.getAttribute('parse');
    this.dictQuery = Sanscript.t(lemma, 'slp1', this.script);

    await searchDictionary(this.dictSources, this.dictQuery, this.script);
    this.setSidebarWord(form, lemma, parse);
    this.showSidebar = true;
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
    searchDictionary(this.dictSources, this.dictQuery, this.script);
  },

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
      this.submitDictionaryQuery();
      this.showDictSourceSelector = false;
    }
  },
});
