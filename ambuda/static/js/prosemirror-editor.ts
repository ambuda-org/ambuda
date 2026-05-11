/* eslint-disable max-classes-per-file */
import {
  EditorState, Plugin, Transaction, Selection,
} from 'prosemirror-state';
import { EditorView, Decoration, DecorationSet } from 'prosemirror-view';
import {
  Schema, Node as PMNode, Mark, Fragment,
  DOMParser as PMDOMParser, DOMSerializer, NodeSpec, MarkSpec,
} from 'prosemirror-model';
import { keymap } from 'prosemirror-keymap';
import { history, undo as pmUndo, redo as pmRedo } from 'prosemirror-history';
import { baseKeymap } from 'prosemirror-commands';
import { INLINE_MARKS, getAllMarkNames, type MarkName } from './marks-config.ts';
import routes from './routes';

// Keep in sync with ambuda/utils/structuring.py::BlockType
export const BLOCK_TYPES = [
  { tag: 'p', label: 'Paragraph', color: 'blue' },
  { tag: 'verse', label: 'Verse', color: 'purple' },
  { tag: 'heading', label: 'Heading', color: 'orange' },
  { tag: 'title', label: 'Title', color: 'indigo' },
  { tag: 'subtitle', label: 'Subtitle', color: 'pink' },
  { tag: 'footnote', label: 'Footnote', color: 'green' },
  { tag: 'trailer', label: 'Trailer', color: 'teal' },
  { tag: 'ignore', label: 'Ignore', color: 'gray' },
  { tag: 'metadata', label: 'Metadata', color: 'gray' },
];

const BLOCK_TYPE_COLORS: Record<string, string> = Object.fromEntries(
  BLOCK_TYPES.map((bt) => [bt.tag, bt.color === 'gray' ? 'border-gray-300' : `border-${bt.color}-400`]),
);

// Nodes are the basic pieces of the document.
const nodes: Record<string, NodeSpec> = {
  doc: {
    content: 'block+',
  },
  block: {
    content: 'inline*',
    attrs: {
      // The block type.
      type: { default: 'p' },
      // The text that this block belongs to
      text: { default: null },
      // Slug ID
      n: { default: null },
      // Footnote mark
      mark: { default: null },
      lang: { default: null },
      // If true, merge this block with the next when publishing at ext.
      merge_next: { default: false },
    },
    group: 'block',
    code: true,
    preserveWhitespace: 'full',
    parseDOM: [
      {
        // matched XML tags
        tag: 'p, verse, heading, title, subtitle, footnote, trailer, ignore',
        preserveWhitespace: 'full',
        getAttrs(dom: HTMLElement) {
          return {
            type: dom.tagName.toLowerCase(),
            text: dom.getAttribute('text'),
            n: dom.getAttribute('n'),
            mark: dom.getAttribute('mark'),
            lang: dom.getAttribute('lang'),
            merge_next: dom.getAttribute('merge-next') === 'true',
          };
        },
      },
    ],
    toDOM(node: PMNode) {
      const attrs: Record<string, string> = {};
      if (node.attrs.text) attrs.text = node.attrs.text;
      if (node.attrs.n) attrs.n = node.attrs.n;
      if (node.attrs.mark) attrs.mark = node.attrs.mark;
      if (node.attrs.lang) attrs.lang = node.attrs.lang;
      if (node.attrs.merge_next) attrs['merge-next'] = 'true';

      // format: [tag, attrs, "hole" where children should be inserted]
      return [node.attrs.type || 'p', attrs, 0];
    },
  },
  break_separator: {
    inline: true,
    group: 'inline',
    atom: true,
    attrs: {
      type: { default: null },
    },
    parseDOM: [
      {
        tag: 'break',
        getAttrs(dom: HTMLElement) {
          return { type: dom.getAttribute('type') || null };
        },
      },
      { tag: 'span.pm-break-marker' },
    ],
    toDOM(node: PMNode) {
      const label = node.attrs.type ? `¶ ${node.attrs.type}` : '¶';
      return ['span', { class: 'pm-break-marker', contenteditable: 'false' }, label];
    },
  },
  text: {
    group: 'inline',
  },
};

// Marks are labels attached to text.
const marks: Record<string, MarkSpec> = Object.fromEntries(
  INLINE_MARKS.map((markConfig) => [
    markConfig.name,
    {
      parseDOM: [{ tag: markConfig.name }],
      toDOM() {
        return ['span', { class: markConfig.className }, 0];
      },
      ...(markConfig.excludes ? { excludes: markConfig.excludes } : {}),
    },
  ]),
);

const customSchema = new Schema({ nodes, marks });

// Extract the word at the cursor position along with line context
function getWordAtCursor(
  state: EditorState,
): { word: string; lineText: string; wordIndex: number } | null {
  const { $from } = state.selection;
  const node = $from.parent;

  if (node.type.name !== 'block') {
    return null;
  }

  const buf: string[] = [];
  node.forEach((child) => {
    if (child.isText && child.text) {
      buf.push(child.text);
    }
  });
  const text = buf.join('');
  const cursorOffset = $from.parentOffset;

  if (!text || cursorOffset > text.length) {
    return null;
  }

  const lineStart = text.lastIndexOf('\n', cursorOffset - 1) + 1;
  const lineEnd = text.indexOf('\n', cursorOffset);
  const line = text.substring(lineStart, lineEnd === -1 ? text.length : lineEnd).trim();

  const cursorLineOFfset = cursorOffset - lineStart;
  const words = line.split(/\s+/).filter((w) => w.length > 0);
  let pos = 0;
  for (let i = 0; i < words.length; i += 1) {
    const wordStart = line.indexOf(words[i], pos);
    const wordEnd = wordStart + words[i].length;
    if (cursorLineOFfset >= wordStart && cursorLineOFfset <= wordEnd) {
      return { word: words[i], line, wordIndex: i };
    }
    pos = wordEnd;
  }

  return null;
}

// Plugin to track cursor changes and emit active word
function activeWordPlugin(
  onActiveWordChange?: (context: { word: string; line: string; wordIndex: number } | null) => void,
) {
  return new Plugin({
    view() {
      return {
        update(view, prevState) {
          if (!view.state.selection.eq(prevState.selection)) {
            const context = getWordAtCursor(view.state);
            if (onActiveWordChange) {
              onActiveWordChange(context);
            }
          }
        },
      };
    },
  });
}

type IMEConfig = { enabled: boolean; fromScript: string; toScript: string };

