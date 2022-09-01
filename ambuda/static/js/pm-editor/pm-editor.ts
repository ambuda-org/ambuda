import { EditorState } from 'prosemirror-state';
import { EditorView } from 'prosemirror-view';
import {
  DOMOutputSpec, DOMParser, Node, Schema,
} from 'prosemirror-model';
import { keymap } from 'prosemirror-keymap';
import { undo, redo, history } from 'prosemirror-history';
import { baseKeymap } from 'prosemirror-commands';

const schema = new Schema({
  nodes: {
    // The document (page) is a nonempty sequence of lines.
    doc: { content: 'line+' },
    // A line contains text. Represented in the DOM as a `<p>` element.
    line: {
      content: 'text*',
      parseDOM: [{ tag: 'p' }],
      toDOM() { return ['p', 0] as DOMOutputSpec; },
    },
    text: { inline: true },
  },
});

// Turns `text` into a `Document` corresponding to our schema. Just splits on line breaks.
function docFromText(text: string): Node {
  // Could create it manually with schema.node() and schema.text(),
  // but can also turn into div and parse it.
  const dom = document.createElement('div');
  // The "-1" is so that empty lines are retained: https://stackoverflow.com/q/14602062
  text.split(/(?:\r\n?|\n)/, -1).forEach((line) => {
    const p = dom.appendChild(document.createElement('p'));
    p.appendChild(document.createTextNode(line));
    dom.appendChild(p);
  });
  const ret = DOMParser.fromSchema(schema).parse(dom, { preserveWhitespace: 'full' });
  return ret;
}

// Serializes the EditorState (assuming the schema above) into a plain text string.
export function toText(view: EditorView): string {
  const doc = view.state.doc.toJSON();
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

// Creates editor with contents from `text`, appends it to `parentNode`. Returns its EditorView.
export function createEditorFromTextAt(text: string, parentNode: HTMLElement): EditorView {
  const state = EditorState.create({
    doc: docFromText(text),
    plugins: [
      history(),
      keymap({ 'Mod-z': undo, 'Mod-y': redo }),
      keymap(baseKeymap),
    ],
  });
  // Display the editor.
  const view = new EditorView(parentNode, { state });
  return view;
}
