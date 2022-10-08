/* global Alpine, Sanscript */

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
 * Most of the code follows normal Alpine idioms. We still have some legacy
 * code that does direct element manipulation (in particular, see our use of
 * the `$` function), but we will remove these over time.
 *
 * Known issues:
 * - JS replacement of server-side content isn't smooth.
 *
 *
 * # Technical terms
 *
 * - mula: the original verse (mūlam)
 * - slug: human-readable ID that appears in the URL.
 */

import {
  transliterateHTMLString, $,
} from './core.ts';
import Routes from './routes';

// Script options. We enumerate only the ones we need to refer to internally
const Script = {
  Devanagari: 'devanagari',
  SLP1: 'slp1',
};

// Layout option for parse data
export const Layout = {
  // Parse data replaces the original text. (default)
  InPlace: 'in-place',
  // Original block on the left, parse data on the right.
  SideBySide: 'side-by-side',
};

/* Alpine code
 * ===========
 */

// Dictionary key for localstorage.
const READER_CONFIG_KEY = 'reader';

const MSG_CONTENT_MISSING = '<p>Sorry, this content is not available right now.</p>';

// The main application.
export default () => ({

  // User settings
  // -------------
  // Persistent user-specific data that we store in localStorage.

  // Text size for body text.
  fontSize: 'md:text-xl',
  // Script for Sanskrit text.
  script: Script.Devanagari,
  // How to display parse data to the user.
  parseLayout: Layout.InPlace,
  // The dictionary sources to use when fetching.
  dictSources: ['mw'],

  // Server data
  // -----------
  // Text or dictionary data fetched from the server.

  // Blocks of text content
  //
  // Structure ("?" indicates an optional field):
  // [
  //   {
  //     id: "Text.1.2",
  //     mula: "<div>...</div>",
  //     parse?: "<div>...</div>",
  //     showParse?: true,
  //   },
  // ]
  // FIXME: enforce a schema with TypeScript.
  data: {
    text_title: null,
    section_title: null,
    blocks: [],
    prev_url: null,
    next_url: null,
  },

  // The current dictionary response.
  dictionaryResponse: null,
  // Analysis of a word clicked by the user.
  wordAnalysis: {
    // The inflected form
    form: null,
    // The form lemma
    lemma: null,
    // The English parse (gender, case, ...) of this form.
    parse: null,
  },

  // Transient data
  // --------------
  // Internal application data that manages the application state.

  // If true, show the sidebar.
  showSidebar: false,
  // Sidebar error message (for failed fetches)
  sidebarErrorMessage: null,
  // Text in the dictionary search field. This field is visible only on wide
  // screens.
  dictQuery: '',
  // If true, show the dictionary selection widget.
  showDictSourceSelector: false,

  init() {
    this.loadSettings();
    this.data = JSON.parse(document.getElementById('payload').textContent);

    this.replaceHistoryState();
    window.addEventListener('popstate', this.onPopHistoryState.bind(this));
  },

  // Settings
  // ========

  /** Load user settings from local storage. */
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

  /** Save user settings to local storage. */
  saveSettings() {
    const settings = {
      fontSize: this.fontSize,
      script: this.script,
      parseLayout: this.parseLayout,
      dictSources: this.dictSources,
    };
    localStorage.setItem(READER_CONFIG_KEY, JSON.stringify(settings));
  },

  // Utility functions
  // =================

  /**
   * Transliterate an HTML blob to the user's preferred script.
   *
   * This function ignores attributes and content within tags.
   */
  transliterateHTML(devanagariHTML) {
    return transliterateHTMLString(devanagariHTML, this.script);
  },

  /** Transliterate a Devanagari string to the user's preferred script. */
  transliterateStr(devanagariStr) {
    if (!devanagariStr) return '';
    return Sanscript.t(devanagariStr, Script.Devanagari, this.script);
  },

  // Browser history
  // ===============
  // For a useful summary of the API and gotchas, see::
  //
  // https://blog.twitter.com/engineering/en_us/a/2012/implementing-pushstate-for-twittercom

  createHistoryState(scrollTop) {
    // `this.data` is a proxy object and cannot be cloned directly. So instead,
    // clone it by building a new object from its JSON string.
    const dataClone = JSON.parse(JSON.stringify(this.data));
    return { data: dataClone, scrollTop: document.documentElement.scrollTop };
  },
  /**
   * Save the history state for the current URL.
   *
   * Call this method just after the initial full-page load.
   */
  replaceHistoryState() {
    const url = window.location.pathname;
    const state = this.createHistoryState();
    window.history.replaceState(state, '', url);
  },

  /**
   * Save the history state for the current URL.
   *
   * Call this method to nagivate to a new reader page.
   */
  pushHistoryState(url) {
    // Reset scroll position to match browser behavior.
    document.documentElement.scrollTop = 0;
    const state = this.createHistoryState();
    window.history.pushState(state, '', url);
  },

  /** Handler for the `popstate` event. */
  onPopHistoryState(e) {
    if (!e.state) {
      return;
    }
    const { data, scrollTop } = e.state;
    this.data = data;

    // FIXME: this line doesn't seem to take effect, perhaps because it runs
    // before the content above has rendered.
    // document.documentElement.scrollTop = scrollTop;
  },

  // Ajax requests
  // =============

  /** Load text data from the server. */
  async fetchSection(url) {
    if (!url) return;

    // HACK: just prepend "/api".
    const apiURL = `/api${url}`;
    const resp = await fetch(apiURL);

    if (resp.ok) {
      // Replace state to retain scroll position.
      this.replaceHistoryState();

      this.data = await resp.json();

      this.pushHistoryState(url);
    } else {
      // Loading failed -- just use the server-side.
      // FIXME: make the non-JS experience smoother.
    }
  },

  /** Query the dictionary and populate the sidebar. */
  async searchDictionary() {
    if (!this.dictQuery || this.dictSources.length === 0) {
      return;
    }
    const url = Routes.ajaxDictionaryQuery(this.dictSources, this.dictQuery);
    const resp = await fetch(url);
    if (resp.ok) {
      this.dictionaryResponse = await resp.text();
    } else {
      // FIXME: add i18n support
      this.dictionaryResponse = MSG_CONTENT_MISSING;
    }
  },

  async fetchBlockParse(blockSlug) {
    const textSlug = Routes.getTextSlug();
    const url = Routes.parseData(textSlug, blockSlug);

    // Fetch parsed data.
    let resp;
    try {
      resp = await fetch(url);
    } catch (e) {
      return [null, false];
    }

    if (resp.ok) {
      const html = await resp.text();
      return [html, true];
    }
    // FIXME: add i18n support
    const html = MSG_CONTENT_MISSING;
    return [html, false];
  },

  // `parseLayout` logic
  // ===================

  /** Get CSS related to the `parseLayout` setting. */
  getParseLayoutClasses() {
    if (this.parseLayout === Layout.SideBySide) {
      // Extra wide to fit the side-by-side view.
      // '!' to take priority over existing styles.
      return 'md:!max-w-3xl';
    }
    return '';
  },
  getBlockClasses(b) {
    if (b.showParse) {
      if (this.parseLayout === Layout.SideBySide) {
        // Show side-by-side.
        return 'flex flex-wrap justify-between w-full';
      }
      return '';
    }
    // Otherwise, indicate that the verse is clickable.
    return 'cursor-pointer';
  },
  getParseLayoutTogglerText() {
    if (this.parseLayout === Layout.SideBySide) {
      return 'Hide parse';
    }
    return 'Show original';
  },
  getMulaClasses() {
    if (this.parseLayout === Layout.SideBySide) {
      // Extra margin for better readability.
      return 'mr-4';
    }
    return '';
  },
  showBlockMula(b) {
    if (this.parseLayout === Layout.InPlace) {
      // For this layout, show the mula iff the parse is not visible.
      return !b.showParse;
    }
    // By default, always show the mula.
    return true;
  },
  hideParse(b) {
    b.showParse = false;
  },

  // Click handlers
  // ==============
  // For clicked words. Over time, we will move more of the state here from the
  // DOM into the Alpine object.

  /** Generic click handler for multiple objects in the reader. */
  async onClick(e) {
    // Don't run e.preventDefault by default, as the user might be clicking an
    // actual link.

    // Parsed word: show details for this word.
    const $word = e.target.closest('s-w');
    if ($word) {
      this.onClickWord($word);
      return;
    }

    const $a = e.target.closest('a');
    if ($a) {
      // HACK for "show original" link inside block.
      return;
    }

    // Block: show parse data for this block.
    const $block = e.target.closest('s-block');
    if ($block) {
      this.onClickBlock($block.dataset.slug);
    }
  },

  async onClickBlock(blockSlug) {
    const block = this.data.blocks.find((b) => b.slug === blockSlug);

    // If we have parse data already, display it then return.
    if (block.parse) {
      block.showParse = true;
      return;
    }

    const [html, ok] = await this.fetchBlockParse(blockSlug);
    if (ok) {
      block.parse = html;
      block.showParse = true;
      this.sidebarErrorMessage = null;
    } else {
      this.sidebarErrorMessage = html;
      this.showSidebar = true;
    }
  },

  // Show information for a clicked word.
  async onClickWord($word) {
    const form = Sanscript.t($word.textContent, this.script, Script.Devanagari);
    const lemma = Sanscript.t($word.getAttribute('lemma'), Script.SLP1, Script.Devanagari);
    const parse = $word.getAttribute('parse');

    this.dictQuery = Sanscript.t(lemma, Script.SLP1, this.script);
    await this.searchDictionary();

    this.wordAnalysis = { form, lemma, parse };
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
});