function imePlugin(getConfig: () => IMEConfig) {
  let buffer = '';
  let bufferStart = -1;
  let popup: HTMLDivElement | null = null;
  let dispatching = false;

  function ensurePopup(): HTMLDivElement {
    if (!popup) {
      popup = document.createElement('div');
      popup.className = 'ime-popup';
      popup.style.display = 'none';
      document.body.appendChild(popup);
    }
    return popup;
  }

  function updatePopup(view: EditorView) {
    const el = ensurePopup();
    if (!buffer) {
      el.style.display = 'none';
      return;
    }

    const config = getConfig();
    const transliterated = (window as any).Sanscript.t(buffer, config.fromScript, config.toScript);
    el.textContent = transliterated;
    el.style.display = '';

    try {
      const coords = view.coordsAtPos(bufferStart);
      el.style.left = `${coords.left}px`;
      const popupHeight = el.offsetHeight || 24;
      const spaceBelow = window.innerHeight - coords.bottom;
      if (spaceBelow < popupHeight + 8) {
        el.style.top = `${coords.top - popupHeight - 4}px`;
      } else {
        el.style.top = `${coords.bottom + 4}px`;
      }
    } catch {
      // coordsAtPos can fail if DOM layout is unavailable
    }
  }

  function hidePopup() {
    ensurePopup().style.display = 'none';
  }

  function commitBuffer(view: EditorView, suffix: string = '') {
    if (!buffer) return;
    dispatching = true;
    const config = getConfig();
    const text = (window as any).Sanscript.t(buffer, config.fromScript, config.toScript) + suffix;
    const bufferEnd = bufferStart + buffer.length;
    view.dispatch(view.state.tr.insertText(text, bufferStart, bufferEnd));
    buffer = '';
    bufferStart = -1;
    hidePopup();
    dispatching = false;
  }

  function discardBuffer(view: EditorView) {
    if (!buffer) return;
    dispatching = true;
    const bufferEnd = bufferStart + buffer.length;
    view.dispatch(view.state.tr.delete(bufferStart, bufferEnd));
    buffer = '';
    bufferStart = -1;
    hidePopup();
    dispatching = false;
  }

  return new Plugin({
    view() {
      return {
        update(view: EditorView, prevState: EditorState) {
          // Commit if selection moved outside buffer (e.g. mouse click)
          if (buffer && !dispatching && !view.state.selection.eq(prevState.selection)) {
            const { from } = view.state.selection;
            if (from < bufferStart || from > bufferStart + buffer.length) {
              commitBuffer(view);
            }
          }
        },
        destroy() {
          if (popup && popup.parentNode) {
            popup.parentNode.removeChild(popup);
            popup = null;
          }
        },
      };
    },
    props: {
      handleKeyDown(view: EditorView, event: KeyboardEvent) {
        const config = getConfig();
        if (!config.enabled) return false;

        const { from } = view.state.selection;
        const bufferEnd = bufferStart + buffer.length;

        if (event.key === 'Escape') {
          if (buffer) {
            discardBuffer(view);
            return true;
          }
          return false;
        }

        if (event.key === 'Enter') {
          if (buffer) {
            commitBuffer(view);
            return true;
          }
          return false;
        }

        if (event.key === ' ') {
          if (buffer) {
            commitBuffer(view, ' ');
            return true;
          }
          return false;
        }

        if (event.key === 'Backspace') {
          if (buffer) {
            const offset = from - bufferStart;
            if (offset <= 0) {
              commitBuffer(view);
              return false;
            }
            dispatching = true;
            view.dispatch(view.state.tr.delete(from - 1, from));
            dispatching = false;
            buffer = buffer.slice(0, offset - 1) + buffer.slice(offset);
            if (!buffer) {
              bufferStart = -1;
              hidePopup();
            } else {
              updatePopup(view);
            }
            return true;
          }
          return false;
        }

        if (event.key === 'ArrowLeft') {
          if (buffer) {
            if (from > bufferStart) return false;
            commitBuffer(view);
          }
          return false;
        }

        if (event.key === 'ArrowRight') {
          if (buffer) {
            if (from < bufferEnd) return false;
            commitBuffer(view);
          }
          return false;
        }

        if (event.key.length === 1 && !event.ctrlKey && !event.metaKey) {
          event.preventDefault();
          dispatching = true;
          if (!buffer) {
            bufferStart = from;
            view.dispatch(view.state.tr.insertText(event.key, from, from));
            buffer = event.key;
          } else {
            const offset = from - bufferStart;
            view.dispatch(view.state.tr.insertText(event.key, from, from));
            buffer = buffer.slice(0, offset) + event.key + buffer.slice(offset);
          }
          dispatching = false;
          updatePopup(view);
          return true;
        }

        if (['Shift', 'Control', 'Alt', 'Meta', 'CapsLock'].includes(event.key)) {
          return false;
        }

        if (buffer) {
          commitBuffer(view);
        }
        return false;
      },
    },
  });
}

function createBlockBelow(state: EditorState, dispatch?: (tr: Transaction) => void): boolean {
  const { $from, $to } = state.selection;
  const currentBlock = $from.node($from.depth);

  if (currentBlock.type.name !== 'block') {
    return false;
  }

  if (dispatch) {
    const blockPos = $from.before($from.depth);
    const blockStart = blockPos + 1; // +1 to account for the block node itself
    const cursorPos = $from.pos;

    const cursorInBlock = cursorPos - blockStart;

    const contentBefore: PMNode[] = [];
    const contentAfter: PMNode[] = [];

    let currentPos = 0;
    currentBlock.forEach((child, offset) => {
      const childEnd = currentPos + child.nodeSize;

      if (childEnd <= cursorInBlock) {
        // Entire child is before cursor
        contentBefore.push(child);
      } else if (currentPos >= cursorInBlock) {
        // Entire child is after cursor
        contentAfter.push(child);
      } else if (child.isText) {
        // Cursor is within this child (text node)
        const splitPoint = cursorInBlock - currentPos;
        const textBefore = child.text!.substring(0, splitPoint);
        const textAfter = child.text!.substring(splitPoint);

        if (textBefore) {
          contentBefore.push(state.schema.text(textBefore, child.marks));
        }
        if (textAfter) {
          contentAfter.push(state.schema.text(textAfter, child.marks));
        }
      }

      currentPos = childEnd;
    });

    let { tr } = state;
    const newCurrentBlock = state.schema.nodes.block.create(
      currentBlock.attrs,
      contentBefore.length > 0 ? contentBefore : undefined,
    );
    tr = tr.replaceWith(blockPos, blockPos + currentBlock.nodeSize, newCurrentBlock);

    const afterPos = blockPos + newCurrentBlock.nodeSize;
    const newBlock = state.schema.nodes.block.create(
      { type: 'p' },
      contentAfter.length > 0 ? contentAfter : undefined,
    );
    tr = tr.insert(afterPos, newBlock);

    // Set cursor at the beginning of the new block
    tr = tr.setSelection(Selection.near(tr.doc.resolve(afterPos + 1)));

    dispatch(tr);
  }

  return true;
}

class BlockView {
  dom: HTMLElement;

  contentDOM: HTMLElement;

  node: PMNode;

  view: EditorView;

  getPos: () => number | undefined;

  controlsDOM: HTMLElement;

  typeSelect: HTMLSelectElement;

  textInput: HTMLInputElement;

  textLabel: HTMLSpanElement;

  nInput: HTMLInputElement;

  nLabel: HTMLSpanElement;

  markInput: HTMLInputElement;

  markLabel: HTMLSpanElement;

  mergeCheckbox: HTMLInputElement;

  mergeLabel: HTMLLabelElement;

  dropdownButton: HTMLButtonElement;

  dropdownMenu: HTMLElement;

  dropdownWrapper: HTMLElement;

  mergeUpBtn: HTMLButtonElement;

  mergeDownBtn: HTMLButtonElement;

  dropdownOpen: boolean;

  editor: any; // ProofingEditor instance

  validationBadge: HTMLSpanElement;

  validationDetail: HTMLDivElement;

  private _lastCheckText: string;

  private _lastCheckType: string;

  private _checkDebounceTimer: ReturnType<typeof setTimeout> | null;

