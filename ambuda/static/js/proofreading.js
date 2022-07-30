/* global $, Server */

// OCR trigger
$('#run-ocr').addEventListener('click', (e) => {
  e.preventDefault();

  const $button = e.target;
  $button.textContent = '...';
  $button.disabled = true;

  const { pathname } = window.location;
  const url = pathname.replace('/proofing/', '/api/ocr/');

  Server.getText(url, (text) => {
    $('[name=content]').value = text;
    $button.textContent = 'OCR';
    $button.disabled = false;
  }, () => {
    $button.textContent = 'OCR';
    $button.disabled = false;
  });
});

// Resize textarea text size
$('#text-increase').addEventListener('click', (e) => {
  e.preventDefault();
  const $textarea = $('textarea');
  const oldSize = $textarea.dataset.size || '1.0';
  const newSize = parseFloat(oldSize) + 0.2;
  $textarea.dataset.size = newSize;
  $textarea.style.fontSize = `${newSize}rem`;
});
$('#text-decrease').addEventListener('click', (e) => {
  e.preventDefault();
  const $textarea = $('textarea');
  const oldSize = $textarea.dataset.size || '1.0';
  const newSize = parseFloat(oldSize) - 0.2;
  $textarea.dataset.size = newSize;
  $textarea.style.fontSize = `${newSize}rem`;
});

// Warn the user if leaving the page after changing the text box.
let hasUnsavedChanges = false;
$('[name=content]').addEventListener('change', () => {
  hasUnsavedChanges = true;
});
$('[type=submit]').addEventListener('click', () => {
  hasUnsavedChanges = false;
});

window.onbeforeunload = () => {
  if (hasUnsavedChanges) {
    return 'You have unsaved changes! If you leave this page, your changes will be lost.';
  }
  // so that eslint doesn't complain
  return undefined;
};
