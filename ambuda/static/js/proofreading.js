/* global Alpine, $, OpenSeadragon, IMAGE_URL */

/* Transcription and proofreading interface. */
const CONFIG_KEY = 'proofing-editor';
const LAYOUT_SIDE_BY_SIDE = 'flex flex-col-reverse md:flex-row h-[90vh]';
const LAYOUT_TOP_AND_BOTTOM = 'flex flex-col-reverse h-[90vh]';

const editorComponent = () => ({
  isRunningOCR: false,
  textRatio: 1,
  layout: 'side-by-side',

  init() {
    this.loadConfig();
  },
  loadConfig() {
    const configStr = localStorage.getItem(CONFIG_KEY);
    if (configStr) {
      try {
        const config = JSON.parse(configStr);
        this.textRatio = config.textRatio;
        this.layout = config.layout;
      } catch (error) {
        // console.error(error);
      }
    }
  },
  saveConfig() {
    const config = {
      textRatio: this.textRatio,
      layout: this.layout,
    };
    localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
  },
  async runOCR() {
    this.isRunningOCR = true;

    const { pathname } = window.location;
    const url = pathname.replace('/proofing/', '/api/ocr/');

    const content = await fetch(url)
      .then((response) => {
        if (response.ok) {
          return response.text();
        }
        return '(server error)';
      });
    $('[name=content]').value = content;

    this.isRunningOCR = false;
  },
  increaseTextSize() {
    this.textRatio += 0.2;
    this.saveConfig();
  },
  decreaseTextSize() {
    this.textRatio = Math.max(0, this.textRatio - 0.2);
    this.saveConfig();
  },
  displaySideBySide() {
    this.layout = LAYOUT_SIDE_BY_SIDE;
    this.saveConfig();
  },
  displayTopAndBottom() {
    this.layout = LAYOUT_TOP_AND_BOTTOM;
    this.saveConfig();
  },

  markAs(before, after) {
    // FIXME: more idiomatic way to get this?
    const $textarea = $('#content');
    const start = $textarea.selectionStart;
    const end = $textarea.selectionEnd;
    const { value } = $textarea;
    const selectedText = value.substr(start, end - start);
    $textarea.value = value.substr(0, start) + before + selectedText + after + value.substr(end);
  },
  markAsError() {
    this.markAs('<error>', '</error>');
  },
  markAsFix() {
    this.markAs('<fix>', '</fix>');
  },
  markAsUnclear() {
    this.markAs('<flag>', '</flag>');
  },
  markAsFootnoteNumber() {
    this.markAs('[^', ']');
  },
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

window.addEventListener('alpine:init', () => {
  Alpine.data('editor', editorComponent);
});

// Setup
initializeImageViewer(IMAGE_URL);
window.onbeforeunload = () => {
  if (hasUnsavedChanges) {
    return 'You have unsaved changes! If you leave this page, your changes will be lost.';
  }
  // so that eslint doesn't complain
  return undefined;
};