  private createLabeledInput(attrName: string, labelText: string, placeholder: string, width: string, extraClass: string = ''): { label: HTMLSpanElement; input: HTMLInputElement } {
    const label = document.createElement('span');
    label.className = 'text-slate-400 text-[11px] ml-1';
    label.textContent = labelText;
    this.controlsDOM.appendChild(label);

    const input = document.createElement('input');
    input.type = 'text';
    input.value = this.node.attrs[attrName] || '';
    input.placeholder = placeholder;
    input.className = `border border-slate-300 bg-transparent text-xs text-slate-600 ${width} px-1 py-0 hover:bg-slate-100 rounded ${extraClass}`;
    input.addEventListener('change', () => this.updateNodeAttr(attrName, input.value || null));
    this.controlsDOM.appendChild(input);

    return { label, input };
  }

  private createDropdownButton(icon: string, label: string, handler: () => void, className: string = ''): HTMLButtonElement {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `w-full text-left px-3 py-2 text-xs hover:bg-slate-100 flex items-center gap-2 ${className}`;
    btn.innerHTML = `<span>${icon}</span> ${label}`;
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      handler();
      this.closeDropdown();
    });
    this.dropdownMenu.appendChild(btn);
    return btn;
  }

  constructor(node: PMNode, view: EditorView, getPos: () => number | undefined, editor: any) {
    this.node = node;
    this.view = view;
    this.getPos = getPos;
    this.editor = editor;
    this.dropdownOpen = false;

    if (editor.blockViews) {
      editor.blockViews.add(this);
    }

    this.dom = document.createElement('div');
    this.setBlockDOMClasses();

    // Controls bar
    this.controlsDOM = document.createElement('div');
    this.controlsDOM.className = 'flex gap-1 mb-1 px-1.5 py-1 text-xs text-slate-500 items-center bg-slate-50 rounded leading-tight';

    // Type dropdown
    this.typeSelect = document.createElement('select');
    this.typeSelect.className = 'border border-slate-300 bg-white text-xs font-medium cursor-pointer hover:bg-slate-100 rounded px-1 py-0';
    const currentType = node.attrs.type || 'p';
    BLOCK_TYPES.forEach((bt) => {
      const option = document.createElement('option');
      option.value = bt.tag;
      option.textContent = bt.label;
      if (bt.tag === currentType) option.selected = true;
      this.typeSelect.appendChild(option);
    });
    this.typeSelect.addEventListener('change', () => this.updateNodeAttr('type', this.typeSelect.value));
    this.controlsDOM.appendChild(this.typeSelect);

    // Attribute inputs
    // TODO: rename `text` to `label` in storage.
    const text = this.createLabeledInput('text', 'label=', 'label', 'w-20');
    this.textLabel = text.label;
    this.textInput = text.input;
    this.textLabel.style.display = this.editor.showAdvancedOptions ? '' : 'none';
    this.textInput.style.display = this.editor.showAdvancedOptions ? '' : 'none';

    const n = this.createLabeledInput('n', 'n=', '#', 'w-12', 'font-mono');
    this.nLabel = n.label;
    this.nInput = n.input;

    const mark = this.createLabeledInput('mark', 'mark=', 'mark', 'w-16', 'font-mono');
    this.markLabel = mark.label;
    this.markInput = mark.input;

    this.updateFieldVisibility();

    // Merge checkbox
    this.mergeLabel = document.createElement('label');
    this.mergeLabel.className = 'flex items-center gap-0.5 cursor-pointer hover:bg-slate-100 px-1 rounded ml-1';
    this.mergeLabel.style.display = this.editor.showAdvancedOptions ? '' : 'none';

    this.mergeCheckbox = document.createElement('input');
    this.mergeCheckbox.type = 'checkbox';
    this.mergeCheckbox.className = 'w-3 h-3';
    this.mergeCheckbox.checked = node.attrs.merge_next || false;
    this.mergeCheckbox.addEventListener('change', () => this.updateNodeAttr('merge_next', this.mergeCheckbox.checked));

    const mergeText = document.createElement('span');
    mergeText.className = 'text-[11px]';
    mergeText.textContent = 'merge next';

    this.mergeLabel.appendChild(this.mergeCheckbox);
    this.mergeLabel.appendChild(mergeText);
    this.controlsDOM.appendChild(this.mergeLabel);

    // Unified validation badge
    this._lastCheckText = '';
    this._lastCheckType = node.attrs.type || 'p';
    this._checkDebounceTimer = null;

    this.validationBadge = document.createElement('span');
    this.validationBadge.className = 'cursor-pointer select-none ml-1';
    this.validationBadge.style.display = 'none';
    this.validationBadge.addEventListener('click', (e) => {
      e.preventDefault();
      if (this.validationDetail.innerHTML) {
        this.validationDetail.style.display = this.validationDetail.style.display === 'none' ? 'block' : 'none';
      }
    });
    this.controlsDOM.appendChild(this.validationBadge);

    this.validationDetail = document.createElement('div');
    this.validationDetail.className = 'text-xs px-2 py-1 bg-slate-50 border border-slate-200 rounded mb-1';
    this.validationDetail.style.display = 'none';

    // Dropdown
    this.dropdownWrapper = document.createElement('div');
    this.dropdownWrapper.className = 'ml-auto relative';

    this.dropdownButton = document.createElement('button');
    this.dropdownButton.type = 'button';
    this.dropdownButton.className = 'text-[11px] px-2 py-0.5 bg-slate-100 hover:bg-slate-200 rounded border border-slate-300';
    this.dropdownButton.title = 'Block actions';
    this.dropdownButton.innerHTML = '&hellip;';
    this.dropdownButton.addEventListener('click', (e) => {
      e.preventDefault();
      this.toggleDropdown();
    });
    this.dropdownWrapper.appendChild(this.dropdownButton);

    this.dropdownMenu = document.createElement('div');
    this.dropdownMenu.className = 'absolute right-0 mt-1 bg-white border border-slate-300 rounded shadow-lg z-10 min-w-[140px]';
    this.dropdownMenu.style.display = 'none';

    this.createDropdownButton('<span class="text-green-600">+</span>', 'Add below', () => this.addBlockBelow());
    this.createDropdownButton('↑', 'Move up', () => this.moveBlockUp(), 'border-t border-slate-200');
    this.createDropdownButton('↓', 'Move down', () => this.moveBlockDown());
    this.mergeUpBtn = this.createDropdownButton('⤒', 'Merge up', () => this.mergeBlockUp(), 'border-t border-slate-200');
    this.mergeDownBtn = this.createDropdownButton('⤓', 'Merge down', () => this.mergeBlockDown());
    this.createDropdownButton('×', 'Remove', () => this.removeBlock(), 'border-t border-slate-200 hover:!bg-red-50 text-red-700');

    this.dropdownWrapper.appendChild(this.dropdownMenu);
    this.controlsDOM.appendChild(this.dropdownWrapper);

    document.addEventListener('click', (e) => {
      if (this.dropdownOpen && !this.dropdownWrapper.contains(e.target as Node)) {
        this.closeDropdown();
      }
    });

    this.dom.appendChild(this.controlsDOM);
    this.dom.appendChild(this.validationDetail);

    // Content area
    this.contentDOM = document.createElement('div');
    this.updateContentDOMClasses();
    this.contentDOM.style.fontSize = `${this.editor.textZoom}rem`;
    this.contentDOM.contentEditable = 'true';
    this.dom.appendChild(this.contentDOM);

    // Record the initial text so update() doesn't re-trigger on the
    // same content. The actual initial check is done as a batch by
    // the editor after all BlockViews are constructed.
    const blockType = node.attrs.type || 'p';
    if (blockType !== 'ignore' && blockType !== 'metadata') {
      this._lastCheckText = node.textContent;
    }
  }

  setBlockDOMClasses() {
    const blockType = this.node.attrs.type || 'p';
    this.dom.className = `border-l-4 pl-4 mb-3 transition-colors ${BLOCK_TYPE_COLORS[blockType] || 'border-gray-400'}`;
    if (this.node.attrs.merge_next) {
      this.dom.classList.add('bg-yellow-50', '!border-dashed');
    }
  }

  updateFieldVisibility() {
    const isFootnote = this.node.attrs.type === 'footnote';
    const showAdvanced = this.editor.showAdvancedOptions;

    // N field: show for non-footnote blocks when advanced options are enabled
    if (this.nLabel && this.nInput) {
      const showN = !isFootnote && showAdvanced;
      this.nLabel.style.display = showN ? '' : 'none';
      this.nInput.style.display = showN ? '' : 'none';
    }

    // Mark field: always show for footnote blocks, hide for others
    if (this.markLabel && this.markInput) {
      this.markLabel.style.display = isFootnote ? '' : 'none';
      this.markInput.style.display = isFootnote ? '' : 'none';
    }
  }

  updateContentDOMClasses() {
    const blockType = this.node.attrs.type || 'p';
    this.contentDOM.className = 'pm-content-dom deva-serif';
    if (blockType === 'ignore') {
      this.contentDOM.classList.add('bg-gray-100', 'text-gray-500');
    } else if (blockType === 'metadata') {
      this.contentDOM.classList.add('pm-metadata');
    }
  }

  updateNodeAttr(name: string, value: any) {
    const pos = this.getPos();
    if (pos === undefined) return;

    const tr = this.view.state.tr.setNodeMarkup(pos, undefined, {
      ...this.node.attrs,
      [name]: value,
    });
    this.view.dispatch(tr);

    if (name === 'type' || name === 'merge_next') {
      this.setBlockDOMClasses();
      if (name === 'type') {
        this.updateContentDOMClasses();
        this.updateFieldVisibility();
      }
    }
  }

  update(node: PMNode) {
    if (node.type !== this.node.type) return false;

    this.node = node;

    this.setBlockDOMClasses();
    this.updateContentDOMClasses();

    const blockType = node.attrs.type || 'p';
    if (this.typeSelect.value !== blockType) {
      this.typeSelect.value = blockType;
    }
    if (this.textInput.value !== (node.attrs.text || '')) {
      this.textInput.value = node.attrs.text || '';
    }
    if (this.nInput && this.nInput.value !== (node.attrs.n || '')) {
      this.nInput.value = node.attrs.n || '';
    }
    if (this.markInput && this.markInput.value !== (node.attrs.mark || '')) {
      this.markInput.value = node.attrs.mark || '';
    }
    if (this.mergeCheckbox.checked !== node.attrs.merge_next) {
      this.mergeCheckbox.checked = node.attrs.merge_next;
    }

    this.updateFieldVisibility();

    const currentText = node.textContent;

    // Trigger re-check if text or block type changed
    if (blockType === 'ignore' || blockType === 'metadata') {
      this.validationBadge.style.display = 'none';
      this.validationDetail.style.display = 'none';
      if (this._checkDebounceTimer) {
        clearTimeout(this._checkDebounceTimer);
        this._checkDebounceTimer = null;
      }
      this._lastCheckText = '';
      this._lastCheckType = blockType;
    } else if (currentText !== this._lastCheckText || blockType !== this._lastCheckType) {
      this.scheduleCheck(currentText);
      this._lastCheckType = blockType;
    }

    return true;
  }

  stopEvent(event: Event) {
    // Allow all events within the contentDOM (for editing)
    // but prevent events in the controls and validation detail from affecting ProseMirror
    const target = event.target as Node;
    return this.controlsDOM.contains(target) || this.validationDetail.contains(target);
  }

  ignoreMutation(mutation: MutationRecord) {
    // Ignore all mutations outside contentDOM (controls bar, validation detail, etc.)
    const target = mutation.target as Node;
    if (this.controlsDOM.contains(target) || this.validationDetail.contains(target)) {
      return true;
    }
    if (mutation.type === 'attributes' && target !== this.contentDOM) {
      return true;
    }
    return false;
  }

  updateAdvancedOptionsVisibility() {
    const show = this.editor.showAdvancedOptions;
    this.textLabel.style.display = show ? '' : 'none';
    this.textInput.style.display = show ? '' : 'none';
    this.mergeLabel.style.display = show ? '' : 'none';
    // Update n and mark field visibility based on both advanced options and block type
    this.updateFieldVisibility();
  }

  getBlockIndex(): number {
    const pos = this.getPos();
    if (pos === undefined) return -1;
    let offset = 0;
    for (let i = 0; i < this.view.state.doc.childCount; i += 1) {
      if (offset === pos) return i;
      offset += this.view.state.doc.child(i).nodeSize;
    }
    return -1;
  }

  toggleDropdown() {
    this.dropdownOpen = !this.dropdownOpen;
    this.dropdownMenu.style.display = this.dropdownOpen ? 'block' : 'none';

    if (this.dropdownOpen) {
      const index = this.getBlockIndex();
      const count = this.view.state.doc.childCount;
      const disabledClass = 'opacity-40 pointer-events-none';
      this.mergeUpBtn.className = this.mergeUpBtn.className.replace(disabledClass, '').trim();
      this.mergeDownBtn.className = this.mergeDownBtn.className.replace(disabledClass, '').trim();

      const isFirst = index <= 0;
      const isLast = index >= count - 1;
      if (isFirst) this.mergeUpBtn.className += ` ${disabledClass}`;
      if (isLast) this.mergeDownBtn.className += ` ${disabledClass}`;
    }
  }

  closeDropdown() {
    this.dropdownOpen = false;
    this.dropdownMenu.style.display = 'none';
  }

  addBlockBelow() {
    const pos = this.getPos();
    if (pos === undefined) return;

    const blockPos = pos;
    const afterPos = blockPos + this.node.nodeSize;
    const newBlock = this.view.state.schema.nodes.block.create({ type: 'p' });
    const tr = this.view.state.tr.insert(afterPos, newBlock);
    tr.setSelection(Selection.near(tr.doc.resolve(afterPos + 1)));
    this.view.dispatch(tr);
  }

  removeBlock() {
    const pos = this.getPos();
    if (pos === undefined) return;

    // Don't allow deleting if it's the only block
    if (this.view.state.doc.childCount === 1) {
      alert('Cannot remove the last block');
      return;
    }

    if (window.confirm('Are you sure you want to remove this block?')) {
      const tr = this.view.state.tr.delete(pos, pos + this.node.nodeSize);
      this.view.dispatch(tr);
    }
  }

  moveBlockUp() {
    this.editor.moveBlockUp(this.getBlockIndex());
  }

  moveBlockDown() {
    this.editor.moveBlockDown(this.getBlockIndex());
  }

  mergeBlockUp() {
    this.editor.mergeBlockUp(this.getBlockIndex());
  }

  mergeBlockDown() {
    this.editor.mergeBlockDown(this.getBlockIndex());
  }

  applyCheckResult(result: { ok: boolean; error_count: number; checks: Record<string, any> }) {
    this.validationBadge.style.display = '';
    this.validationBadge.classList.remove('pm-check-pass', 'pm-check-fail');
    if (result.ok) {
      this.validationBadge.textContent = '\u2713 pass';
      this.validationBadge.classList.add('pm-check-pass');
      this.validationDetail.innerHTML = '';
      this.validationDetail.style.display = 'none';
    } else {
      const n = result.error_count;
      this.validationBadge.textContent = `\u2717 ${n} error${n !== 1 ? 's' : ''}`;
      this.validationBadge.classList.add('pm-check-fail');
      this.validationDetail.innerHTML = this.renderValidationDetail(result);
      this.validationDetail.style.display = 'none';
    }
  }

  private renderValidationDetail(result: { checks: Record<string, any> }): string {
    const parts: string[] = [];
    const { checks } = result;

    if (checks.well_formed_text) {
      const wft = checks.well_formed_text;
      if (wft.ok) {
        parts.push('<div>\u2713 text well-formed</div>');
      } else {
        const errs = (wft.errors || []).map((e: string) => this.escapeHTML(e)).join(', ');
        parts.push(`<div>\u2717 text: ${errs}</div>`);
      }
    }

    if (checks.meter) {
      const m = checks.meter;
      if (m.ok) {
        parts.push(`<div>\u2713 meter: ${this.escapeHTML(m.meter || '')}</div>`);
      } else {
        parts.push('<div>\u2717 meter unknown</div>');
        parts.push(this.renderScanReport(m.scan || []));
      }
    }

    return parts.join('');
  }

  private scheduleCheck(text: string) {
    if (this._checkDebounceTimer) {
      clearTimeout(this._checkDebounceTimer);
    }
    this._lastCheckText = text;
    this._checkDebounceTimer = setTimeout(() => {
      this.runCheck(text);
    }, 800);
  }

  private async runCheck(text: string) {
    if (!text.trim()) {
      this.validationBadge.style.display = 'none';
      this.validationDetail.style.display = 'none';
      return;
    }

    const blockType = this.node.attrs.type || 'p';
    try {
      const resp = await fetch(routes.proofingBlockCheck(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ blocks: [{ text, type: blockType }] }),
      });
      if (!resp.ok) return;
      const data = await resp.json();
      if (data.results && data.results.length > 0) {
        this.applyCheckResult(data.results[0]);
      }
    } catch (err) {
      console.error('[BlockCheck] Fetch error:', err);
      this.validationBadge.style.display = 'none';
    }
  }

  private escapeHTML(str: string): string {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }

  private renderScanReport(scan: Array<Array<{ text: string; weight: string; odd: boolean }>>): string {
    if (!scan.length) return '<span style="color:#dc2626">No metrical data</span>';
    const maxCols = Math.max(...scan.map((line) => line.length));
    const rows = scan.map((line) => {
      const cells = line.map((s) => {
        const bg = s.odd ? 'background:#fecaca;' : '';
        return `<td style="text-align:center;padding:1px 3px;${bg}"><div>${this.escapeHTML(s.text)}</div><div style="font-size:9px;color:#64748b">${s.weight}</div></td>`;
      }).join('');
      // Pad short rows so columns stay aligned
      const pad = maxCols - line.length;
      const padCells = pad > 0 ? `<td colspan="${pad}"></td>` : '';
      return `<tr>${cells}${padCells}</tr>`;
    }).join('');
    return `<table style="border-collapse:collapse">${rows}</table>`;
  }

  destroy() {
    if (this._checkDebounceTimer) {
      clearTimeout(this._checkDebounceTimer);
    }
    // Unregister this BlockView from the editor
    if (this.editor.blockViews) {
      this.editor.blockViews.delete(this);
    }
  }
}

