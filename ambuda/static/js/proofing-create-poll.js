import { $, Server } from './core.ts';

export default (() => {
  // Polls for status on project creation. Used only on
  // templates/proofing/create-project-post.html.
  function init() {
    const $el = document.getElementById('proofing_polling_task_id');
    if (!$el) {
      return;
    }
    const taskId = JSON.parse($el.innerText);
    setInterval(() => {
      Server.getText(`/proofing/status/${taskId}`, (text) => {
        $('#progress').innerHTML = text;
      });
    }, 5000);
  }

  return { init };
})();
