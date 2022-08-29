import { EditorState } from "prosemirror-state"
import { EditorView } from "prosemirror-view"
import { DOMParser, Node } from "prosemirror-model"

import { almostTrivialSchema } from "./schema"
import { plugins } from "./plugins"

// Parse a string (the contents of the textarea) into a HTML element.
// Only recognizes blank lines as <p> separators, and line breaks as <br>.
function domFromText(text: string): HTMLDivElement {
    const dom = document.createElement("div");
    text.split(/(?:\r\n?|\n){2,}/).forEach(block => {
        let p = dom.appendChild(document.createElement("p"));
        if (block) {
            block.split(/(?:\r\n?|\n)/).forEach(line => {
                if (line) {
                    if (p.hasChildNodes()) p.appendChild(document.createElement('br'));
                    p.appendChild(document.createTextNode(line));
                }
            });
        }
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
        return view.state.doc.textBetween(
            0, // from
            view.state.doc.content.size, // to
            "\n\n", // blockSeparator
            "\n", // leafNode
        );
    }

    // To be safe, first verify that the round-trip is clean, at least initially.
    // console.log(toText());
    // console.log($textarea.textContent, '-- the contents of the textarea.');
    console.assert(toText() == $textarea.textContent); // TODO: Show error message if this fails.

    // Make it visible
    editor.style.display = 'unset';
    $textarea.style.display = 'none';

    // Before the form is submitted, copy the contents of the ProseMirror editor back to the textarea.
    document.querySelector('form')!.addEventListener('submit', (event) => { $textarea.value = toText(); });
}

// TODO: Figure out how to make this available "properly".
(window as any).replaceTextareaWithPmeditor = replaceTextareaWithPmeditor;