import ProseMirrorEditor, { XMLView } from '@/prosemirror-editor.ts';

describe('ProseMirrorEditor', () => {
  let container;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  afterEach(() => {
    document.body.removeChild(container);
  });

  test('initializes with simple XML content', () => {
    const xml = '<page><p>Hello world</p></page>';
    const editor = new ProseMirrorEditor(container, xml);

    expect(editor.view).toBeDefined();
    expect(editor.view.state.doc.childCount).toBe(1);

    const firstBlock = editor.view.state.doc.child(0);
    expect(firstBlock.attrs.type).toBe('p');
    expect(firstBlock.textContent).toBe('Hello world');

    editor.destroy();
  });

  test('getText returns XML content', () => {
    const xml = '<page><p>Test content</p></page>';
    const editor = new ProseMirrorEditor(container, xml);

    const output = editor.getText();
    expect(output).toContain('<page>');
    expect(output).toContain('<p>Test content</p>');

    editor.destroy();
  });

  // Regression tests for the escapeXMLText / escapeXMLAttr split.
  // Apostrophes and double quotes are valid as literal characters inside
  // element text and only need escaping inside attribute values. Previously
  // both were escaped everywhere, causing &apos; / &quot; to leak into stored
  // revisions and show up as literal text in diffs.
  describe('XML escaping in serialization', () => {
    test('apostrophes in element text are NOT escaped to &apos;', () => {
      const xml = "<page><p>foo'bar</p></page>";
      const editor = new ProseMirrorEditor(container, xml);

      const output = editor.getText();
      expect(output).toContain("foo'bar");
      expect(output).not.toContain('&apos;');

      editor.destroy();
    });

    test('double quotes in element text are NOT escaped to &quot;', () => {
      const xml = '<page><p>she said "hi"</p></page>';
      const editor = new ProseMirrorEditor(container, xml);

      const output = editor.getText();
      expect(output).toContain('she said "hi"');
      expect(output).not.toContain('&quot;');

      editor.destroy();
    });

    test('& < > in element text ARE escaped (required for valid XML)', () => {
      const xml = '<page><p>a &amp; b &lt; c &gt; d</p></page>';
      const editor = new ProseMirrorEditor(container, xml);

      const output = editor.getText();
      expect(output).toContain('&amp;');
      expect(output).toContain('&lt;');
      expect(output).toContain('&gt;');

      editor.destroy();
    });

    test('double quotes in attribute values ARE escaped (would break the attribute)', () => {
      // Use an attribute the editor recognizes (text="...") with a quote inside.
      // Input must escape the quote so the input itself parses; the assertion
      // confirms the editor preserves that escaping on output.
      const xml = '<page><p text="quoted &quot;value&quot;">body</p></page>';
      const editor = new ProseMirrorEditor(container, xml);

      const output = editor.getText();
      expect(output).toContain('text="quoted &quot;value&quot;"');

      editor.destroy();
    });

    test('round-trip preserves apostrophes through parse + serialize', () => {
      // The actual bug: editor parsed clean ' from input but emitted &apos;
      // on save, so the next round-trip showed up as literal entity in diffs.
      const xml = "<page><p>round'trip</p></page>";
      const editor1 = new ProseMirrorEditor(container, xml);
      const intermediate = editor1.getText();
      editor1.destroy();

      const editor2 = new ProseMirrorEditor(container, intermediate);
      const final = editor2.getText();
      editor2.destroy();

      expect(final).toContain("round'trip");
      expect(final).not.toContain('&apos;');
    });
  });

  test('toggleMark adds error mark to selection', () => {
    const xml = '<page><p>Hello world</p></page>';
    const editor = new ProseMirrorEditor(container, xml);

    // Select "world" - positions are: 'w' at 7, end of "world" at 12
    const { TextSelection } = require('prosemirror-state');
    const tr = editor.view.state.tr.setSelection(
      TextSelection.create(editor.view.state.doc, 7, 12)
    );
    editor.view.updateState(editor.view.state.apply(tr));

    editor.toggleMark('error');
    const output = editor.getText();
    expect(output).toContain('<error>world</error>');

    editor.destroy();
  });

  test('setText updates editor content', () => {
    const editor = new ProseMirrorEditor(container, '<page><p>Initial</p></page>');

    editor.setText('<page><p>Updated</p></page>');

    expect(editor.view.state.doc.child(0).textContent).toBe('Updated');

    editor.destroy();
  });

  test('Shift-Enter creates a new block below', () => {
    const xml = '<page><p>First block</p></page>';
    const editor = new ProseMirrorEditor(container, xml);

    const { from, to } = editor.view.state.selection;
    const shiftEnterEvent = new KeyboardEvent('keydown', {
      key: 'Enter',
      shiftKey: true,
      bubbles: true,
    });

    editor.view.dom.dispatchEvent(shiftEnterEvent);

    const output = editor.getText();
    expect(output).toContain('<p>First block</p>');
    expect(output).toContain('<p></p>');
    expect(editor.view.state.doc.childCount).toBe(2);

    editor.destroy();
  });

  test('Shift-Enter preserves content in current block', () => {
    const xml = '<page><p>Content here</p></page>';
    const editor = new ProseMirrorEditor(container, xml);

    const { TextSelection } = require('prosemirror-state');
    const tr = editor.view.state.tr.setSelection(
      TextSelection.create(editor.view.state.doc, 8, 8)
    );
    editor.view.updateState(editor.view.state.apply(tr));

    const shiftEnterEvent = new KeyboardEvent('keydown', {
      key: 'Enter',
      shiftKey: true,
      bubbles: true,
    });

    editor.view.dom.dispatchEvent(shiftEnterEvent);

    const output = editor.getText();
    expect(output).toBe('<page>\n<p>Content</p>\n<p> here</p>\n</page>');
    expect(editor.view.state.doc.childCount).toBe(2);

    editor.destroy();
  });
});

