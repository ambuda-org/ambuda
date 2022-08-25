/* global Sanscript */
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
    } else if (!node.lang || node.lang === 'sa') {
      // Ignore lang="en"
      forEachTextNode(node, callback);
    }
  }
}

/** Transliterate all Sanskrit strings in the given element. */
function transliterateElement($el, from: string, to: string) {
  if (from === to) return;
  $el.querySelectorAll('[lang=sa]').forEach((elem) => {
    forEachTextNode(elem, (s) => Sanscript.t(s, from, to));
  });
}

// Transliterate mixed Sanskrit content.
function transliterateSanskritBlob(blob: string, outputScript: string) {
  const $div = document.createElement('div');
  $div.innerHTML = blob;
  $div.querySelectorAll('*').forEach((elem) => {
    forEachTextNode(elem, (text) => Sanscript.t(text, 'devanagari', outputScript));
  });
  return $div.innerHTML;
}

// Transliterate mixed English/Sanskrit content.
// FIXME: unify with transliterateSanskritBlob.
function transliterateHTMLString(s: string, outputScript: string) {
  const $div = document.createElement('div');
  $div.innerHTML = s;
  transliterateElement($div, 'devanagari', outputScript);
  return $div.innerHTML;
}

export {
  $,
  transliterateElement,
  transliterateSanskritBlob,
  transliterateHTMLString,
  Server,
  forEachTextNode,
};
