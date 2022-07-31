/* global Sanscript */
/* Main code for the reading environment.
 * TODO: when able, separate this into modules and add a JS build system. */

const URL = {
  ajaxTextContent: (path) => `/api${path}`,
  ajaxDictionaryQuery: (version, query) => `/api/dictionaries/${version}/${query}`,
  dictionaryQuery: (version, query) => `/tools/dictionaries/${version}/${query}`,
  parseData: (textSlug, blockSlug) => `/api/parses/${textSlug}/${blockSlug}`,
  googleOCR: (projectSlug, pageSlug) => `/api/ocr/${projectSlug}/${pageSlug}`,

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
  get contentFontSize() {
    const ls = localStorage.getItem('user-font-size');
    if (!ls || ls === 'undefined') {
      return 'md:text-xl';
    }
    return ls;
  },
  set contentFontSize(value) {
    if (value) {
      localStorage.setItem('user-font-size', value);
    }
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
    <header lang="sa">
      <h1 class="text-xl">${niceForm}</h1>
      <p class="mb-8">${niceLemma} ${parse}</p>
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
    const url = URL.parseData(textSlug, blockSlug);
    Server.getText(
      url,
      (resp) => {
        $block.outerHTML = transliterateSanskritBlob(resp, Preferences.contentScript);
      },
      () => {
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

const TextContent = (() => {
  function changeFontSize(from, to) {
    const $textContent = $('#text--content');
    if ($textContent) {
      $textContent.classList.replace(from, to);
    }
  }

  function transliterate(from, to) {
    const $textContent = $('#text--content');
    if ($textContent) {
      transliterateElement($textContent, from, to);
    }
  }

  function pushState(url, resp) {
    // Size limit here is 16 MiB per MDN.
    // Keep in sync with the popstate() call below.
    window.history.pushState({ textContent: resp }, '', url);
  }

  function popState(state) {
    const $textContent = $('#text--content');
    $textContent.innerHTML = transliterateHTMLString(
      state.textContent,
      Preferences.contentScript,
    );
  }

  // eslint-disable-next-line no-unused-vars
  function ajaxChangeSection(url) {
    const $textContent = $('#text--content');
    const ajaxURL = URL.ajaxTextContent(url);
    Server.getText(
      ajaxURL,
      (resp) => {
        // Push state with the un-transliterated content,
        // to keep the state clean.
        pushState(url, resp);
        $textContent.innerHTML = transliterateHTMLString(resp, Preferences.contentScript);
      },
      () => {
        const text = "<p>Sorry, we couldn't load this page.</p>";
        $textContent.innerHTML = text;
        pushState(url, text);
      },
    );
  }

  function onClickWord($word) {
    const lemma = $word.getAttribute('lemma');
    const form = $word.textContent;
    const parse = $word.getAttribute('parse');

    const version = Preferences.dictVersion;
    const query = Sanscript.t(lemma, 'slp1', Preferences.contentScript);

    Dictionary.fetch(version, query, () => {
      Sidebar.setCurrentWord(form, lemma, parse);
      Sidebar.show();
    });
  }

  function init() {
    const $textContent = $('#text--content');
    if ($textContent) {
      $textContent.addEventListener('click', (e) => {
        const $word = e.target.closest('s-w');

        if ($word) {
          e.preventDefault();
          onClickWord($word);
          return;
        }

        const $undoParse = e.target.closest('.js--source');
        if ($undoParse) {
          e.preventDefault();
          Server.getText(
            $undoParse.href,
            (resp) => {
              const transResp = transliterateSanskritBlob(resp, Preferences.contentScript);
              $undoParse.closest('s-lg').outerHTML = transResp;
            },
            () => {},
          );
          return;
        }

        const $paginate = e.target.closest('.js--paginate');
        if ($paginate) {
          // Disable for now -- includes too much extra state.
          // e.preventDefault();
          // use getAttribute to avoid the hostname.
          // const url = $paginate.getAttribute('href');
          // ajaxChangeSection(url);
          // return;
        }

        const $lg = e.target.closest('s-lg');
        if ($lg) {
          e.preventDefault();
          ParseLayer.showParsedBlock($lg.id);
        }
      });

      // This ensures that the browser back button works correctly.
      window.addEventListener('popstate', (event) => {
        popState(event.state);
      });
    }
  }

  return { init, transliterate, changeFontSize };
})();

const ScriptMenu = (() => {
  function switchScript(newScript) {
    const oldScript = Preferences.contentScript;
    Preferences.contentScript = newScript;
    TextContent.transliterate(oldScript, newScript);
    Sidebar.transliterate(oldScript, newScript);
  }

  function init() {
    const $scriptMenu = $('#switch-sa');
    if ($scriptMenu) {
      $scriptMenu.value = Preferences.contentScript;
      $scriptMenu.addEventListener('change', (e) => {
        switchScript(e.target.value);
      });
    }
  }

  return { init };
})();

const FontSizeMenu = (() => {
  function switchFontSize(newFontSize) {
    const oldFontSize = Preferences.contentFontSize;
    Preferences.contentFontSize = newFontSize;
    TextContent.changeFontSize(oldFontSize, newFontSize);
  }

  function init() {
    const $fontSizeMenu = $('#switch-font-size');
    if ($fontSizeMenu) {
      $fontSizeMenu.value = Preferences.contentFontSize;
      $fontSizeMenu.addEventListener('change', (e) => {
        switchFontSize(e.target.value);
      });
    }
  }

  return { init };
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
  FontSizeMenu.init();
  ScriptMenu.init();
  Dictionary.init();
  ParseLayer.init();
  TextContent.init();
  HamburgerButton.init();

  TextContent.changeFontSize('md:text-xl', Preferences.contentFontSize);
  TextContent.transliterate('devanagari', Preferences.contentScript);
  Sidebar.transliterate('devanagari', Preferences.contentScript);
})();
