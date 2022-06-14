(function() {

// Utilities

const $ = document.querySelector.bind(document);
const $$ = document.querySelectorAll.bind(document);

function getText(url, callback) {
    const req = new XMLHttpRequest();
    req.onreadystatechange = function() {
        if (req.readyState == XMLHttpRequest.DONE) {
            if (req.status == 200) {
                callback(req.responseText);
            }
        }
    };
    req.open('GET', url);
    req.send();
}

function getJSON(url, callback) {
    return getText(url, function(text) { callback(JSON.parse(text)) });
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


// Sidebar show/hide

const SHOW_SIDEBAR = 'SHOW_SIDEBAR'

function toggleSidebar(e) {
    e.preventDefault();
    const classes = $('#sidebar').classList;
    classes.toggle('md:block');
    classes.toggle('md:hidden');

    const isVisible = classes.contains('md:block');
    setShowSidebar(isVisible);
}

function getShowSidebar() {
  return localStorage.getItem(SHOW_SIDEBAR) === 'true';
}
function setShowSidebar(value) {
  localStorage.setItem(SHOW_SIDEBAR, value);
}

const $toggleLink = $("#toggle-sidebar");
if ($toggleLink) {
  $toggleLink.addEventListener('click', toggleSidebar);
  if (getShowSidebar()) { $toggleLink.click(); }
}


// Dictionary

const URL = {
  ajaxDictionaryQuery: (version, query) => {
    return `/api/dict/${version}/${query}`;
  },
  dictionaryQuery: (version, query) => {
    return `/dictionaries/${version}/${query}`;
  },
}

const DICT_SCRIPT = 'DICT_SCRIPT'
const DICT_SCRIPT_DEFAULT = 'devanagari';

function getDictScript() {
  return localStorage.getItem(DICT_SCRIPT) || DICT_SCRIPT_DEFAULT;
}
function setDictScript(value) {
  localStorage.setItem(DICT_SCRIPT, value);
}
function fetchDictEntries(e) {
    e.preventDefault();

    const form = $('#dict--form');
    const query = form.querySelector('input[name=q]').value;
    const version = form.querySelector('select[name=version]').value;
    const url = URL.ajaxDictionaryQuery(version, query);

    getJSON(url, function(resp) {
      const $el = $('#dict--response');
      if (resp.entries && resp.entries.length > 0) {
        // Transliterate in a container elem, then copy it over to the document.
        const oldScript = 'devanagari';
        const newScript = getDictScript();

        const container = document.createElement('div');
        container.innerHTML = '<ul>' + resp.entries.join('') + '</ul>';
        container.querySelectorAll('[lang=sa]').forEach((elem) => {
          forEachTextNode(elem, (s) => {
            return Sanscript.t(s.toLowerCase(), oldScript, newScript);
          })
        });

        $el.innerHTML = container.innerHTML;
      } else {
        $el.innerHTML = `<p>No results found for query "<kbd>${query}</kbd>".</p>`;
      }
      history.replaceState({}, "", URL.dictionaryQuery(version, query));
    });
}

const $dictForm = $('#dict--form');
if ($dictForm) {
  $dictForm.addEventListener('submit', fetchDictEntries);
  $dictScript = $('#dict--script');

  $dictScript.addEventListener('change', function() {
    const oldScript = getDictScript();
    const newScript = this.value;
    setDictScript(newScript);

    $('#dict--response').querySelectorAll('[lang=sa]').forEach((elem) => {
      forEachTextNode(elem, (s) => {
        return Sanscript.t(s.toLowerCase(), oldScript, newScript);
      })
    });
  });
  $dictScript.value = getDictScript();
}


// Parse data
const $parseMenu = $("#parse--menu");
if ($parseMenu) {
  $parseMenu.addEventListener('click', function(e) {
      e.preventDefault();
      if (e.target.tagName !== 'A') {
          return;
      }
      const url = '/api' + e.target.pathname;
      getText(url, function(t) {
          $('#parse--response').innerHTML = t;
      });
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

function transliteratePage(oldScript, newScript, selector) {
  if (oldScript === newScript) { return };
  document.querySelectorAll(selector).forEach((elem) => {
    forEachTextNode(elem, (s) => {
      return Sanscript.t(s.toLowerCase(), oldScript, newScript);
    });
  });
}

function switchScript(newScript) {
  const oldScript = getUserScript();
  setUserScript(newScript);
  transliteratePage(oldScript, newScript, '.x-verse');
}

const $scriptMenu = $("#switch-sa");
if ($scriptMenu) {
  $scriptMenu.addEventListener('change', function() {
    switchScript(this.value);
  });
  transliteratePage(SA_DEFAULT, getUserScript(), '.x-verse');
  $scriptMenu.value = getUserScript();
}

})();