// Maps each BreakView's DOM element to its BreakView so handleDOMEvents can find it.
const breakViewsByDom = new WeakMap<HTMLElement, BreakView>();

class BreakView {
  dom: HTMLElement;

  node: PMNode;

  view: EditorView;

  getPos: () => number | undefined;

  private menu: HTMLElement | null = null;

  private removeMenu: (() => void) | null = null;

  constructor(node: PMNode, view: EditorView, getPos: () => number | undefined) {
    this.node = node;
    this.view = view;
    this.getPos = getPos;

    this.dom = document.createElement('span');
    this.dom.setAttribute('contenteditable', 'false');
    this.render();

    console.log('[break] BreakView created, dom:', this.dom);
    breakViewsByDom.set(this.dom, this);
  }

  private render() {
    const type = this.node.attrs.type;
    this.dom.className = `pm-break-marker${type ? ' pm-break-marker--typed' : ''}`;
    this.dom.textContent = type ? `¶ ${type}` : '¶';
  }

  openMenu(e: MouseEvent) {
    this.closeMenu();

    const menu = document.createElement('div');
    menu.className = 'pm-break-context-menu';
    menu.style.cssText = 'position:fixed;z-index:9999;background:#fff;border:1px solid #cbd5e1;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,0.15);padding:4px 0;min-width:130px;font-size:13px;';

    const currentType = this.node.attrs.type;

    const makeItem = (label: string, value: string | null) => {
      const item = document.createElement('div');
      item.style.cssText = 'padding:5px 12px;cursor:pointer;display:flex;align-items:center;gap:6px;';
      if (value === currentType) {
        item.style.fontWeight = '600';
        item.style.background = '#f1f5f9';
      }
      const check = document.createElement('span');
      check.style.cssText = 'width:12px;font-size:11px;color:#64748b;';
      check.textContent = value === currentType ? '✓' : '';
      item.appendChild(check);
      const text = document.createElement('span');
      text.textContent = label;
      item.appendChild(text);
      item.addEventListener('mouseenter', () => { item.style.background = '#f8fafc'; });
      item.addEventListener('mouseleave', () => { item.style.background = value === currentType ? '#f1f5f9' : ''; });
      item.addEventListener('mousedown', (ev) => {
        ev.preventDefault();
        this.setType(value);
        this.closeMenu();
      });
      return item;
    };

    // Header
    const header = document.createElement('div');
    header.style.cssText = 'padding:4px 12px 4px;font-size:11px;color:#94a3b8;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;border-bottom:1px solid #e2e8f0;margin-bottom:2px;';
    header.textContent = 'Break type';
    menu.appendChild(header);

    menu.appendChild(makeItem('(none)', null));
    BLOCK_TYPES.forEach((bt) => {
      menu.appendChild(makeItem(bt.label, bt.tag));
    });

    // Position near cursor
    menu.style.left = `${e.clientX}px`;
    menu.style.top = `${e.clientY}px`;
    document.body.appendChild(menu);
    this.menu = menu;

    // Adjust if off-screen
    requestAnimationFrame(() => {
      const rect = menu.getBoundingClientRect();
      if (rect.right > window.innerWidth) {
        menu.style.left = `${e.clientX - rect.width}px`;
      }
      if (rect.bottom > window.innerHeight) {
        menu.style.top = `${e.clientY - rect.height}px`;
      }
    });

    const close = (ev: MouseEvent) => {
      if (!menu.contains(ev.target as Node)) {
        this.closeMenu();
      }
    };
    setTimeout(() => document.addEventListener('mousedown', close), 0);
    this.removeMenu = () => document.removeEventListener('mousedown', close);
  }

