/* global Alpine, Sanscript */

import {
  transliterateElement, transliterateHTMLString, transliterateSanskritBlob, $, Server,
} from './core.ts';
import Routes from './routes';

/* Legacy code
 * ===========
 * Future PRs will migrate this code to Alpine.
 */

const Preferences = {
  // FIXME: remove this once everything has been migrated to `reader.js`.
  get contentScript() {
    const ls = localStorage.getItem('user-script');
    if (!ls || ls === 'undefined') {
      return 'devanagari';
    }
    return ls;
  },
  set contentScript(value) {
    if (value) {
      localStorage.setItem('user-script', value);
    }
  },

  get dictVersion() {
    const val = localStorage.getItem('dict-version');
    if (!val || val === 'undefined') {
      // MW for now because of Apte coverage issues.
      return 'mw';
    }
    return val;
  },
  set dictVersion(value) {
    localStorage.setItem('dict-version', value);
  },
};

const Sidebar = {
  toggle() {
    const classes = $('#sidebar').classList;
    classes.toggle('block');
    classes.toggle('hidden');
  },
  show() {
    if ($('#sidebar').classList.contains('hidden')) {
      this.toggle();
    }
  },
  hide() {
    if (!$('#sidebar').classList.contains('hidden')) {
      this.toggle();
    }
  },
  setCurrentWord(form, lemma, parse) {
    const niceForm = Sanscript.t(form, 'slp1', Preferences.contentScript);
    const niceLemma = Sanscript.t(lemma, 'slp1', Preferences.contentScript);
    const html = `
    <header>
      <h1 class="text-xl" lang="sa">${niceForm}</h1>
      <p class="mb-8"><span lang="sa">${niceLemma}</span> ${parse}</p>
    </header>`;
    $('#parse--response').innerHTML = html;
  },
  transliterate(from, to) {
    const $content = $('#sidebar');
    if ($content) {
      transliterateElement($content, from, to);
    }
  },
};

// Dictionary

const Dictionary = (() => {
  function fetch(version, query, callback) {
    $('#dict--form input[name=q]').value = query;

    const url = Routes.ajaxDictionaryQuery(version, query);
    const $container = $('#dict--response');
    Server.getText(
      url,
      (resp) => {
        $container.innerHTML = transliterateHTMLString(resp, Preferences.contentScript);
        if (callback) {
          callback();
        }
      },
      () => {
        $container.innerHTML = '<p>Sorry, this content is not available right now.</p>';
      },
    );
  }

  // Submit the form using the current form state.
  function submitForm() {
    const $form = $('#dict--form');
    const query = $form.querySelector('input[name=q]').value;
    const version = $form.querySelector('select[name=version]').value;

    if (!query) {
      return;
    }

    fetch(version, query, () => {
      // FIXME: remove "startsWith" hack and move this to Dictionaries page.
      if (window.location.pathname.startsWith('/tools/dict')) {
        window.history.replaceState({}, '', Routes.dictionaryQuery(version, query));
      }
    });
  }

  function init() {
    const $dictForm = $('#dict--form');
    if ($dictForm) {
      $dictForm.addEventListener('submit', (e) => {
        e.preventDefault();
        submitForm();
      });

      const $dictVersion = $('#dict--version');
      $dictVersion.addEventListener('change', (e) => {
        Preferences.dictVersion = e.target.value;
        submitForm();
      });
      $dictVersion.value = Preferences.dictVersion;
    }
  }

  return { init, fetch };
})();

const ParseLayer = (() => {
  function getBlockSlug(blockID) {
    // Slice to remove text XML id.
    return blockID.split('.').slice(1).join('.');
  }

  function showParsedBlock(blockID) {
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
        parsedNode.innerHTML = transliterateSanskritBlob(resp, Preferences.contentScript);
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
        Sidebar.show();
      },
    );
  }

  function init() {
    const $container = $('#parse--response');
    if ($container) {
      $container.addEventListener('click', (e) => {
        e.preventDefault();
        const link = e.target.closest('a');

        const $form = $('#dict--form');
        const query = link.textContent.trim();
        const version = $form.querySelector('select[name=version]').value;
        Dictionary.fetch(version, query);
      });
    }
  }

  return { init, showParsedBlock, getBlockSlug };
})();

/* Alpine code
 * ===========
 * Future PRs will merge the legacy code above into the application below.
 */

function switchScript(oldScript, newScript) {
  const $textContent = $('#text--content');
  if ($textContent) {
    transliterateElement($textContent, oldScript, newScript);
  }

  Sidebar.transliterate(oldScript, newScript);
}

const READER_CONFIG_KEY = 'reader';
export default () => ({
  fontSize: 'md:text-xl',
  script: 'devanagari',
  parseLayout: 'in-place',

  init() {
    this.loadSettings();
    switchScript('devanagari', this.script);

    // Load legacy content.
    Dictionary.init();
    ParseLayer.init();
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

  // legacy bindings
  hideSidebar() {
    Sidebar.hide();
  },
});
