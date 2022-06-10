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
    console.log(version);
    const url = `/api/dict/${version}/${query}`;
    getJSON(url, function(resp) {
		if (resp.entries && resp.entries.length > 0) {
			$('#mw-response').innerHTML = '<ul>' + resp.entries.join('') + '</ul>';
		} else {
			$('#mw-response').innerHTML = '<p>No results found.</p>';
		}
    });
}

function toggleSidebar(e) {
    e.preventDefault();
    const classes = $('#sidebar').classList;
    classes.toggle('md:block');
    classes.toggle('md:hidden');
}

// Transliteration

/* Get and set user data. */
const SA_KEY = 'sa_script';
const SA_DEFAULT = 'devanagari';
const SA_SELECTOR = '#switch-sa';

function getUserScript() {
  return localStorage.getItem(SA_KEY) || SA_DEFAULT;
}
function setUserScript(value) {
  localStorage.setItem(SA_KEY, value);
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
    console.log(newScript);
    const oldScript = getUserScript();
    setUserScript(newScript);
    transliteratePage(oldScript, newScript, '.x-verse');
}

$('#mw-ajax').addEventListener('submit', ajaxDict);
$('#toggle-sidebar').addEventListener('click', toggleSidebar);
$(SA_SELECTOR).addEventListener('change', function() { switchScript(this.value) });

transliteratePage(SA_DEFAULT, getUserScript(), '.x-verse');

// Update menu to match.
const menuSa = $(SA_SELECTOR)
if (menuSa) {
  menuSa.value = getUserScript();
}

})();
