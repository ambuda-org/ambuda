/* global Alpine, $, OpenSeadragon, IMAGE_URL */
/* Transcription and proofreading interface. */


const CONFIG_KEY = 'proofing-editor';
const LAYOUT_SIDE_BY_SIDE = 'flex flex-col-reverse md:flex-row h-[90vh]';
const LAYOUT_TOP_AND_BOTTOM = 'flex flex-col-reverse h-[90vh]';


/* Initialize our image viewer. */
function initializeImageViewer(imageURL) {
  return OpenSeadragon({
    id: 'osd-image',
    tileSources: {
      type: 'image',
      url: imageURL,
      buildPyramid: false,
    },

    // Buttons
    showZoomControl: false,
    showHomeControl: false,
    showRotationControl: true,
    showFullPageControl: false,
    // Zoom buttons are defined in the `Editor` component below.
    rotateLeftButton: 'osd-rotate-left',
    rotateRightButton: 'osd-rotate-right',

    // Animations
    gestureSettingsMouse: {
      flickEnabled: true,
    },
    animationTime: 0.5,

    // The zoom multiplier to use when using the zoom in/out buttons.
    zoomPerClick: 1.1,
    // Max zoom level
    maxZoomPixelRatio: 2.5,
  });
}

const imageViewer = initializeImageViewer(IMAGE_URL);


const Editor = () => ({
  isRunningOCR: false,
  textZoom: 1,
  imageZoom: null,
  layout: 'side-by-side',

  init() {
    this.loadSettings();
    // Set `imageZoom` only after the viewer is fully initialized.
    imageViewer.addHandler('open', () => {
      this.imageZoom = this.imageZoom || imageViewer.viewport.getHomeZoom();
      imageViewer.viewport.zoomTo(this.imageZoom);
    });
  },

  // Settings IO

  loadSettings() {
    const settingsStr = localStorage.getItem(CONFIG_KEY);
    if (settingsStr) {
      try {
        const settings = JSON.parse(settingsStr);
        this.textZoom = settings.textZoom || this.textZoom;
        // We can only get an accurate default zoom after the viewer is fully
        // initialized. See `init` for details.
        this.imageZoom = settings.imageZoom;
        this.layout = settings.layout || this.layout;
      } catch (error) {
        console.error(error);
      }
    }
  },
  saveSettings() {
    const settings = {
      textZoom: this.textZoom,
      imageZoom: this.imageZoom,
      layout: this.layout,
    };
    localStorage.setItem(CONFIG_KEY, JSON.stringify(settings));
  },

  // OCR controls

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

  // Image zoom controls

  increaseImageZoom() {
    this.imageZoom *= 1.2;
    imageViewer.viewport.zoomTo(this.imageZoom);
    this.saveSettings();
  },
  decreaseImageZoom() {
    this.imageZoom *= 0.8;
    imageViewer.viewport.zoomTo(this.imageZoom);
    this.saveSettings();
  },
  resetImageZoom() {
    this.imageZoom = imageViewer.viewport.getHomeZoom();
    imageViewer.viewport.zoomTo(this.imageZoom);
    this.saveSettings();
  },

  // Text zoom controls

  increaseTextSize() {
    this.textZoom += 0.2;
    this.saveSettings();
  },
  decreaseTextSize() {
    this.textZoom = Math.max(0, this.textZoom - 0.2);
    this.saveSettings();
  },

  // Layout controls

  displaySideBySide() {
    this.layout = LAYOUT_SIDE_BY_SIDE;
    this.saveSettings();
  },
  displayTopAndBottom() {
    this.layout = LAYOUT_TOP_AND_BOTTOM;
    this.saveSettings();
  },

  // Markup controls

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

// Setup
window.addEventListener('alpine:init', () => {
  Alpine.data('editor', Editor);
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
