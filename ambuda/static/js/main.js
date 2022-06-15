(function() {

const URL = {
  ajaxDictionaryQuery: (version, query) => {
    return `/api/dict/${version}/${query}`;
  },
  dictionaryQuery: (version, query) => {
    return `/dictionaries/${version}/${query}`;
  },
  parseData: (textSlug, blockSlug) => {
    return `/api/parses/${textSlug}/${blockSlug}`;
  },
}

const DICT_SCRIPT = 'DICT_SCRIPT'
const DICT_SCRIPT_DEFAULT = 'devanagari';


// Utilities

const $ = document.querySelector.bind(document);
const $$ = document.querySelectorAll.bind(document);

function getText(url, success, failure) {
  const req = new XMLHttpRequest();
  req.onreadystatechange = function() {
    if (req.readyState == XMLHttpRequest.DONE) {
      if (req.status == 200) {
        success(req.responseText);
      } else {
        failure();
      }
  }
  };
  req.open('GET', url);
  req.send();
}

function forEachTextNode(elem, callback) {
  const nodeList = elem.childNodes;
  for (let i = 0; i < nodeList.length; i++) {
    const node = nodeList[i];
    if (node.nodeType === Node.TEXT_NODE) {
      node.textContent = callback(node.textContent);
    } else {
      // Ignore lang="en"
      if (node.lang !== 'en') {
        forEachTextNode(node, callback);
      }
    }
  }
}

function transliterateElement($el, from, to) {
  $el.querySelectorAll('[lang=sa]').forEach((elem) => {
    forEachTextNode(elem, (s) => {
      return Sanscript.t(s.toLowerCase(), from, to);
    })
  });
}


// Sidebar show/hide

const SHOW_SIDEBAR = 'SHOW_SIDEBAR'

function toggleSidebar() {
  const classes = $('#sidebar').classList;
  classes.toggle('md:block');
  classes.toggle('md:hidden');

  const isVisible = classes.contains('md:block');
  setShowSidebar(isVisible);
}
function onClickToggleLink(e) {
  e.preventDefault();
  toggleSidebar();
}

function getShowSidebar() {
  return localStorage.getItem(SHOW_SIDEBAR) === 'true';
}
function setShowSidebar(value) {
  localStorage.setItem(SHOW_SIDEBAR, value);
}

const $toggleLink = $("#toggle-sidebar");
if ($toggleLink) {
  $toggleLink.addEventListener('click', onClickToggleLink);
  if (getShowSidebar()) { $toggleLink.click(); }
}


// Dictionary

function getDictScript() {
  return localStorage.getItem(DICT_SCRIPT) || DICT_SCRIPT_DEFAULT;
}
function setDictScript(value) {
  localStorage.setItem(DICT_SCRIPT, value);
}
function fetchDictEntries(e) {
    e.preventDefault();

    const $form = $('#dict--form');
    const query = $form.querySelector('input[name=q]').value;
    const version = $form.querySelector('select[name=version]').value;
    const url = URL.ajaxDictionaryQuery(version, query);

    const $container = $('#dict--response');
    getText(url,
      (resp) => {
        const $div = document.createElement('div');
        $div.innerHTML = resp;
        transliterateElement($div, 'devanagari', getDictScript());
        $container.innerHTML = $div.innerHTML;

        history.replaceState({}, "", URL.dictionaryQuery(version, query));
      },
      () => {
        $container.innerHTML = '<p>Sorry, this content is not available right now. (Server error)</p>'
      }
    );
}

const $dictForm = $('#dict--form');
if ($dictForm) {
  $dictForm.addEventListener('submit', fetchDictEntries);

  $dictScript = $('#dict--script');
  $dictScript.addEventListener('change', function() {
    const oldScript = getDictScript();
    const newScript = this.value;
    setDictScript(newScript);
    transliterateElement($("#dict--response"), oldScript, newScript);
  });
  $dictScript.value = getDictScript();
}


// Parse data
const $textContent = $("#text--content");
if ($textContent) {
  $textContent.addEventListener('click', function(e) {
    const block = e.target.closest("s-lg");
    if (block !== null && block.id.startsWith("R.")) {
      const slug = block.id.split(".").slice(1).join(".");

      const $container = $('#parse--response');
      const url = URL.parseData('ramayanam', slug)
      getText(url,
        (resp) => {
          const $div = document.createElement('div');
          $div.innerHTML = resp;
          transliterateElement($div, 'devanagari', getDictScript());

          $container.innerHTML = $div.innerHTML;
          if (!getShowSidebar()) { toggleSidebar(); }
        },
        () => {
          $container.innerHTML = '<p>Sorry, this content is not available right now. (Server error)</p>'
        }
      );
    }
  });
}

// Text transliteration

const SA_KEY = 'SA_KEY'
const SA_DEFAULT = 'devanagari';

function getUserScript() {
  return localStorage.getItem(SA_KEY) || SA_DEFAULT;
}
function setUserScript(value) {
  localStorage.setItem(SA_KEY, value);
}

function switchScript(newScript) {
  const oldScript = getUserScript();
  setUserScript(newScript);
  transliterateElement(document, oldScript, newScript);
}

const $scriptMenu = $("#switch-sa");
if ($scriptMenu) {
  $scriptMenu.addEventListener('change', function() {
    switchScript(this.value);
  });
  transliterateElement(document, SA_DEFAULT, getUserScript());
  $scriptMenu.value = getUserScript();
}

})();
