/* global $, Server, OpenSeadragon, IMAGE_URL */

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

/* Initialize our image viewer. */
function initializeImageViewer(imageURL) {
  OpenSeadragon({
    id: 'osd-image',
    tileSources: {
      type: 'image',
      url: imageURL,
      buildPyramid: false,
    },

    // Buttons
    showRotationControl: true,
    showFullPageControl: false,
    zoomInButton: 'osd-zoom-in',
    zoomOutButton: 'osd-zoom-out',
    homeButton: 'osd-home',
    rotateLeftButton: 'osd-rotate-left',
    rotateRightButton: 'osd-rotate-right',

    // Animations
    gestureSettingsMouse: {
      flickEnabled: true,
    },
    animationTime: 0,

    // The zoom multiplier to use when using the zoom in/out buttons.
    zoomPerClick: 1.2,
    // Max zoom level
    maxZoomPixelRatio: 2,
  });
}

// Setup
initializeImageViewer(IMAGE_URL);
window.onbeforeunload = () => {
  if (hasUnsavedChanges) {
    return 'You have unsaved changes! If you leave this page, your changes will be lost.';
  }
  // so that eslint doesn't complain
  return undefined;
};
