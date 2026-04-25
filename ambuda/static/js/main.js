/* globals Alpine, Sanscript */

import { $ } from './core.ts';
import Bharati from './bharati';
import Dictionary from './dictionary';
import HamburgerButton from './hamburger-button';
import HTMLPoller from './html-poller';
import Reader from './reader';
import SortableList from './sortable-list';
import { TagEditor, ProjectList } from './tag-editor';
import HomeSearch from './home-search';
import TextSearch from './library-search';
import SearchablePicker from './searchable-picker';
import CollectionMultiPicker from './collection-multi-picker';

window.addEventListener('alpine:init', () => {
  Alpine.data('dictionary', Dictionary);
  Alpine.data('htmlPoller', HTMLPoller);
  Alpine.data('bharati', Bharati);
  Alpine.data('reader', Reader);
  Alpine.data('sortableList', SortableList);
  Alpine.data('tagEditor', TagEditor);
  Alpine.data('projectList', ProjectList);
  Alpine.data('homeSearch', HomeSearch);
  Alpine.data('textSearch', TextSearch);
  Alpine.data('searchablePicker', SearchablePicker);
  Alpine.data('collectionMultiPicker', CollectionMultiPicker);
});

(() => {
  HamburgerButton.init();
})();
