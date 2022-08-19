/* global Sanscript */

/* NOTE: This code is deprecated, and we're in the process of splitting it up
 * into separate files:
 *
 * - `reader.js` defines the reading environment.
 * - `proofreading.js` defines the proofing environment.
 */

const URL = {
  ajaxDictionaryQuery: (version, query) => `/api/dictionaries/${version}/${query}`,
  dictionaryQuery: (version, query) => `/tools/dictionaries/${version}/${query}`,
  parseData: (textSlug, blockSlug) => `/api/parses/${textSlug}/${blockSlug}`,

  // TODO: where to put this?
  getTextSlug: () => {
    const { pathname } = window.location;
    const suffix = pathname.replace('/texts/', '');
    const slug = suffix.split('/')[0];
    return slug;
  },
};

const Server = {
  getText(url, success, failure) {
    const req = new XMLHttpRequest();
    req.onreadystatechange = () => {
      if (req.readyState === XMLHttpRequest.DONE) {
        if (req.status === 200) {
          success(req.responseText);
        } else {
          failure();
        }
      }
    };
    req.open('GET', url);
    req.send();
  },
};

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

// Utilities

const $ = document.querySelector.bind(document);

function forEachTextNode(elem, callback) {
  const nodeList = elem.childNodes;
  for (let i = 0; i < nodeList.length; i += 1) {
    const node = nodeList[i];
    if (node.nodeType === Node.TEXT_NODE) {
      node.textContent = callback(node.textContent);
    } else if (node.lang !== 'en') {
      // Ignore lang="en"
      forEachTextNode(node, callback);
    }
  }
}

function transliterateElement($el, from, to) {
  $el.querySelectorAll('[lang=sa]').forEach((elem) => {
    forEachTextNode(elem, (s) => Sanscript.t(s, from, to));
  });
}

// Transliterate mixed Sanskrit content.
function transliterateSanskritBlob(blob, outputScript) {
  const $div = document.createElement('div');
  $div.innerHTML = blob;
  $div.querySelectorAll('*').forEach((elem) => {
    forEachTextNode(elem, (text) => Sanscript.t(text, 'devanagari', outputScript));
  });
  return $div.innerHTML;
}

// Transliterate mixed English/Sanskrit content.
function transliterateHTMLString(s, outputScript) {
  const $div = document.createElement('div');
  $div.innerHTML = s;
  transliterateElement($div, 'devanagari', outputScript);
  return $div.innerHTML;
}

// Sidebar show/hide

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

    const url = URL.ajaxDictionaryQuery(version, query);
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
        window.history.replaceState({}, '', URL.dictionaryQuery(version, query));
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
    const textSlug = URL.getTextSlug();

    const $block = $(`#${blockID.replaceAll('.', '\\.')}`);

    if ($block.classList.contains('has-parsed')) {
      // Text has already been parsed. Show it if necessary.
      $block.classList.add('show-parsed');
      return;
    }
    $block.classList.add('has-parsed');

    // Fetch parsed data.
    const url = URL.parseData(textSlug, blockSlug);
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

const HamburgerButton = (() => {
  function init() {
    const $ham = $('#hamburger');
    if ($ham) {
      $ham.addEventListener('click', (e) => {
        e.preventDefault();
        $('#navbar').classList.toggle('hidden');
      });
    }
  }

  return { init };
})();

(() => {
  Dictionary.init();
  ParseLayer.init();

  HamburgerButton.init();
})();
