/* globals Alpine */

import { EditorState } from 'prosemirror-state';
import { EditorView } from 'prosemirror-view';
import {
  DOMParser, Node, Schema, DOMOutputSpec,
} from 'prosemirror-model';
import { keymap } from 'prosemirror-keymap';
import { undo, redo, history } from 'prosemirror-history';
import { baseKeymap } from 'prosemirror-commands';

const almostTrivialSchema = new Schema({
  nodes: {
    // The document is a nonempty sequence of lines.
    doc: { content: 'line+' },
    // A line on the page. Represented in the DOM as a `<p>` element.
    line: {
      content: 'text*',
      parseDOM: [{ tag: 'p' }],
      toDOM() { return ['p', 0] as DOMOutputSpec; },
    },
    text: { inline: true },
  },
});

// Parse a string (the contents of the textarea) into a HTML element.
// Just splits on line breaks.
function domFromText(text: string): HTMLDivElement {
  const dom = document.createElement('div');
  // The "-1" is for empty lines: https://stackoverflow.com/q/14602062
  text.split(/(?:\r\n?|\n)/, -1).forEach((line) => {
    const p = dom.appendChild(document.createElement('p'));
    p.appendChild(document.createTextNode(line));
    dom.appendChild(p);
  });
  return dom;
}

function fromText(text: string): Node {
  const dom = domFromText(text);
  const ret = DOMParser.fromSchema(almostTrivialSchema).parse(dom, { preserveWhitespace: 'full' });
  return ret;
}

// Serializes the EditorState into a plain text string.
function toText(): string {
  const doc = (window as any).view.state.doc.toJSON();
  /*
    The JSON looks like:
          {
              "type": "doc",
              "content": [
                  {
                      "type": "line",
                      "content": [
                          {
                              "type": "text",
                              "text": "This is the first line."
                          }
                      ]
                  },
                  {
                      "type": "line"
                  },
              ]
          }
    etc.
  */
  return doc.content.map((line) => (line.content ? line.content[0].text : '')).join('\n');
}

// Create a new ProseMirror editor with the contents of the textarea, and hide the textarea.
function replaceTextareaWithPmeditor() {
  const $textarea = document.querySelector('textarea')!;
  const editor = document.getElementById('editor')!;
  // Initialize an editor with the textarea's contents.
  const state = EditorState.create({
    schema: almostTrivialSchema,
    doc: fromText($textarea.textContent!),
    plugins: [
      history(),
      keymap({ 'Mod-z': undo, 'Mod-y': redo }),
      keymap(baseKeymap),
    ],
  });
    // Render it.
  const view = new EditorView(editor, { state });
  (window as any).view = view;

    // Before the form is submitted, copy contents of the ProseMirror editor back to the textarea.
    document.querySelector('form')!.addEventListener(
      'submit',
      (event) => { $textarea.value = toText(); },
    );
}

replaceTextareaWithPmeditor();
