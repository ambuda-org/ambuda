/* globals Alpine, Sanscript */

import { $ } from './core.ts';
import Dictionary from './dictionary';
import HamburgerButton from './hamburger-button';
import HTMLPoller from './html-poller';
import Reader from './reader';
import SortableList from './sortable-list';

window.addEventListener('alpine:init', () => {
  Alpine.data('dictionary', Dictionary);
  Alpine.data('htmlPoller', HTMLPoller);
  Alpine.data('reader', Reader);
  Alpine.data('sortableList', SortableList);
});

(() => {
  HamburgerButton.init();
})();
