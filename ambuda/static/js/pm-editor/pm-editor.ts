/* globals Alpine */

import { EditorState } from "prosemirror-state"
import { EditorView } from "prosemirror-view"
import { DOMParser, Node } from "prosemirror-model"

import { almostTrivialSchema } from "./schema"
import { plugins } from "./plugins"

// Parse a string (the contents of the textarea) into a HTML element.
// Just splits on line breaks.
function domFromText(text: string): HTMLDivElement {
    const dom = document.createElement("div");
    // The "-1" is for empty lines: https://stackoverflow.com/q/14602062
    text.split(/(?:\r\n?|\n)/, -1).forEach(line => {
        let p = dom.appendChild(document.createElement("p"));
        p.appendChild(document.createTextNode(line));
        dom.appendChild(p);
    });
    return dom;
};

function fromText(text: string): Node {
    const dom = domFromText(text);
    const ret = DOMParser.fromSchema(almostTrivialSchema).parse(dom, { preserveWhitespace: "full" });
    return ret;
}

// Create a new ProseMirror editor with the contents of the textarea, and hide the textarea.
function replaceTextareaWithPmeditor() {
    const $textarea = document.querySelector('textarea')!;
    if ($textarea.style.display == 'none') {
        return;
    }
    const editor = document.getElementById('editor')!;
    // Initialze it with the textarea's contents.
    const view = new EditorView(editor, {
        state: EditorState.create({
            schema: almostTrivialSchema,
            doc: fromText($textarea.textContent!),
            plugins: plugins(almostTrivialSchema)
        })
    });
    (window as any).view = view;

    // Serializes the EditorState into a plain text string.
    function toText(): string {
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
        return doc.content.map(line => line.content ? line.content[0].text : '').join('\n');
    }

    // To be safe, first verify that the round-trip is clean, at least initially.
    // console.log($textarea.textContent, '-- the contents of the textarea.');
    // console.log(toText(), '-- the result of toText');
    console.assert(toText() == $textarea.textContent); // TODO: Show error message if this fails.

    // Make it visible
    editor.style.display = 'unset';
    $textarea.style.display = 'none';

    // Before the form is submitted, copy the contents of the ProseMirror editor back to the textarea.
    document.querySelector('form')!.addEventListener('submit', (event) => { $textarea.value = toText(); });
}

// TODO: Figure out how to make this available "properly".
(window as any).replaceTextareaWithPmeditor = replaceTextareaWithPmeditor;