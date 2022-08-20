/* globals Alpine, Sanscript */

import Dictionary from './dictionary';
import Reader from './reader';
import Proofer from './proofer';
import HamburgerButton from './hamburger-button';

window.addEventListener('alpine:init', () => {
  Alpine.data('dictionary', Dictionary);
  Alpine.data('reader', Reader);
  Alpine.data('proofer', Proofer);
});

(() => {
  HamburgerButton.init();
})();
