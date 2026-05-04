/* global Alpine, $, OpenSeadragon, Sanscript */
/* Transcription and proofreading interface. */

import { $ } from './core.ts';
import ProofingEditor, { XMLView, BLOCK_TYPES } from './prosemirror-editor.ts';
import { INLINE_MARKS, MARK_GROUPS } from './marks-config.ts';
import routes from './routes';

const CONFIG_KEY = 'proofing-editor';

function fuzzyMatch(query, text) {
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();
  let ti = 0;
  for (let qi = 0; qi < lowerQuery.length; qi += 1) {
    const idx = lowerText.indexOf(lowerQuery[qi], ti);
    if (idx < 0) return false;
    ti = idx + 1;
  }
  return true;
}

const ImageLayout = {
  Left: 'image-left',
  Right: 'image-right',
  Top: 'image-top',
  Bottom: 'image-bottom',
};

const ImageClasses = {
  Left: 'flex flex-row-reverse h-[90vh]',
  Right: 'flex flex-row h-[90vh]',
  Top: 'flex flex-col-reverse h-[90vh]',
  Bottom: 'flex flex-col h-[90vh]',
};

const ViewType = {
  Visual: 'visual',
  XML: 'xml',
};

const RevisionStatus = {
  Skip: 'skip',
  Reviewed0: 'reviewed-0',
  Reviewed1: 'reviewed-1',
  Reviewed2: 'reviewed-2',
};

const ModalType = {
  CommandPalette: 'command-palette',
  History: 'history',
  Submit: 'submit',
  Normalize: 'normalize',
  Transliterate: 'transliterate',
  AutoStructure: 'auto-structure',
};

// Parse OCR bounding boxes from TSV
function parseBoundingBoxes(tsvData) {
  if (!tsvData) return [];

  const lines = tsvData.trim().split('\n');
  return lines.map((line) => {
    const parts = line.split('\t');
    if (parts.length >= 5) {
      return {
        x1: parseInt(parts[0], 10),
        y1: parseInt(parts[1], 10),
        x2: parseInt(parts[2], 10),
        y2: parseInt(parts[3], 10),
        text: parts[4],
      };
    }
    return null;
  }).filter((box) => box !== null);
}

// Calculate Levenshtein distance between two strings
function levenshteinDistance(str1, str2) {
  const len1 = str1.length;
  const len2 = str2.length;

  const dp = Array(len1 + 1).fill(null).map(() => Array(len2 + 1).fill(0));

  for (let i = 0; i <= len1; i += 1) {
    dp[i][0] = i;
  }
  for (let j = 0; j <= len2; j += 1) {
    dp[0][j] = j;
  }

  for (let i = 1; i <= len1; i += 1) {
    for (let j = 1; j <= len2; j += 1) {
      if (str1[i - 1] === str2[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1];
      } else {
        dp[i][j] = Math.min(
          dp[i - 1][j] + 1, // deletion
          dp[i][j - 1] + 1, // insertion
          dp[i - 1][j - 1] + 1, // substitution
        );
      }
    }
  }

  return dp[len1][len2];
}

// Calculate similarity ratio between two strings (0 to 1, where 1 is identical)
function similarityRatio(str1, str2) {
  if (str1 === str2) return 1.0;
  if (!str1 || !str2) return 0.0;

  const distance = levenshteinDistance(str1, str2);
  const maxLen = Math.max(str1.length, str2.length);

  return 1 - (distance / maxLen);
}

// Group bounding boxes by line based on y-coordinate
function groupBoundingBoxesByLine(boxes) {
  if (!boxes || boxes.length === 0) return [];

  const Y_SENSITIVITY = 10;
  const sortedBoxes = [...boxes].sort((a, b) => {
    const yDiff = a.y1 - b.y1;
    if (Math.abs(yDiff) < Y_SENSITIVITY) {
      // If y-coordinates are very close, sort by x
      return a.x1 - b.x1;
    }
    return yDiff;
  });

  const lines = [];
  let currentLine = [sortedBoxes[0]];
  let currentLineY = sortedBoxes[0].y1;

  // Words on the same line should have similar y-coordinates
  for (let i = 1; i < sortedBoxes.length; i += 1) {
    const box = sortedBoxes[i];
    const yDiff = Math.abs(box.y1 - currentLineY);

    if (yDiff < Y_SENSITIVITY) {
      currentLine.push(box);
    } else {
      lines.push(currentLine);
      currentLine = [box];
      currentLineY = box.y1;
    }
  }

  if (currentLine.length > 0) {
    lines.push(currentLine);
  }

  return lines.map((lineBoxes) => {
    const text = lineBoxes.map((box) => box.text).join(' ');
    return {
      text,
      boxes: lineBoxes,
    };
  });
}

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