describe('XMLView', () => {
  let container;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  afterEach(() => {
    document.body.removeChild(container);
  });

  test('initializes with XML content', () => {
    const xml = '<page><p>Hello world</p></page>';
    const xmlView = new XMLView(container, xml);

    expect(xmlView.view).toBeDefined();
    expect(xmlView.view.state.doc).toBeDefined();
    expect(xmlView.getText()).toBe(xml);

    xmlView.destroy();
  });

  test('document has codeblock structure', () => {
    const xml = '<page><p>Test</p></page>';
    const xmlView = new XMLView(container, xml);

    const doc = xmlView.view.state.doc;
    expect(doc.childCount).toBe(1);
    expect(doc.child(0).type.name).toBe('codeblock');
    expect(doc.child(0).textContent).toBe(xml);

    xmlView.destroy();
  });

  test('getText returns XML content', () => {
    const xml = '<page><p>Hello world</p></page>';
    const xmlView = new XMLView(container, xml);

    expect(xmlView.getText()).toBe(xml);

    xmlView.destroy();
  });

  test('setText updates content', () => {
    const xml1 = '<page><p>First</p></page>';
    const xml2 = '<page><p>Second</p></page>';
    const xmlView = new XMLView(container, xml1);

    xmlView.setText(xml2);

    expect(xmlView.getText()).toBe(xml2);
    expect(xmlView.view.state.doc.textContent).toBe(xml2);

    xmlView.destroy();
  });

  test('decorations are created for XML tags', () => {
    const xml = '<page><p>Hello</p></page>';
    const xmlView = new XMLView(container, xml);

    const decorationPlugin = xmlView.view.state.plugins.find(
      p => p.spec && p.spec.props && p.spec.props.decorations
    );
    expect(decorationPlugin).toBeDefined();

    const decorations = decorationPlugin.getState(xmlView.view.state);
    expect(decorations).toBeDefined();

    const allDecorations = decorations.find();
    expect(allDecorations.length).toBe(4);

    xmlView.destroy();
  });

  test('decorations cover all XML tags', () => {
    const xml = '<page><p>Test</p></page>';
    const xmlView = new XMLView(container, xml);

    const decorationPlugin = xmlView.view.state.plugins.find(
      p => p.spec && p.spec.props && p.spec.props.decorations
    );

    const decorations = decorationPlugin.getState(xmlView.view.state);
    const allDecorations = decorations.find();

    // Should have decorations for: <page>, <p>, </p>, </page> = 4 tags
    expect(allDecorations.length).toBe(4);

    xmlView.destroy();
  });

  test('decorations have color style', () => {
    const xml = '<page><p>Test</p></page>';
    const xmlView = new XMLView(container, xml);

    const decorationPlugin = xmlView.view.state.plugins.find(
      p => p.spec && p.spec.props && p.spec.props.decorations
    );

    const decorations = decorationPlugin.getState(xmlView.view.state);
    const allDecorations = decorations.find();

    const hasColorStyle = allDecorations.some(deco =>
      deco.type.attrs && deco.type.attrs.style && deco.type.attrs.style.includes('color')
    );
    expect(hasColorStyle).toBe(true);

    xmlView.destroy();
  });

  test('decorations update when text changes', () => {
    const xml1 = '<page></page>';
    const xml2 = '<page><p>New</p><verse>Content</verse></page>';
    const xmlView = new XMLView(container, xml1);

    const decorationPlugin = xmlView.view.state.plugins.find(
      p => p.spec && p.spec.props && p.spec.props.decorations
    );

    let decorations = decorationPlugin.getState(xmlView.view.state);
    let allDecorations = decorations.find();
    const initialCount = allDecorations.length;

    xmlView.setText(xml2);

    decorations = decorationPlugin.getState(xmlView.view.state);
    allDecorations = decorations.find();

    // More tags in xml2, so should have more decorations
    expect(allDecorations.length).toBeGreaterThan(initialCount);

    xmlView.destroy();
  });

  test('focus sets focus on the editor', () => {
    const xml = '<page><p>Test</p></page>';
    const xmlView = new XMLView(container, xml);

    xmlView.focus();

    expect(xmlView.view.hasFocus()).toBe(true);

    xmlView.destroy();
  });

  test('handles empty content', () => {
    const xmlView = new XMLView(container, '');

    expect(xmlView.getText()).toBe('');
    expect(xmlView.view.state.doc.textContent).toBe('');

    xmlView.destroy();
  });


  test('preserves whitespace and newlines', () => {
    const xml = `<page>
<p>Line 1
Line 2</p>
</page>`;
    const xmlView = new XMLView(container, xml);

    expect(xmlView.getText()).toBe(xml);
    expect(xmlView.getText()).toContain('\n');

    xmlView.destroy();
  });
});

