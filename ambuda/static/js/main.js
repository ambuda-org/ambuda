/* globals Alpine, Sanscript */

import { $, Server } from './core.ts';
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

// Export to all pages.
// FIXME(arun): clean up existing usages.
window.Server = Server;
window.$ = $;