export default () => ({
  // Settings
  textZoom: 1,
  imageZoom: null,
  imageZoomMode: 'manual',
  layout: 'image-right',
  viewMode: ViewType.Visual,
  // [transliteration] the source script
  fromScript: 'hk',
  // [transliteration] the destination script
  toScript: 'devanagari',
  // If true, show advanced options (text, n, and merge_next)
  showAdvancedOptions: false,
  imeEnabled: false,
  showMarkToolbar: false,
  inlineMarks: INLINE_MARKS,
  markGroups: MARK_GROUPS,

  pageState: {},

  // Inline alert state
  alertMessage: '',
  alertType: 'success',
  alertVisible: false,
  alertTimeout: null,

  // Navigation state
  isNavigating: false,
  isSaving: false,
  showUnsavedWarning: false,
  pendingNavigation: null,
  lastSaveResponse: null,

  // Suggestion-review diff pane
  diffHtml: '',
  diffUpdating: false,
  _diffTimer: null,
  _diffSeq: 0,

  // Internal-only
  layoutClasses: ImageClasses.Right,
  isRunningOCR: false,
  isRunningLLMStructuring: false,
  isRunningStructuring: false,
  hasUnsavedChanges: false,
  xmlParseError: null,
  imageViewer: null,
  editor: null,
  // Modal state - only one modal open at a time
  activeModal: null,
  commandPaletteQuery: '',
  commandPaletteSelected: 0,
  historyLoading: false,
  historyRevisions: [],
  modalSummary: '',
  modalStatus: '',
  modalExplanation: '',
  originalContent: '',
  changesPreview: '',
  // Normalize modal options
  normalizeReplaceColonVisarga: true,
  normalizeReplaceSAvagraha: true,
  normalizeReplaceDoublePipe: true,
  // Auto-structure modal options
  autoStructureMatchStage: true,
  autoStructureMatchSpeaker: true,
  autoStructureMatchChaya: true,
  // Split pane ratio (percentage of the first/text pane)
  splitPercent: 50,
  // Track bounding box: auto-scroll image to show current bounding box
  trackBoundingBox: false,
  // If true, invert the colors of the page image
  invertImageColors: false,
  // If true, navigate to next page after submitting
  advanceAfterSubmit: false,
  // OCR bounding box highlighting
  boundingBoxes: [],
  boundingBoxLines: [],
  currentOverlay: null,

  init() {
    this.loadSettings();
    this.layoutClasses = this.getLayoutClasses();

    this.pageState = JSON.parse(this.$el.dataset.pageState);

    if (this.pageState.suggestion) {
      this.diffHtml = this.pageState.suggestion.diffHtml || '';
    }

    // Browser back/forward support
    window.addEventListener('popstate', this.onPopState.bind(this));

    // OCR bounding boxes (rendered on OSD image viewer)
    this.boundingBoxes = parseBoundingBoxes(this.pageState.ocrBoundingBoxes);
    this.boundingBoxLines = groupBoundingBoxesByLine(this.boundingBoxes);

    // Initialize editor (either ProofingEditor or XMLView based on viewMode)
    const editorElement = $('#prosemirror-editor');
    const initialContent = $('#content').value || '';
    this.originalContent = initialContent;

    // NOTE: always use Alpine.raw() to access the editor because Alpine reactivity/proxies breaks
    // the underlying data model and causes bizarre errors, e.g.:
    //
    // https://discuss.prosemirror.net/t/getting-rangeerror-applying-a-mismatched-transaction-even-with-trivial-code/4948/3
    this.editor = this.createEditor(editorElement, initialContent, this.viewMode);

    // Set `imageZoom` only after the viewer is fully initialized.
    this.imageViewer = initializeImageViewer(this.pageState.imageUrl);
    this.imageViewer.addHandler('open', () => {
      if (this.imageZoomMode === 'fit-width' || this.imageZoomMode === 'fit-height') {
        // Defer fit calls until after OSD's initial home animation and browser layout
        requestAnimationFrame(() => {
          if (this.imageZoomMode === 'fit-width') {
            this.imageViewer.viewport.fitHorizontally(true);
          } else {
            this.imageViewer.viewport.fitVertically(true);
          }
          this.imageZoom = this.imageViewer.viewport.getZoom();
        });
      } else {
        this.imageZoom = this.imageZoom || this.imageViewer.viewport.getHomeZoom();
        this.imageViewer.viewport.zoomTo(this.imageZoom);
      }
    });

    // Use `.bind(this)` so that `this` in the function refers to this app and
    // not `window`.
    window.onbeforeunload = this.onBeforeUnload.bind(this);
  },

  getCommands() {
    const markCommands = INLINE_MARKS.map((mark) => ({
      label: `Edit > Mark as '${mark.label}'`,
      code: `m${mark.name[0]}${mark.name.slice(1)}`,
      action: () => this.toggleMark(mark.name),
    }));

    const blockTypeCommands = BLOCK_TYPES.map((bt) => ({
      label: `Edit > Set block to '${bt.label}'`,
      code: `b${bt.tag}`,
      action: () => Alpine.raw(this.editor).setActiveBlockType(bt.tag),
    }));

    return [
      { label: 'Edit > Undo', action: () => this.undo() },
      { label: 'Edit > Redo', action: () => this.redo() },
      { label: 'Edit > Insert block', action: () => this.insertBlock() },
      { label: 'Edit > Insert break', code: 'ib', action: () => this.insertBreak() },
      { label: 'Edit > Delete active block', action: () => this.deleteBlock() },
      { label: 'Edit > Move block up', action: () => this.moveBlockUp() },
      { label: 'Edit > Move block down', action: () => this.moveBlockDown() },
      { label: 'Edit > Merge block up', action: () => this.mergeBlockUp() },
      { label: 'Edit > Merge block down', action: () => this.mergeBlockDown() },
      ...markCommands,
      ...blockTypeCommands,
      { label: 'View > Track bounding box', action: () => this.toggleTrackBoundingBox() },
      { label: 'View > Show image on left', action: () => this.displayImageOnLeft() },
      { label: 'View > Show image on right', action: () => this.displayImageOnRight() },
      { label: 'View > Show image on top', action: () => this.displayImageOnTop() },
      { label: 'View > Show image on bottom', action: () => this.displayImageOnBottom() },
      { label: 'Tools > Normalize', action: () => this.openNormalizeModal() },
      { label: 'Tools > Transliterate', code: 'tt', action: () => this.openTransliterateModal() },
      { label: 'Tools > Auto-structure', action: () => this.openAutoStructureModal() },
      { label: 'Tools > Transliterator IME', code: 'ti', action: () => this.toggleIME() },
    ];
  },

  getFilteredCommands() {
    const query = this.commandPaletteQuery;
    if (!query) return this.getCommands();

    const lowerQuery = query.toLowerCase();
    const codeMatches = [];
    const fuzzyMatches = [];

    for (const cmd of this.getCommands()) {
      const isShortcodeMatch = cmd.code && cmd.code.startsWith(lowerQuery);
      if (isShortcodeMatch) {
        codeMatches.push(cmd);
      } else if (fuzzyMatch(query, cmd.label)) {
        fuzzyMatches.push(cmd);
      }
    }

    return [...codeMatches, ...fuzzyMatches];
  },

  openCommandPalette() {
    this.activeModal = ModalType.CommandPalette;
    this.commandPaletteQuery = '';
    this.commandPaletteSelected = 0;

    this.$nextTick(() => {
      // requestAnimationFrame ensures the browser has painted the modal
      requestAnimationFrame(() => {
        const input = document.querySelector('#command-palette-input');
        if (input) {
          input.focus();
        }
      });
    });
  },

  closeModal() {
    this.activeModal = null;
  },

  handleCommandPaletteKeydown(e) {
    const filtered = this.getFilteredCommands();
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this.commandPaletteSelected = Math.min(this.commandPaletteSelected + 1, filtered.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      this.commandPaletteSelected = Math.max(this.commandPaletteSelected - 1, 0);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      this.executeSelectedCommand();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      this.closeModal();
    }
  },

  executeCommand(index) {
    const filtered = this.getFilteredCommands();
    if (filtered[index]) {
      filtered[index].action();
      if (this.activeModal === ModalType.CommandPalette) {
        // without this guard, alpine closes the wrong modal (eg transliterator)
        this.closeModal();
        Alpine.raw(this.editor).focus();
      }
    }
  },

  executeSelectedCommand() {
    this.executeCommand(this.commandPaletteSelected);
  },

  updateCommandPaletteQuery(query) {
    this.commandPaletteQuery = query;
    this.commandPaletteSelected = 0;
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
        this.imageZoomMode = settings.imageZoomMode || this.imageZoomMode;
        this.layout = settings.layout || this.layout;
        this.viewMode = settings.viewMode || this.viewMode;

        this.fromScript = settings.fromScript || this.fromScript;
        this.toScript = settings.toScript || this.toScript;
        this.showAdvancedOptions = settings.showAdvancedOptions || this.showAdvancedOptions;
        this.imeEnabled = settings.imeEnabled || false;

        this.trackBoundingBox = settings.trackBoundingBox || false;
        this.invertImageColors = settings.invertImageColors || false;
        this.advanceAfterSubmit = settings.advanceAfterSubmit || false;
        this.splitPercent = settings.splitPercent || 50;

        // Normalize preferences (default to true if not set)
        this.normalizeReplaceColonVisarga = settings.normalizeReplaceColonVisarga !== undefined
          ? settings.normalizeReplaceColonVisarga
          : true;
        this.normalizeReplaceSAvagraha = settings.normalizeReplaceSAvagraha !== undefined
          ? settings.normalizeReplaceSAvagraha
          : true;
        this.normalizeReplaceDoublePipe = settings.normalizeReplaceDoublePipe !== undefined
          ? settings.normalizeReplaceDoublePipe
          : true;
      } catch (error) {
        // Old settings are invalid -- rewrite with valid values.
        this.saveSettings();
      }
    }
  },

  saveSettings() {
    const settings = {
      textZoom: this.textZoom,
      imageZoom: this.imageZoom,
      imageZoomMode: this.imageZoomMode,
      layout: this.layout,
      viewMode: this.viewMode,
      fromScript: this.fromScript,
      toScript: this.toScript,
      showAdvancedOptions: this.showAdvancedOptions,
      imeEnabled: this.imeEnabled,
      trackBoundingBox: this.trackBoundingBox,
      invertImageColors: this.invertImageColors,
      normalizeReplaceColonVisarga: this.normalizeReplaceColonVisarga,
      normalizeReplaceSAvagraha: this.normalizeReplaceSAvagraha,
      normalizeReplaceDoublePipe: this.normalizeReplaceDoublePipe,
      advanceAfterSubmit: this.advanceAfterSubmit,
      splitPercent: this.splitPercent,
    };
    localStorage.setItem(CONFIG_KEY, JSON.stringify(settings));
  },

  getLayoutClasses() {
    const layoutClassMap = {
      [ImageLayout.Left]: ImageClasses.Left,
      [ImageLayout.Right]: ImageClasses.Right,
      [ImageLayout.Top]: ImageClasses.Top,
      [ImageLayout.Bottom]: ImageClasses.Bottom,
    };
    return layoutClassMap[this.layout] || ImageClasses.Right;
  },

  // Callbacks

  /** Displays a warning dialog if the user has unsaved changes and tries to navigate away. */
  onBeforeUnload(e) {
    if (this.hasUnsavedChanges) {
      // Keeps the dialog event.
      return true;
    }
    // Cancels the dialog event.
    return null;
  },

  // SPA navigation
  // ----------------------------------------------

  goToPrev() {
    if (this.pageState.prevSlug) this.navigateToPage(this.pageState.prevSlug);
  },

  goToNext() {
    if (this.pageState.nextSlug) this.navigateToPage(this.pageState.nextSlug);
  },

  navigateToPage(slug) {
    if (this.hasUnsavedChanges) {
      this.pendingNavigation = slug;
      this.showUnsavedWarning = true;
      return;
    }
    this.loadPage(slug, true);
  },

  confirmDiscardAndNavigate() {
    this.showUnsavedWarning = false;
    this.hasUnsavedChanges = false;
    const slug = this.pendingNavigation;
    this.pendingNavigation = null;
    if (slug) this.loadPage(slug, true);
  },

  cancelNavigation() {
    this.showUnsavedWarning = false;
    this.pendingNavigation = null;
  },

  async loadPage(slug, pushState) {
    this.isNavigating = true;
    this.dismissAlert();

    try {
      const url = routes.proofingPageData(this.pageState.projectSlug, slug);
      const response = await fetch(url);
      if (!response.ok) {
        this.showAlert('error', `Failed to load page: ${response.status}`);
        return;
      }

      const data = await response.json();

      this.pageState = data;

      // Update editor content
      Alpine.raw(this.editor).setText(data.content);
      $('#content').value = data.content;
      this.originalContent = data.content;

      // Update OpenSeadragon image
      this.updateImage(data.imageUrl);

      // Update OCR bounding boxes
      this.clearBoundingBoxHighlight();
      this.boundingBoxes = parseBoundingBoxes(data.ocrBoundingBoxes);
      this.boundingBoxLines = groupBoundingBoxesByLine(this.boundingBoxes);

      // Update hidden form fields
      const versionInput = $('input[name="version"]');
      if (versionInput) versionInput.value = data.version;
      const statusInput = $('input[name="status"]');
      if (statusInput) statusInput.value = data.status;

      // Reset state
      this.hasUnsavedChanges = false;
      this.isRunningOCR = false;
      this.isRunningLLMStructuring = false;
      this.isRunningStructuring = false;

      // Update browser history and title
      if (pushState) {
        const newUrl = data.editUrl;
        window.history.pushState({ pageSlug: slug }, '', newUrl);
      }
      document.title = `Edit: ${this.pageState.projectTitle}/${slug} | Ambuda`;
    } catch (error) {
      console.error('Navigation failed:', error);
      this.showAlert('error', 'Failed to load page. Please check your connection.');
    } finally {
      this.isNavigating = false;
    }
  },

  onPopState(event) {
    const slug = event.state && event.state.pageSlug;
    if (!slug || slug === this.pageState.pageSlug) return;

    if (this.hasUnsavedChanges) {
      // Re-push current state to "undo" the browser navigation
      window.history.pushState(
        { pageSlug: this.pageState.pageSlug },
        '',
        `/proofing/${this.pageState.projectSlug}/${this.pageState.pageSlug}/`,
      );
      this.pendingNavigation = slug;
      this.showUnsavedWarning = true;
      return;
    }

    this.loadPage(slug, false);
  },

  updateImage(newUrl) {
    const viewer = this.imageViewer;
    if (!viewer) return;

    const { world } = viewer;
    const itemCount = world.getItemCount();
    for (let i = itemCount - 1; i >= 0; i -= 1) {
      world.removeItem(world.getItemAt(i));
    }

    viewer.addTiledImage({
      tileSource: {
        type: 'image',
        url: newUrl,
        buildPyramid: false,
      },
      success: () => {
        if (this.imageZoomMode === 'fit-width') {
          requestAnimationFrame(() => viewer.viewport.fitHorizontally(true));
        } else if (this.imageZoomMode === 'fit-height') {
          requestAnimationFrame(() => viewer.viewport.fitVertically(true));
        } else {
          const zoom = this.imageZoom || viewer.viewport.getHomeZoom();
          viewer.viewport.zoomTo(zoom);
        }
      },
    });
  },

  // Inline alerts
  // ----------------------------------------------

  showAlert(type, message) {
    if (this.alertTimeout) {
      clearTimeout(this.alertTimeout);
      this.alertTimeout = null;
    }
    this.alertType = type;
    this.alertMessage = message;
    this.alertVisible = true;

    if (type === 'success' || type === 'info') {
      this.alertTimeout = setTimeout(() => this.dismissAlert(), 5000);
    }
  },

  dismissAlert() {
    this.alertVisible = false;
    this.alertMessage = '';
    if (this.alertTimeout) {
      clearTimeout(this.alertTimeout);
      this.alertTimeout = null;
    }
  },

  // Status badge helpers
  // ----------------------------------------------

  statusBadgeClasses() {
    const colorMap = {
      'reviewed-0': 'bg-red-200 text-red-800',
      'reviewed-1': 'bg-yellow-200 text-yellow-800',
      'reviewed-2': 'bg-green-200 text-green-800',
      skip: 'bg-gray-200 text-gray-800',
    };
    return colorMap[this.pageState.status] || '';
  },

  statusLabel() {
    const labelMap = {
      'reviewed-0': 'Needs work',
      'reviewed-1': 'Proofed once',
      'reviewed-2': 'Proofed twice',
      skip: 'Not relevant',
    };
    return labelMap[this.pageState.status] || this.pageState.status;
  },

  // OCR controls

  async fetchAndApply(apiPath, options = {}) {
    const url = `/api${apiPath}${this.pageState.projectSlug}/${this.pageState.pageSlug}/`;
    const response = await fetch(url, options);
    const content = response.ok ? await response.text() : '(server error)';
    Alpine.raw(this.editor).setText(content);
    $('#content').value = content;
  },

  async runOCR() {
    this.isRunningOCR = true;
    await this.fetchAndApply('/ocr/');
    this.isRunningOCR = false;
  },

  // Currently disabled.
  async runLLMStructuring() {
    this.isRunningLLMStructuring = true;
    const body = JSON.stringify({ content: Alpine.raw(this.editor).getText() });
    await this.fetchAndApply('/llm-structuring/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });
    this.isRunningLLMStructuring = false;
  },

  async runStructuring() {
    this.isRunningStructuring = true;
    const body = JSON.stringify({ content: Alpine.raw(this.editor).getText() });
    await this.fetchAndApply('/structuring/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });
    this.isRunningStructuring = false;
  },

  // Image zoom controls

  setImageZoom(zoom) {
    this.imageZoom = zoom;
    this.imageZoomMode = 'manual';
    this.imageViewer.viewport.zoomTo(zoom);
    this.saveSettings();
  },
  increaseImageZoom() { this.setImageZoom(this.imageZoom * 1.2); },
  decreaseImageZoom() { this.setImageZoom(this.imageZoom * 0.8); },
  resetImageZoom() { this.setImageZoom(this.imageViewer.viewport.getHomeZoom()); },
  fitImageWidth() {
    this.imageViewer.viewport.fitHorizontally();
    this.imageZoom = this.imageViewer.viewport.getZoom();
    this.imageZoomMode = 'fit-width';
    this.saveSettings();
  },
  fitImageHeight() {
    this.imageViewer.viewport.fitVertically();
    this.imageZoom = this.imageViewer.viewport.getZoom();
    this.imageZoomMode = 'fit-height';
    this.saveSettings();
  },

  // Text zoom controls

  updateTextZoom(zoom) {
    this.textZoom = zoom;
    Alpine.raw(this.editor).setTextZoom(zoom);
    this.saveSettings();
  },
  increaseTextSize() { this.updateTextZoom(this.textZoom + 0.1); },
  decreaseTextSize() { this.updateTextZoom(Math.max(0.5, this.textZoom - 0.1)); },
  resetTextSize() { this.updateTextZoom(1); },

  // Layout controls

  setLayout(layout) {
    this.layout = layout;
    this.layoutClasses = this.getLayoutClasses();
    this.saveSettings();
  },
  displayImageOnLeft() { this.setLayout(ImageLayout.Left); },
  displayImageOnRight() { this.setLayout(ImageLayout.Right); },
  displayImageOnTop() { this.setLayout(ImageLayout.Top); },
  displayImageOnBottom() { this.setLayout(ImageLayout.Bottom); },

  isHorizontalLayout() {
    return this.layout === ImageLayout.Left || this.layout === ImageLayout.Right;
  },

  isReversedLayout() {
    return this.layout === ImageLayout.Left || this.layout === ImageLayout.Top;
  },

  startResize() {
    const container = this.$refs.splitContainer;
    const horizontal = this.isHorizontalLayout();
    const reversed = this.isReversedLayout();

    const onMouseMove = (ev) => {
      const rect = container.getBoundingClientRect();
      let percent = horizontal
        ? ((ev.clientX - rect.left) / rect.width) * 100
        : ((ev.clientY - rect.top) / rect.height) * 100;
      if (reversed) percent = 100 - percent;
      if (Math.abs(percent - 50) < 2) percent = 50;
      this.splitPercent = Math.max(10, Math.min(90, percent));
    };

    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      this.saveSettings();
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    document.body.style.cursor = horizontal ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';
  },

  resetSplit() {
    this.splitPercent = 50;
    this.saveSettings();
  },

  createEditor(element, content, viewMode) {
    const onChange = () => {
      this.hasUnsavedChanges = true;
      $('#content').value = Alpine.raw(this.editor).getText();
      if (this.pageState.suggestion) {
        this.scheduleDiffUpdate();
      }
    };
    if (viewMode === ViewType.XML) {
      return new XMLView(element, content, onChange, this.textZoom);
    }
    return new ProofingEditor(
      element,
      content,
      onChange,
      this.showAdvancedOptions,
      this.textZoom,
      (context) => this.onActiveWordChange(context),
      () => ({ enabled: this.imeEnabled, fromScript: this.fromScript, toScript: this.toScript }),
    );
  },

  displayView(viewMode) {
    // Already showing -- just return.
    if (this.viewMode === viewMode) return;

    // Store state before switching.
    const editorElement = $('#prosemirror-editor');
    const content = Alpine.raw(this.editor).getText();
    Alpine.raw(this.editor).destroy();

    try {
      this.editor = this.createEditor(editorElement, content, viewMode);
    } catch (error) {
      this.xmlParseError = `Invalid XML: ${error.message}`;
      console.error('Failed to parse XML:', error);
      return;
    }

    // Reset state + focus
    this.viewMode = viewMode;
    this.xmlParseError = null;
    this.saveSettings();
    Alpine.raw(this.editor).focus();
  },
  displayVisualView() { this.displayView(ViewType.Visual); },
  displayXMLView() { this.displayView(ViewType.XML); },

  toggleTrackBoundingBox() {
    this.trackBoundingBox = !this.trackBoundingBox;
    this.saveSettings();
  },

  toggleInvertImageColors() {
    this.invertImageColors = !this.invertImageColors;
    this.saveSettings();
  },

  toggleIME() {
    this.imeEnabled = !this.imeEnabled;
    this.saveSettings();
  },

  toggleAdvancedOptions() {
    this.showAdvancedOptions = !this.showAdvancedOptions;
    this.saveSettings();

    if (this.viewMode === ViewType.Visual && Alpine.raw(this.editor).setShowAdvancedOptions) {
      Alpine.raw(this.editor).setShowAdvancedOptions(this.showAdvancedOptions);
    }
  },

  changeSelectedText(callback) {
    const selection = Alpine.raw(this.editor).getSelection();
    const replacement = callback(selection.text);
    Alpine.raw(this.editor).replaceSelection(replacement);
  },

  toggleMarkToolbar() {
    this.showMarkToolbar = !this.showMarkToolbar;
  },

  toggleMark(markName) {
    Alpine.raw(this.editor).toggleMark(markName);
  },

  marksForGroup(groupKey) {
    return this.inlineMarks.filter((m) => m.group === groupKey);
  },

  insertBlock() {
    Alpine.raw(this.editor).insertBlock();
  },

  insertBreak() {
    const editor = Alpine.raw(this.editor);
    const { state, dispatch } = editor.view;
    const breakNode = state.schema.nodes.break_separator.create();
    dispatch(state.tr.replaceSelectionWith(breakNode));
  },

  deleteBlock() {
    Alpine.raw(this.editor).deleteActiveBlock();
  },

  moveBlockUp() {
    Alpine.raw(this.editor).moveBlockUp();
  },

  moveBlockDown() {
    Alpine.raw(this.editor).moveBlockDown();
  },

  mergeBlockUp() {
    Alpine.raw(this.editor).mergeBlockUp();
  },

  mergeBlockDown() {
    Alpine.raw(this.editor).mergeBlockDown();
  },

  undo() {
    Alpine.raw(this.editor).undo();
  },

  redo() {
    Alpine.raw(this.editor).redo();
  },

  replaceColonVisarga() {
    this.changeSelectedText((s) => s.replaceAll(':', 'ः'));
  },

  replaceSAvagraha() {
    this.changeSelectedText((s) => s.replaceAll('S', 'ऽ'));
  },

  openNormalizeModal() {
    this.activeModal = ModalType.Normalize;
  },

  applyNormalization() {
    this.changeSelectedText((text) => {
      let normalized = text;

      if (this.normalizeReplaceColonVisarga) {
        normalized = normalized.replaceAll(':', 'ः');
      }

      if (this.normalizeReplaceSAvagraha) {
        normalized = normalized.replaceAll('S', 'ऽ');
      }

      if (this.normalizeReplaceDoublePipe) {
        normalized = normalized.replaceAll('||', '॥');
      }

      return normalized;
    });

    this.saveSettings();
    this.closeModal();
  },

  openTransliterateModal() {
    this.activeModal = ModalType.Transliterate;
  },

  openAutoStructureModal() {
    this.activeModal = ModalType.AutoStructure;
  },

  async applyAutoStructure() {
    const content = Alpine.raw(this.editor).getText();

    try {
      this.isRunningStructuring = true;
      const response = await fetch(routes.proofingAutoStructure(), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content,
          match_stage: this.autoStructureMatchStage,
          match_speaker: this.autoStructureMatchSpeaker,
          match_chaya: this.autoStructureMatchChaya,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      if (data.error) {
        this.xmlParseError = data.error;
      } else {
        Alpine.raw(this.editor).setText(data.content);
        this.closeModal();
      }
    } catch (error) {
      console.error('Auto-structure failed:', error);
      this.xmlParseError = `Auto-structure failed: ${error.message}`;
    } finally {
      this.isRunningStructuring = false;
    }
  },

  applyTransliteration() {
    this.changeSelectedText((s) => Sanscript.t(s, this.fromScript, this.toScript));
    this.saveSettings();
    this.closeModal();
  },

  transliterateSelectedText() {
    this.changeSelectedText((s) => Sanscript.t(s, this.fromScript, this.toScript));
    this.saveSettings();
  },

  copyCharacter(e) {
    const character = e.target.textContent;
    navigator.clipboard.writeText(character);
  },

  copyPageXML() {
    const content = Alpine.raw(this.editor).getText();
    navigator.clipboard.writeText(content);
  },

  async openHistoryModal() {
    this.activeModal = ModalType.History;
    this.historyLoading = true;
    this.historyRevisions = [];

    const url = `/api/proofing/${this.pageState.projectSlug}/${this.pageState.pageSlug}/history`;

    try {
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        this.historyRevisions = data.revisions || [];
      } else {
        console.error('Failed to fetch history:', response.status);
      }
    } catch (error) {
      console.error('Error fetching history:', error);
    } finally {
      this.historyLoading = false;
    }
  },

  getRevisionColorClass(status) {
    const colorMap = {
      [RevisionStatus.Reviewed0]: 'bg-red-200 text-red-800',
      [RevisionStatus.Reviewed1]: 'bg-yellow-200 text-yellow-800',
      [RevisionStatus.Reviewed2]: 'bg-green-200 text-green-800',
      [RevisionStatus.Skip]: 'bg-gray-200 text-gray-800',
    };
    return colorMap[status] || '';
  },

  openSubmitModal() {
    // Sync to text area.
    const currentContent = Alpine.raw(this.editor).getText();
    $('#content').value = currentContent;

    this.changesPreview = this.generateChangesPreview();

    const submitter = this.pageState.suggestion?.submitter;
    this.modalSummary = submitter ? `Accepted suggestion from ${submitter}` : '';
    this.modalStatus = this.pageState.status;
    this.modalExplanation = '';
    this.activeModal = ModalType.Submit;
  },

  generateChangesPreview() {
    const currentContent = Alpine.raw(this.editor).getText();

    // Trim and normalize whitespace for comparison
    const originalTrimmed = this.originalContent.trim();
    const currentTrimmed = currentContent.trim();

    if (originalTrimmed === currentTrimmed) {
      return '<span class="text-slate-500 italic">No changes made</span>';
    }

    // Simple diff: show both old and new content
    const originalLines = originalTrimmed.split('\n');
    const currentLines = currentTrimmed.split('\n');

    let diff = '';
    const maxLines = Math.max(originalLines.length, currentLines.length);

    // Show a simple comparison (first 15 changed lines)
    let changedCount = 0;
    let unchangedCount = 0;

    for (let i = 0; i < maxLines && changedCount < 15; i += 1) {
      const oldLine = originalLines[i] || '';
      const newLine = currentLines[i] || '';

      if (oldLine !== newLine) {
        changedCount += 1;
        unchangedCount = 0;

        if (oldLine && newLine) {
          diff += `<div class="text-red-700 bg-red-50 px-2 py-1 mb-0.5">- ${this.escapeHtml(oldLine)}</div>`;
          diff += `<div class="text-green-700 bg-green-50 px-2 py-1 mb-1">+ ${this.escapeHtml(newLine)}</div>`;
        } else if (oldLine) {
          diff += `<div class="text-red-700 bg-red-50 px-2 py-1 mb-1">- ${this.escapeHtml(oldLine)}</div>`;
        } else if (newLine) {
          diff += `<div class="text-green-700 bg-green-50 px-2 py-1 mb-1">+ ${this.escapeHtml(newLine)}</div>`;
        }
      } else {
        unchangedCount += 1;
        if (unchangedCount <= 2 && changedCount > 0) {
          diff += `<div class="text-slate-500 px-2 py-1 mb-0.5 text-xs">  ${this.escapeHtml(oldLine)}</div>`;
        }
      }
    }

    if (changedCount === 0) {
      return '<span class="text-slate-500 italic">Only whitespace changes detected</span>';
    }

    if (maxLines > 15 + changedCount) {
      diff += `<div class="text-slate-500 italic mt-2 text-xs">... and more changes (${maxLines} total lines)</div>`;
    }

    return diff || '<span class="text-slate-500 italic">Changes detected</span>';
  },

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  },

  async submitFormFromModal() {
    this.closeModal();
    const ok = await this.saveViaAPI();
    if (!ok) return;
    if (this.pageState.suggestion) {
      // Suggestion review: hop to the next pending suggestion or back to the index.
      const next = this.lastSaveResponse?.next_review_url
        || this.pageState.suggestion.nextReviewUrl;
      const fallback = this.lastSaveResponse?.index_url
        || this.pageState.suggestion.indexUrl;
      window.location.href = next || fallback;
      return;
    }
    if (this.advanceAfterSubmit && this.pageState.nextSlug) {
      await this.loadPage(this.pageState.nextSlug, true);
      this.showAlert('success', 'Saved previous page.');
    }
  },

  scheduleDiffUpdate() {
    if (!this.pageState.suggestion) return;
    if (this._diffTimer) clearTimeout(this._diffTimer);
    this.diffUpdating = true;
    this._diffTimer = setTimeout(() => this.refreshDiff(), 300);
  },

  async refreshDiff() {
    if (!this.pageState.suggestion) return;
    const seq = ++this._diffSeq;
    try {
      const csrfToken = $('input[name="csrf_token"]')?.value || '';
      const response = await fetch(this.pageState.suggestion.diffUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({ content: Alpine.raw(this.editor).getText() }),
      });
      const data = await response.json();
      // Drop stale responses if a newer request fired in the meantime.
      if (seq !== this._diffSeq) return;
      if (data.ok) {
        this.diffHtml = data.html || '';
      }
    } catch (e) {
      // Silently swallow — the diff pane is a hint, not critical.
      console.warn('Diff refresh failed:', e);
    } finally {
      if (seq === this._diffSeq) this.diffUpdating = false;
    }
  },

  async rejectSuggestion() {
    if (!this.pageState.suggestion || this.isSaving) return;
    if (!confirm('Reject this suggestion?')) return;
    this.isSaving = true;
    try {
      const csrfToken = $('input[name="csrf_token"]')?.value || '';
      const formData = new FormData();
      formData.append('csrf_token', csrfToken);
      const response = await fetch(this.pageState.suggestion.rejectUrl, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (data.ok) {
        this.hasUnsavedChanges = false;
        const next = data.next_review_url || this.pageState.suggestion.nextReviewUrl;
        const fallback = data.index_url || this.pageState.suggestion.indexUrl;
        window.location.href = next || fallback;
      } else {
        this.showAlert('error', data.message || 'Could not reject suggestion.');
        this.isSaving = false;
      }
    } catch (error) {
      console.error('Reject failed:', error);
      this.showAlert('error', 'Reject failed. Please check your connection.');
      this.isSaving = false;
    }
  },

  async saveViaAPI() {
    if (this.isSaving) return;
    this.isSaving = true;

    try {
      const content = Alpine.raw(this.editor).getText();
      const csrfToken = $('input[name="csrf_token"]')?.value || '';

      const formData = new FormData();
      formData.append('content', content);
      formData.append('version', this.pageState.version);
      formData.append('status', this.pageState.canSaveDirectly ? this.modalStatus : this.pageState.status);
      formData.append('summary', this.modalSummary);
      formData.append('explanation', this.modalExplanation);
      formData.append('csrf_token', csrfToken);

      const url = this.pageState.saveUrl
        || routes.proofingSave(this.pageState.projectSlug, this.pageState.pageSlug);
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
      });

      if (response.status === 401 || response.status === 403) {
        this.showAlert('error', 'Session expired. Please sign in again.');
        return;
      }

      const data = await response.json();
      this.lastSaveResponse = data;

      if (data.ok) {
        this.hasUnsavedChanges = false;
        this.originalContent = content;
        if (data.new_version !== undefined) {
          this.pageState.version = data.new_version;
          const versionInput = $('input[name="version"]');
          if (versionInput) versionInput.value = data.new_version;
        }
        if (data.new_status) {
          this.pageState.status = data.new_status;
          this.pageState.isR0 = data.new_status === 'reviewed-0';
          const statusInput = $('input[name="status"]');
          if (statusInput) statusInput.value = data.new_status;
        }
        this.showAlert('success', data.message);
        return true;
      } if (data.conflict_content) {
        this.showAlert('error', `${data.message}\n\nConflict content is available in the console.`);
        console.warn('Edit conflict content:', data.conflict_content);
        if (data.new_version !== undefined) {
          this.pageState.version = data.new_version;
        }
      } else {
        this.showAlert('error', data.message);
      }
    } catch (error) {
      console.error('Save failed:', error);
      this.showAlert('error', 'Save failed. Please check your connection.');
    } finally {
      setTimeout(() => { this.isSaving = false; }, 500);
    }
  },

  submitForm(e) {
    e.preventDefault();
    this.openSubmitModal();
  },

  // Bounding box highlighting
  // ----------------------------------------------

  onActiveWordChange(context) {
    if (!context || !this.boundingBoxLines.length || !this.imageViewer) {
      this.clearBoundingBoxHighlight();
      return;
    }

    const matchedBox = this.findBestMatchingBoundingBox(context);
    if (matchedBox) {
      this.highlightBoundingBox(matchedBox);
    } else {
      this.clearBoundingBoxHighlight();
    }
  },

  findBestMatchingBoundingBox(context) {
    const LINE_FUZZY_THRESHOLD = 0.7;
    const WORD_FUZZY_THRESHOLD = 0.7;

    const { word, line, wordIndex } = context;

    const normalizedWord = word.trim();
    const normalizedLine = line.trim();
    if (!normalizedWord || !normalizedLine) return null;

    let bestLine = null;
    let bestLineSimilarity = LINE_FUZZY_THRESHOLD;
    this.boundingBoxLines.forEach((boundingLine) => {
      if (bestLine && bestLineSimilarity === 1) return;
      const normalizedBoundingLine = boundingLine.text.trim();
      if (normalizedBoundingLine === normalizedLine) {
        bestLine = boundingLine;
        bestLineSimilarity = 1;
        return;
      }

      const similarity = similarityRatio(normalizedLine, normalizedBoundingLine);
      if (similarity > bestLineSimilarity) {
        bestLineSimilarity = similarity;
        bestLine = boundingLine;
      }
    });

    if (!bestLine) {
      return this.findBestMatchingBoundingBoxFallback(normalizedWord);
    }

    let bestWordBox = null;
    let bestWordSimilarity = WORD_FUZZY_THRESHOLD;

    for (let i = 0; i < bestLine.boxes.length; i += 1) {
      const box = bestLine.boxes[i];
      const boxText = box.text.toLowerCase();

      if (boxText === normalizedWord) {
        return box;
      }

      const similarity = similarityRatio(normalizedWord, boxText);
      if (similarity > bestWordSimilarity) {
        bestWordSimilarity = similarity;
        bestWordBox = box;
      }
    }

    return bestWordBox;
  },

  // Fallback to old algorithm when line matching fails
  findBestMatchingBoundingBoxFallback(normalizedWord) {
    for (let i = 0; i < this.boundingBoxes.length; i += 1) {
      const box = this.boundingBoxes[i];
      if (box.text.toLowerCase() === normalizedWord) {
        return box;
      }
    }

    const FUZZY_THRESHOLD = 0.7;
    let bestMatch = null;
    let bestSimilarity = FUZZY_THRESHOLD;

    this.boundingBoxes.forEach((box) => {
      const boxText = box.text.toLowerCase();
      const similarity = similarityRatio(normalizedWord, boxText);

      if (similarity > bestSimilarity) {
        bestSimilarity = similarity;
        bestMatch = box;
      }
    });

    return bestMatch;
  },

  highlightBoundingBox(box) {
    this.clearBoundingBoxHighlight();

    if (!this.imageViewer || !this.imageViewer.world.getItemAt(0)) {
      return;
    }

    const tiledImage = this.imageViewer.world.getItemAt(0);
    const imageSize = tiledImage.getContentSize();

    // OpenSeadragon uses a coordinate system where the image width is normalized to 1.0
    // and all other dimensions (including y-axis) are scaled relative to the width.
    // This maintains the aspect ratio. So we divide ALL coordinates by image width.
    const x = box.x1 / imageSize.x;
    const y = box.y1 / imageSize.x; // Note: dividing by width, not height
    const width = (box.x2 - box.x1) / imageSize.x;
    const height = (box.y2 - box.y1) / imageSize.x; // Note: dividing by width, not height

    const overlayElement = document.createElement('div');
    overlayElement.className = 'ocr-bounding-box-highlight';
    overlayElement.style.border = '1px solid red';
    overlayElement.style.boxSizing = 'border-box';
    overlayElement.style.pointerEvents = 'none';

    const rect = new OpenSeadragon.Rect(x, y, width, height);

    this.imageViewer.addOverlay({
      element: overlayElement,
      location: rect,
    });

    this.currentOverlay = overlayElement;

    if (this.trackBoundingBox) {
      const bounds = this.imageViewer.viewport.getBounds();
      const outX = x < bounds.x || x + width > bounds.x + bounds.width;
      const outY = y < bounds.y || y + height > bounds.y + bounds.height;

      if (outX || outY) {
        const center = this.imageViewer.viewport.getCenter();
        const panX = outX ? x + width / 2 : center.x;
        const panY = outY ? y + height / 2 : center.y;
        this.imageViewer.viewport.panTo(new OpenSeadragon.Point(panX, panY));
      }
    }
  },

  clearBoundingBoxHighlight() {
    if (this.currentOverlay) {
      try {
        this.imageViewer.removeOverlay(this.currentOverlay);
      } catch (e) {
        // eslint-disable-next-line no-console
        console.debug('Failed to remove overlay:', e);
      }
      this.currentOverlay = null;
    }
  },
});
