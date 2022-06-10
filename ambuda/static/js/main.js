(function() {

const $ = document.querySelector.bind(document);
const $$ = document.querySelectorAll.bind(document);

function getJSON(url, callback) {
    const req = new XMLHttpRequest();
    req.onreadystatechange = function() {
        if (req.readyState == XMLHttpRequest.DONE) {
            if (req.status == 200) {
                callback(JSON.parse(req.responseText));
            }
        }
    };
    req.open('GET', url);
    req.send();
}

function ajaxDict(e) {
    e.preventDefault();
    const form = $('#mw-ajax');
    const query = form.querySelector('input[name=q]').value;
    const version = form.querySelector('select[name=version]').value;
    const url = `/api/dict/${version}/${query}`;
    getJSON(url, function(resp) {
		if (resp.entries && resp.entries.length > 0) {
			$('#mw-response').innerHTML = '<ul>' + resp.entries.join('') + '</ul>';
		} else {
			$('#mw-response').innerHTML = `<p>No results found for query "<kbd>${query}</kbd>".</p>`;
		}
    });
}

function toggleSidebar(e) {
    e.preventDefault();
    const classes = $('#sidebar').classList;
    classes.toggle('md:block');
    classes.toggle('md:hidden');

    const isVisible = classes.contains('md:block');
    setShowSidebar(isVisible);
}

// Transliteration

/* Get and set user data. */
const SA_KEY = 'sa_script';
const SHOW_DICT = 'show_dict'
const SA_DEFAULT = 'devanagari';

function getUserScript() {
  return localStorage.getItem(SA_KEY) || SA_DEFAULT;
}
function setUserScript(value) {
  localStorage.setItem(SA_KEY, value);
}
function getShowSidebar() {
  return localStorage.getItem(SHOW_DICT) || false;
}
function setShowSidebar(value) {
  localStorage.setItem(SHOW_DICT, value);
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


const $toggleLink = $("#toggle-sidebar");
if ($toggleLink) {
  $toggleLink.addEventListener('click', toggleSidebar);
  if (getShowSidebar()) { $toggleLink.click(); }
}

const $scriptMenu = $("#switch-sa");
if ($scriptMenu) {
  $scriptMenu.addEventListener('change', function() {
    switchScript(this.value);
  });
  transliteratePage(SA_DEFAULT, getUserScript(), '.x-verse');
  $scriptMenu.value = getUserScript();
}

$('#mw-ajax').addEventListener('submit', ajaxDict);

})();
