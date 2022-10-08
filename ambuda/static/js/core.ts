/* global Sanscript */

const $ = document.querySelector.bind(document);

/**
 * Iterate over all Sanskrit text nodes in the given element.
 *
 * This function assumes that `elem`'s root language is Sanskrit. Descendant
 * nodes are skipped if their `lang` attribute indicates a non-Sanskrit
 * language.
 */
function forEachSanskritTextNode(elem, callback) {
  const nodeList = elem.childNodes;
  for (let i = 0; i < nodeList.length; i += 1) {
    const node = nodeList[i];
    if (node.nodeType === Node.TEXT_NODE) {
      node.textContent = callback(node.textContent);
    } else if (!node.lang || node.lang === 'sa') {
      forEachSanskritTextNode(node, callback);
    }
  }
}

/** Transliterate all Sanskrit strings in the given element. */
function transliterateElement($el, from: string, to: string) {
  if (from === to) return;
  $el.querySelectorAll('[lang=sa]').forEach((elem) => {
    forEachSanskritTextNode(elem, (s) => Sanscript.t(s, from, to));
  });
}

// Transliterate mixed Latin/Devanagari content.
function transliterateHTMLString(source: string, to: string) {
  const from = 'devanagari';
  if (from === to) return source;

  const $div = document.createElement('div');
  $div.innerHTML = source;
  $div.querySelectorAll('*').forEach((elem) => {
    forEachSanskritTextNode(elem, (s) => Sanscript.t(s, from, to));
  });
  return $div.innerHTML;
}

export {
  $,
  transliterateElement,
  transliterateHTMLString,
  forEachSanskritTextNode,
};