  private closeMenu() {
    if (this.menu) {
      this.menu.remove();
      this.menu = null;
    }
    if (this.removeMenu) {
      this.removeMenu();
      this.removeMenu = null;
    }
  }

  private setType(value: string | null) {
    const pos = this.getPos();
    if (pos === undefined) return;
    const { tr } = this.view.state;
    tr.setNodeMarkup(pos, undefined, { type: value });
    this.view.dispatch(tr);
  }

  update(node: PMNode): boolean {
    if (node.type.name !== 'break_separator') return false;
    this.node = node;
    this.render();
    return true;
  }

  destroy() {
    this.closeMenu();
    breakViewsByDom.delete(this.dom);
  }
}

function parseInlineContent(elem: Element, schema: Schema): PMNode[] {
  const result: PMNode[] = [];

  function serializeNode(node: Node): string {
    if (node.nodeType === Node.TEXT_NODE) {
      return node.textContent || '';
    } if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as Element;
      const tagName = el.tagName.toLowerCase();
      const children = Array.from(node.childNodes).map(serializeNode).join('');
      return `<${tagName}>${children}</${tagName}>`;
    }
    return '';
  }

  function traverse(node: Node, activeMarks: readonly Mark[] = []) {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent || '';
      if (text) {
        result.push(schema.text(text, activeMarks));
      }
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as Element;
      const tagName = el.tagName.toLowerCase();

      // <break> is a void inline node, not a mark
      if (tagName === 'break') {
        const breakType = el.getAttribute('type') || null;
        result.push(schema.nodes.break_separator.create({ type: breakType }));
        return;
      }

      // Check if it's a mark we want to render visually
      const validMarkNames = getAllMarkNames();
      if (validMarkNames.includes(tagName)) {
        const mark = schema.mark(tagName);
        const newMarks = mark.addToSet(activeMarks);
        // Traverse children with the mark applied
        for (let i = 0; i < node.childNodes.length; i += 1) {
          traverse(node.childNodes[i], newMarks);
        }
      } else {
        // For other inline elements (like <a>, <b>, etc.), preserve them as text
        const serialized = serializeNode(node);
        if (serialized) {
          result.push(schema.text(serialized, activeMarks));
        }
      }
    }
  }

  for (let i = 0; i < elem.childNodes.length; i += 1) {
    traverse(elem.childNodes[i]);
  }

  return result;
}

