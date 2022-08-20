/* global Sanscript */
/* exported Routes Server transliterateSanskritBlob transliterateHTMLString */

// A simple interface to server URLs.
const Routes = {
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
  HamburgerButton.init();
})();