describe('IME Plugin', () => {
  let container;
  let imeConfig;

  // Mock Sanscript: prefix output with "T:" to distinguish transliterated text
  beforeAll(() => {
    window.Sanscript = {
      t: jest.fn((s, from, to) => `[${s}]`),
    };
  });

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    imeConfig = { enabled: true, fromScript: 'hk', toScript: 'devanagari' };
    jest.clearAllMocks();
  });

  afterEach(() => {
    document.body.removeChild(container);
    // Clean up any IME popups left on document.body
    document.querySelectorAll('.ime-popup').forEach(el => el.remove());
  });

  function createEditorWithIME(xml = '<page><p></p></page>') {
    return new ProseMirrorEditor(
      container, xml, undefined, false, 1.0, undefined,
      () => imeConfig,
    );
  }

  function sendKey(editor, key, opts = {}) {
    const event = new KeyboardEvent('keydown', {
      key,
      bubbles: true,
      cancelable: true,
      ...opts,
    });
    editor.view.dom.dispatchEvent(event);
  }

  function getBlockText(editor, blockIndex = 0) {
    return editor.view.state.doc.child(blockIndex).textContent;
  }

  function getPopup() {
    return document.querySelector('.ime-popup');
  }

  function setCursor(editor, pos) {
    const { TextSelection } = require('prosemirror-state');
    const tr = editor.view.state.tr.setSelection(
      TextSelection.create(editor.view.state.doc, pos, pos)
    );
    editor.view.updateState(editor.view.state.apply(tr));
  }

  // -- Basic typing --

  test('typing characters inserts raw text into editor', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'h');
    sendKey(editor, 'a');
    sendKey(editor, 'm');

    expect(getBlockText(editor)).toBe('aham');
    editor.destroy();
  });

  test('typing characters shows popup with transliterated text', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');

    const popup = getPopup();
    expect(popup).not.toBeNull();
    expect(popup.style.display).not.toBe('none');
    expect(window.Sanscript.t).toHaveBeenCalledWith('a', 'hk', 'devanagari');

    sendKey(editor, 'h');
    expect(window.Sanscript.t).toHaveBeenCalledWith('ah', 'hk', 'devanagari');

    editor.destroy();
  });

  // -- Commit via Enter --

  test('Enter commits: replaces raw text with transliterated output', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'b');
    sendKey(editor, 'c');
    expect(getBlockText(editor)).toBe('abc');

    sendKey(editor, 'Enter');

    // Sanscript.t('abc', ...) returns '[abc]'
    expect(getBlockText(editor)).toBe('[abc]');
    editor.destroy();
  });

  test('Enter hides popup after commit', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'x');
    sendKey(editor, 'Enter');

    const popup = getPopup();
    expect(popup.style.display).toBe('none');
    editor.destroy();
  });

  test('Enter with empty buffer passes through (does not intercept)', () => {
    const editor = createEditorWithIME();
    // No typing, just press Enter — should not be intercepted by IME
    // (ProseMirror default behavior for Enter in a block)
    const before = editor.view.state.doc.childCount;
    sendKey(editor, 'Enter');
    // We just verify no crash; behavior depends on ProseMirror base keymap
    editor.destroy();
  });

  // -- Commit via Space --

  test('Space commits with trailing space', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'h');
    sendKey(editor, 'i');
    sendKey(editor, ' ');

    expect(getBlockText(editor)).toBe('[hi] ');
    editor.destroy();
  });

  // -- Escape discards --

  test('Escape discards buffer and deletes raw text from editor', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 't');
    sendKey(editor, 'e');
    sendKey(editor, 's');
    sendKey(editor, 't');
    expect(getBlockText(editor)).toBe('test');

    sendKey(editor, 'Escape');
    expect(getBlockText(editor)).toBe('');
    editor.destroy();
  });

  test('Escape hides popup', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'x');
    sendKey(editor, 'Escape');

    const popup = getPopup();
    expect(popup.style.display).toBe('none');
    editor.destroy();
  });

  test('Escape with empty buffer passes through', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'Escape');
    // No crash, no popup created
    editor.destroy();
  });

  // -- Backspace --

  test('Backspace removes last character from buffer and editor', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'b');
    sendKey(editor, 'c');
    expect(getBlockText(editor)).toBe('abc');

    sendKey(editor, 'Backspace');
    expect(getBlockText(editor)).toBe('ab');

    sendKey(editor, 'Backspace');
    expect(getBlockText(editor)).toBe('a');

    editor.destroy();
  });

  test('Backspace hides popup when buffer becomes empty', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'x');
    sendKey(editor, 'Backspace');

    expect(getBlockText(editor)).toBe('');
    const popup = getPopup();
    expect(popup.style.display).toBe('none');
    editor.destroy();
  });

  test('Backspace with empty buffer passes through (not intercepted by IME)', () => {
    const editor = createEditorWithIME('<page><p>AB</p></page>');
    // With no active buffer, Backspace should not be intercepted by IME
    // (actual deletion depends on ProseMirror's keymap handling via dispatchEvent)
    sendKey(editor, 'Backspace');
    // Content unchanged proves IME didn't intercept it
    expect(getBlockText(editor)).toBe('AB');
    editor.destroy();
  });

  // -- Shift key --

  test('Shift key alone does not affect buffer or commit', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'Shift', { shiftKey: true });
    // Buffer should still be 'a', not committed
    expect(getBlockText(editor)).toBe('a');

    // Can continue typing after Shift
    sendKey(editor, 'B', { shiftKey: true });
    expect(getBlockText(editor)).toBe('aB');

    sendKey(editor, 'Enter');
    expect(getBlockText(editor)).toBe('[aB]');
    editor.destroy();
  });

  // -- Other modifier keys --

  test('Ctrl/Meta modifier keys pass through without affecting buffer', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'Control');
    sendKey(editor, 'Alt');
    sendKey(editor, 'Meta');
    // Buffer still intact
    expect(getBlockText(editor)).toBe('a');
    editor.destroy();
  });

  // -- Arrow keys within buffer --

  test('ArrowLeft within buffer moves cursor without committing', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'b');
    sendKey(editor, 'c');
    // Cursor is at end of 'abc' (bufferStart + 3)
    // ArrowLeft should move within buffer, not commit
    sendKey(editor, 'ArrowLeft');
    // Buffer text should still be in editor, not committed
    expect(getBlockText(editor)).toBe('abc');

    // Can still commit with Enter after moving
    sendKey(editor, 'Enter');
    expect(getBlockText(editor)).toBe('[abc]');
    editor.destroy();
  });

  test('ArrowLeft at start of buffer commits', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'b');
    // bufferStart=1, buffer='ab', cursor at 3
    // Manually place cursor at bufferStart (pos 1)
    setCursor(editor, 1);
    // ArrowLeft at bufferStart should commit
    sendKey(editor, 'ArrowLeft');
    expect(getBlockText(editor)).toBe('[ab]');
    editor.destroy();
  });

  test('ArrowRight at end of buffer commits', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'x');
    sendKey(editor, 'y');
    // Cursor is already at end of buffer (bufferStart + 2), ArrowRight should commit
    sendKey(editor, 'ArrowRight');
    expect(getBlockText(editor)).toBe('[xy]');
    editor.destroy();
  });

  test('ArrowRight within buffer moves cursor without committing', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'b');
    sendKey(editor, 'c');
    // bufferStart=1, buffer='abc', cursor at 4
    // Place cursor in middle of buffer (pos 2)
    setCursor(editor, 2);
    // ArrowRight within buffer should not commit
    sendKey(editor, 'ArrowRight');
    expect(getBlockText(editor)).toBe('abc');

    sendKey(editor, 'Enter');
    expect(getBlockText(editor)).toBe('[abc]');
    editor.destroy();
  });

  // -- Mid-buffer editing --

  test('typing in middle of buffer inserts at cursor position', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'c');
    // bufferStart=1, buffer='ac', cursor at 3
    // Place cursor between 'a' and 'c' (pos 2)
    setCursor(editor, 2);
    sendKey(editor, 'b');
    expect(getBlockText(editor)).toBe('abc');

    sendKey(editor, 'Enter');
    expect(getBlockText(editor)).toBe('[abc]');
    editor.destroy();
  });

  test('backspace in middle of buffer deletes correct character', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'x');
    sendKey(editor, 'b');
    // bufferStart=1, buffer='axb', cursor at 4
    // Place cursor after 'x' (pos 3), so backspace deletes 'x'
    setCursor(editor, 3);
    sendKey(editor, 'Backspace');
    expect(getBlockText(editor)).toBe('ab');

    sendKey(editor, 'Enter');
    expect(getBlockText(editor)).toBe('[ab]');
    editor.destroy();
  });

  test('backspace at start of buffer commits then passes through', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'b');
    // bufferStart=1, buffer='ab'
    // Place cursor at bufferStart (pos 1)
    setCursor(editor, 1);
    // Backspace at start should commit
    sendKey(editor, 'Backspace');
    expect(getBlockText(editor)).toBe('[ab]');
    editor.destroy();
  });

  // -- Click outside buffer commits --

  test('clicking outside buffer commits it', () => {
    const editor = createEditorWithIME('<page><p>Hello</p></page>');
    // Place cursor at end of "Hello" (pos 6)
    setCursor(editor, 6);
    sendKey(editor, 'x');
    sendKey(editor, 'y');
    // bufferStart=6, buffer='xy', editor text = 'Helloxy'
    expect(getBlockText(editor)).toBe('Helloxy');

    // Simulate clicking at start of block (pos 1) — outside buffer
    setCursor(editor, 1);
    // The plugin's view.update detects selection moved outside buffer and commits
    // We need to trigger an update cycle — dispatch a no-op transaction
    editor.view.dispatch(editor.view.state.tr);

    // Buffer should be committed: 'xy' replaced with '[xy]'
    expect(getBlockText(editor)).toContain('[xy]');
    editor.destroy();
  });

  test('clicking within buffer does not commit', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'b');
    sendKey(editor, 'c');
    // bufferStart=1, buffer='abc', cursor at 4
    // Click within buffer (pos 2)
    setCursor(editor, 2);
    editor.view.dispatch(editor.view.state.tr);

    // Should NOT commit — raw text still in editor
    expect(getBlockText(editor)).toBe('abc');

    // Can still commit normally
    sendKey(editor, 'Enter');
    expect(getBlockText(editor)).toBe('[abc]');
    editor.destroy();
  });

  // -- ArrowUp/Down commit buffer --

  test('ArrowUp commits buffer', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'b');
    sendKey(editor, 'ArrowUp');
    expect(getBlockText(editor)).toBe('[ab]');
    editor.destroy();
  });

  test('ArrowDown commits buffer', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'c');
    sendKey(editor, 'd');
    sendKey(editor, 'ArrowDown');
    expect(getBlockText(editor)).toBe('[cd]');
    editor.destroy();
  });

  // -- Other non-IME keys --

  test('Tab commits buffer then passes through', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');

    sendKey(editor, 'Tab');
    expect(getBlockText(editor)).toBe('[a]');
    editor.destroy();
  });

  // -- Disabled IME --

  test('when IME is disabled, keys pass through normally', () => {
    imeConfig.enabled = false;
    const editor = createEditorWithIME();
    sendKey(editor, 'a');

    // With IME disabled, 'a' should be handled by ProseMirror default input
    // The popup should not appear
    const popup = getPopup();
    expect(popup).toBeNull();
    editor.destroy();
  });

  // -- Multiple words --

  test('typing multiple words with Space between them', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    sendKey(editor, 'b');
    sendKey(editor, ' ');
    // First word committed: '[ab] '
    sendKey(editor, 'c');
    sendKey(editor, 'd');
    sendKey(editor, 'Enter');
    // Second word committed: '[ab] [cd]'
    expect(getBlockText(editor)).toBe('[ab] [cd]');
    editor.destroy();
  });

  // -- Popup lifecycle --

  test('popup is not created until first character is typed', () => {
    const editor = createEditorWithIME();
    expect(getPopup()).toBeNull();

    sendKey(editor, 'a');
    expect(getPopup()).not.toBeNull();
    editor.destroy();
  });

  test('popup is removed from DOM on editor destroy', () => {
    const editor = createEditorWithIME();
    sendKey(editor, 'a');
    expect(getPopup()).not.toBeNull();

    editor.destroy();
    expect(getPopup()).toBeNull();
  });

  // -- Editor without IME config --

  test('editor without imeGetConfig works normally', () => {
    const editor = new ProseMirrorEditor(container, '<page><p></p></page>');
    // Should not throw; no IME plugin loaded
    sendKey(editor, 'a');
    expect(getPopup()).toBeNull();
    editor.destroy();
  });
});