// Parse XML content to ProseMirror document
// XML is always rooted in a <page> tag containing block elements
function parseXMLToDoc(xmlString: string, schema: Schema): PMNode {
  // Handle empty content
  if (!xmlString || xmlString.trim() === '') {
    return schema.node('doc', null, [schema.node('block', { type: 'p' })]);
  }

  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(xmlString, 'text/xml');

  // Check for parse errors
  const parseError = xmlDoc.querySelector('parsererror');
  if (parseError) {
    console.error('[parseXMLToDoc] XML parse error:', parseError.textContent);
    throw new Error(`Failed to parse XML: ${parseError.textContent}`);
  }

  const blocks: PMNode[] = [];
  const pageElement = xmlDoc.documentElement;

  // Verify it's a <page> element
  if (pageElement.tagName.toLowerCase() !== 'page') {
    throw new Error(`Expected <page> root element, got <${pageElement.tagName}>`);
  }

  // Parse all child block elements
  for (let i = 0; i < pageElement.children.length; i += 1) {
    const elem = pageElement.children[i];
    const type = elem.tagName.toLowerCase();

    // Extract attributes
    const attrs: any = { type };
    if (elem.hasAttribute('text')) attrs.text = elem.getAttribute('text');
    if (elem.hasAttribute('n')) attrs.n = elem.getAttribute('n');
    if (elem.hasAttribute('mark')) attrs.mark = elem.getAttribute('mark');
    if (elem.hasAttribute('lang')) attrs.lang = elem.getAttribute('lang');
    if (elem.getAttribute('merge-next') === 'true') attrs.merge_next = true;

    // Parse inline content
    const content = parseInlineContent(elem, schema);

    blocks.push(schema.node('block', attrs, content));
  }

  if (blocks.length === 0) {
    blocks.push(schema.node('block', { type: 'p' }));
  }

  return schema.node('doc', null, blocks);
}

