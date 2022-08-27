/* globals Alpine, Sanscript */

import { $, Server } from './core.ts';
import Dictionary from './dictionary';
import Reader from './reader';
import Proofer from './proofer';
import HamburgerButton from './hamburger-button';
import ProofingCreatePoll from './proofing-create-poll';

window.addEventListener('alpine:init', () => {
  Alpine.data('dictionary', Dictionary);
  Alpine.data('reader', Reader);
  Alpine.data('proofer', Proofer);
});

(() => {
  HamburgerButton.init();
  ProofingCreatePoll.init();
})();

// Export a few internal values to support some existing ad-hoc usage (e.g.,
// in the pages that shows the progress bar for a project upload.)
// FIXME(arun): clean up existing usage of these values so that our code is less
// FIXME(arun): ad-hoc.
window.Server = Server;
window.$ = $;
