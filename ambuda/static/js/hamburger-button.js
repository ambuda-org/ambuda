import { $ } from './core.ts';

export default (() => {
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
