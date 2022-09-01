/* globals Alpine */

import { EditorState } from 'prosemirror-state';
import { EditorView } from 'prosemirror-view';
import { DOMParser, Node } from 'prosemirror-model';

import almostTrivialSchema from './schema';
import plugins from './plugins';

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
        plugins: plugins(almostTrivialSchema),
    });
    // Render it.
    const view = new EditorView(editor, {
        state,
        dispatchTransaction(transaction) {
            console.log("Document size went from", transaction.before.content.size,
                "to", transaction.doc.content.size);
            let newState = view.state.apply(transaction);
            view.updateState(newState);
        }
    });
    (window as any).view = view;

    // Before the form is submitted, copy contents of the ProseMirror editor back to the textarea.
    document.querySelector('form')!.addEventListener(
        'submit',
        (event) => { $textarea.value = toText(); },
    );
}

replaceTextareaWithPmeditor();