// Escape characters that would break XML *text content*. Quotes are only
// special inside attribute values (escapeXMLAttr below); escaping them in
// text content produces noise like &apos; / &quot; that survives round-trips
// through diffs and confuses reviewers.
function escapeXMLText(str: string): string {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Escape for use inside double-quoted attribute values.
function escapeXMLAttr(str: string): string {
  return escapeXMLText(str).replace(/"/g, '&quot;');
}

function serializeInlineContent(node: PMNode): string {
  let result = '';

  node.forEach((child) => {
    if (child.type.name === 'break_separator') {
      const breakType = child.attrs.type;
      result += breakType ? `<break type="${breakType}"/>` : '<break/>';
    } else if (child.isText) {
      let text = escapeXMLText(child.text || '');
      child.marks.forEach((mark) => {
        text = `<${mark.type.name}>${text}</${mark.type.name}>`;
      });

      result += text;
    }
  });

  return result;
}

function serializeDocToXML(doc: PMNode): string {
  const parts: string[] = [];

  doc.forEach((block) => {
    const type = block.attrs.type || 'p';
    const attrs: string[] = [];

    if (block.attrs.text) attrs.push(`text="${escapeXMLAttr(block.attrs.text)}"`);
    if (block.attrs.n) attrs.push(`n="${escapeXMLAttr(block.attrs.n)}"`);
    if (block.attrs.mark) attrs.push(`mark="${escapeXMLAttr(block.attrs.mark)}"`);
    if (block.attrs.lang) attrs.push(`lang="${escapeXMLAttr(block.attrs.lang)}"`);
    if (block.attrs.merge_next) attrs.push('merge-next="true"');

    const attrsStr = attrs.length > 0 ? ` ${attrs.join(' ')}` : '';
    const content = serializeInlineContent(block);

    parts.push(`<${type}${attrsStr}>${content}</${type}>`);
  });

  return `<page>\n${parts.join('\n')}\n</page>`;
}

// Schema for XML editing mode - a simple code editor
const xmlSchema = new Schema({
  nodes: {
    doc: {
      content: 'codeblock',
    },
    codeblock: {
      content: 'text*',
      group: 'block',
      code: true,
      preserveWhitespace: 'full',
      parseDOM: [{ tag: 'pre' }],
      toDOM() {
        return ['pre', { class: 'xml-code' }, 0];
      },
    },
    text: {
      group: 'inline',
    },
  },
  marks: {},
});

function createXMLDecorations(state: EditorState): DecorationSet {
  const decorations: Decoration[] = [];
  const text = state.doc.textContent;

  const tagRegex = /<\/?([a-zA-Z][\w-]*)((?:\s+[\w-]+(?:="[^"]*")?)*)\s*\/?>/g;
  let match = tagRegex.exec(text);

  while (match !== null) {
    // Positions need to account for document structure:
    // doc (pos 0) -> codeblock (pos 1) -> text content starts at pos 1
    // So we add 1 to convert text offsets to document positions
    const from = match.index + 1;
    const to = match.index + match[0].length + 1;

    decorations.push(
      Decoration.inline(from, to, {
        style: 'color: #60a5fa;', // Blue color for tags
      }),
    );
    match = tagRegex.exec(text);
  }

  return DecorationSet.create(state.doc, decorations);
}

// Plugin to add XML syntax highlighting decorations
function xmlHighlightPlugin() {
  return new Plugin({
    state: {
      init(_, state) {
        return createXMLDecorations(state);
      },
      apply(tr, set, oldState, newState) {
        if (!tr.docChanged) return set;
        return createXMLDecorations(newState);
      },
    },
    props: {
      decorations(state) {
        return this.getState(state);
      },
    },
  });
}

export class XMLView {
  view: EditorView;

  schema: Schema;

  onChange?: () => void;

  textZoom: number;

  // eslint-disable-next-line default-param-last
  constructor(element: HTMLElement, initialContent: string = '', onChange?: () => void, textZoom: number = 1) {
    this.schema = xmlSchema;
    this.onChange = onChange;
    this.textZoom = textZoom;

    const textNode = initialContent ? this.schema.text(initialContent) : undefined;
    const codeblock = this.schema.node('codeblock', null, textNode ? [textNode] : []);

    const state = EditorState.create({
      doc: this.schema.node('doc', null, [codeblock]),
      plugins: [
        history(),
        xmlHighlightPlugin(),
        keymap({ 'Mod-z': pmUndo, 'Mod-y': pmRedo }),
        keymap(baseKeymap),
      ],
    });

    // Create wrapper for styling
    const wrapper = document.createElement('div');
    wrapper.className = 'w-full h-full bg-gray-800 text-gray-300';
    element.appendChild(wrapper);

    this.view = new EditorView(wrapper, {
      state,
      dispatchTransaction: (transaction) => {
        const newState = this.view.state.apply(transaction);
        this.view.updateState(newState);

        if (transaction.docChanged && this.onChange) {
          this.onChange();
        }
      },
      attributes: {
        class: 'w-full h-full font-mono text-sm focus:outline-none',
        spellcheck: 'false',
        style: `font-size: ${textZoom}rem; line-height: ${1.2 + (textZoom - 1) * 0.6}`,
      },
    });
  }

  setTextZoom(zoom: number) {
    this.textZoom = zoom;
    this.view.setProps({
      attributes: {
        class: 'w-full h-full font-mono text-sm focus:outline-none',
        spellcheck: 'false',
        style: `font-size: ${zoom}rem; line-height: ${1.2 + (zoom - 1) * 0.6}`,
      },
    });
  }

  getText(): string {
    return this.view.state.doc.textContent;
  }

  setText(text: string) {
    const textNode = text ? this.schema.text(text) : undefined;
    const codeblock = this.schema.node('codeblock', null, textNode ? [textNode] : []);
    const newState = EditorState.create({
      doc: this.schema.node('doc', null, [codeblock]),
      plugins: this.view.state.plugins,
    });
    this.view.updateState(newState);
  }

  focus() {
    this.view.focus();
  }

  getSelection(): { from: number; to: number; text: string } {
    const { from, to } = this.view.state.selection;
    const text = this.view.state.doc.textBetween(from, to, '\n');
    return { from, to, text };
  }

  replaceSelection(text: string) {
    const { state } = this.view;
    const { from, to } = state.selection;

    const tr = state.tr.insertText(text, from, to);
    const newState = state.apply(tr);
    this.view.updateState(newState);
    this.view.focus();

    if (this.onChange) {
      this.onChange();
    }
  }

  undo() {
    pmUndo(this.view.state, this.view.dispatch);
  }

  redo() {
    pmRedo(this.view.state, this.view.dispatch);
  }

  destroy() {
    this.view.destroy();
  }
}

export default class {
  view: EditorView;

  schema: Schema;

  onChange?: () => void;

  onActiveWordChange?: (
    context: { word: string; lineText: string; wordIndex: number } | null,
  ) => void;

  showAdvancedOptions: boolean;

  blockViews: Set<BlockView>;

  textZoom: number;

  constructor(
    element: HTMLElement,
    // eslint-disable-next-line default-param-last
    initialContent: string = '',
    onChange?: () => void,
    // eslint-disable-next-line default-param-last
    showAdvancedOptions: boolean = false,
    // eslint-disable-next-line default-param-last
    textZoom: number = 1.0,
    onActiveWordChange?: (
      context: { word: string; lineText: string; wordIndex: number } | null,
    ) => void,
    imeGetConfig?: () => IMEConfig,
  ) {
    this.schema = customSchema;
    this.onChange = onChange;
    this.onActiveWordChange = onActiveWordChange;
    this.showAdvancedOptions = showAdvancedOptions;
    this.blockViews = new Set();
    this.textZoom = textZoom;

    let doc;
    try {
      doc = parseXMLToDoc(initialContent, this.schema);
    } catch (error) {
      doc = this.schema.node('doc', null, [this.schema.node('block', { type: 'p' })]);
    }

    const plugins = [
      history(),
      keymap({
        'Mod-z': pmUndo,
        'Mod-y': pmRedo,
        'Shift-Enter': createBlockBelow,
        'Mod-b': (state, dispatch) => { this.toggleMark('bold'); return true; },
        'Mod-i': (state, dispatch) => { this.toggleMark('italic'); return true; },
      }),
      keymap(baseKeymap),
      activeWordPlugin(this.onActiveWordChange),
    ];
    if (imeGetConfig) {
      plugins.unshift(imePlugin(imeGetConfig));
    }

    const state = EditorState.create({
      doc,
      plugins,
    });

    this.view = new EditorView(element, {
      state,
      nodeViews: {
        block: (node, view, getPos) => new BlockView(node, view, getPos as () => number, this),
        break_separator: (node, view, getPos) => new BreakView(node, view, getPos as () => number),
      },
      dispatchTransaction: (transaction) => {
        const newState = this.view.state.apply(transaction);
        this.view.updateState(newState);

        if (transaction.docChanged && this.onChange) {
          this.onChange();
        }
      },
    });

    this.view.dom.addEventListener('click', (event) => {
      const target = event.target as HTMLElement;
      console.log('[break] click target:', target, target.className);
      const breakEl = target.closest('.pm-break-marker') as HTMLElement | null;
      console.log('[break] breakEl:', breakEl);
      if (!breakEl) return;
      event.preventDefault();
      const bv = breakViewsByDom.get(breakEl);
      console.log('[break] breakView:', bv);
      if (bv) bv.openMenu(event as MouseEvent);
    });

    // Batch block check for all non-empty, non-ignore/metadata blocks on initial load
    this.runBatchBlockCheck();
  }

  private async runBatchBlockCheck() {
    const checkViews: BlockView[] = [];
    const blocks: Array<{ text: string; type: string }> = [];
    this.blockViews.forEach((bv) => {
      const blockType = bv.node.attrs.type || 'p';
      if (blockType !== 'ignore' && blockType !== 'metadata' && bv.node.textContent.trim()) {
        checkViews.push(bv);
        blocks.push({ text: bv.node.textContent, type: blockType });
      }
    });
    if (!blocks.length) return;

    try {
      const resp = await fetch(routes.proofingBlockCheck(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ blocks }),
      });
      if (!resp.ok) return;
      const data = await resp.json();
      const results = data.results || [];
      for (let i = 0; i < checkViews.length && i < results.length; i += 1) {
        checkViews[i].applyCheckResult(results[i]);
      }
    } catch (err) {
      console.error('[BlockCheck] Batch fetch error:', err);
    }
  }

  getText(): string {
    return serializeDocToXML(this.view.state.doc);
  }

  setText(text: string) {
    const newDoc = parseXMLToDoc(text, this.schema);
    const newState = EditorState.create({
      doc: newDoc,
      plugins: this.view.state.plugins,
    });
    this.view.updateState(newState);
  }

  focus() {
    this.view.focus();
  }

  getSelection(): { from: number; to: number; text: string } {
    const { from, to } = this.view.state.selection;
    const text = this.view.state.doc.textBetween(from, to, '\n');
    return { from, to, text };
  }

  replaceSelection(text: string) {
    const { state } = this.view;
    const { from, to } = state.selection;

    const tr = state.tr.insertText(text, from, to);
    const newState = state.apply(tr);
    this.view.updateState(newState);
    this.view.focus();

    if (this.onChange) {
      this.onChange();
    }
  }

  toggleMark(markType: MarkName) {
    const { state, dispatch } = this.view;
    const { from, to } = state.selection;

    const mark = this.schema.marks[markType];
    if (!mark) return;

    const hasMark = state.doc.rangeHasMark(from, to, mark);
    if (hasMark) {
      const tr = state.tr.removeMark(from, to, mark);
      dispatch(tr);
    } else {
      const tr = state.tr.addMark(from, to, mark.create());
      dispatch(tr);
    }
  }

  getBlockIndexFromSelection(): number {
    const { state } = this.view;
    const { $from } = state.selection;

    let blockDepth = $from.depth;
    while (blockDepth > 0 && state.doc.resolve($from.pos).node(blockDepth).type.name !== 'block') {
      blockDepth -= 1;
    }
    if (blockDepth === 0) return -1;

    const currentBlock = $from.node(blockDepth);
    for (let i = 0; i < state.doc.childCount; i += 1) {
      if (state.doc.child(i) === currentBlock) return i;
    }
    return -1;
  }

  getBlockStartPos(index: number): number {
    const { state } = this.view;
    let pos = 0;
    for (let i = 0; i < index; i += 1) {
      pos += state.doc.child(i).nodeSize;
    }
    return pos;
  }

  insertBlock(blockIndex?: number) {
    const { state, dispatch } = this.view;
    if (blockIndex === undefined) blockIndex = this.getBlockIndexFromSelection();
    if (blockIndex < 0) return;

    const afterPos = this.getBlockStartPos(blockIndex) + state.doc.child(blockIndex).nodeSize;
    const newBlock = this.schema.nodes.block.create({ type: 'p' });
    const tr = state.tr.insert(afterPos, newBlock);
    tr.setSelection(Selection.near(tr.doc.resolve(afterPos + 1)));
    dispatch(tr);

    if (this.onChange) {
      this.onChange();
    }
  }

  deleteActiveBlock(blockIndex?: number) {
    const { state, dispatch } = this.view;
    if (blockIndex === undefined) blockIndex = this.getBlockIndexFromSelection();
    if (blockIndex < 0) return;

    if (state.doc.childCount === 1) return;

    const blockPos = this.getBlockStartPos(blockIndex);
    const tr = state.tr.delete(blockPos, blockPos + state.doc.child(blockIndex).nodeSize);
    dispatch(tr);

    if (this.onChange) {
      this.onChange();
    }
  }

  moveBlockUp(blockIndex?: number) {
    if (blockIndex === undefined) blockIndex = this.getBlockIndexFromSelection();
    if (blockIndex <= 0) return;
    this.swapBlocks(blockIndex - 1, blockIndex);
  }

  moveBlockDown(blockIndex?: number) {
    if (blockIndex === undefined) blockIndex = this.getBlockIndexFromSelection();
    if (blockIndex < 0 || blockIndex >= this.view.state.doc.childCount - 1) return;
    this.swapBlocks(blockIndex, blockIndex + 1);
  }

  private swapBlocks(indexA: number, indexB: number) {
    const { state, dispatch } = this.view;
    const blockA = state.doc.child(indexA);
    const blockB = state.doc.child(indexB);

    const newChildren: PMNode[] = [];
    for (let i = 0; i < state.doc.childCount; i += 1) {
      if (i === indexA) newChildren.push(blockB);
      else if (i === indexB) newChildren.push(blockA);
      else newChildren.push(state.doc.child(i));
    }

    const newDoc = state.schema.node('doc', null, newChildren);
    let tr = state.tr.replaceWith(0, state.doc.content.size, newDoc);
    // Place cursor in whichever block ended up at indexA (the earlier position)
    tr = tr.setSelection(Selection.near(tr.doc.resolve(this.getBlockStartPos(indexA) + 1)));
    dispatch(tr);

    if (this.onChange) {
      this.onChange();
    }
  }

  mergeBlockUp(blockIndex?: number) {
    this.mergeBlocks('up', blockIndex);
  }

  mergeBlockDown(blockIndex?: number) {
    this.mergeBlocks('down', blockIndex);
  }

  mergeBlocks(direction: 'up' | 'down', blockIndex?: number) {
    const { state, dispatch } = this.view;
    if (blockIndex === undefined) blockIndex = this.getBlockIndexFromSelection();

    if (direction === 'up' && blockIndex <= 0) return;
    if (direction === 'down' && (blockIndex < 0 || blockIndex >= state.doc.childCount - 1)) return;

    const keepIndex = direction === 'up' ? blockIndex - 1 : blockIndex;
    const removeIndex = direction === 'up' ? blockIndex : blockIndex + 1;
    const keepBlock = state.doc.child(keepIndex);
    const removeBlock = state.doc.child(removeIndex);

    const separator = state.schema.text('\n');
    const mergedContent = Fragment.from([
      ...keepBlock.content.content,
      separator,
      ...removeBlock.content.content,
    ]);
    const mergedBlock = keepBlock.copy(mergedContent);

    const newChildren: PMNode[] = [];
    for (let i = 0; i < state.doc.childCount; i += 1) {
      if (i === keepIndex) {
        newChildren.push(mergedBlock);
      } else if (i !== removeIndex) {
        newChildren.push(state.doc.child(i));
      }
    }

    const newDoc = state.schema.node('doc', null, newChildren);
    let tr = state.tr.replaceWith(0, state.doc.content.size, newDoc);

    let targetPos = 0;
    for (let i = 0; i < keepIndex; i += 1) {
      targetPos += newChildren[i].nodeSize;
    }
    tr = tr.setSelection(Selection.near(tr.doc.resolve(targetPos + 1)));

    dispatch(tr);

    if (this.onChange) {
      this.onChange();
    }
  }

  setActiveBlockType(typeName: string) {
    const { state, dispatch } = this.view;
    const blockIndex = this.getBlockIndexFromSelection();
    if (blockIndex < 0) return;

    const blockPos = this.getBlockStartPos(blockIndex);
    const block = state.doc.child(blockIndex);
    const tr = state.tr.setNodeMarkup(blockPos, undefined, {
      ...block.attrs,
      type: typeName,
    });
    dispatch(tr);

    if (this.onChange) {
      this.onChange();
    }
  }

  undo() {
    pmUndo(this.view.state, this.view.dispatch);
  }

  redo() {
    pmRedo(this.view.state, this.view.dispatch);
  }

  setShowAdvancedOptions(show: boolean) {
    this.showAdvancedOptions = show;

    this.blockViews.forEach((blockView) => {
      blockView.updateAdvancedOptionsVisibility();
    });
  }

  setTextZoom(zoom: number) {
    this.textZoom = zoom;

    this.blockViews.forEach((blockView) => {
      blockView.contentDOM.style.fontSize = `${zoom}rem`;
    });
  }

  destroy() {
    this.view.destroy();
  }
}
