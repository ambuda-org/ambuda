// The schema for the documents to be edited.
// A subset of prosemirror-schema-basic: https://github.com/ProseMirror/prosemirror-schema-basic

import { Schema, NodeSpec, MarkSpec, DOMOutputSpec } from "prosemirror-model"

// const trivialSchema = new Schema({
//     nodes: {
//         doc: { content: "paragraph+" },
//         paragraph: {
//             content: "text*",
//             toDOM: () => ["p", 0],
//         },
//         text: { inline: true },
//     }
// })

const pDOM: DOMOutputSpec = ["p", 0],
    brDOM: DOMOutputSpec = ["br"]

/// Specs for the nodes defined in this schema.
const nodes = {
    /// NodeSpec The top level document node.
    doc: {
        content: "block+"
    } as NodeSpec,

    /// A plain paragraph textblock. Represented in the DOM
    /// as a `<p>` element.
    paragraph: {
        content: "inline*",
        group: "block",
        parseDOM: [{ tag: "p" }],
        toDOM() { return pDOM }
    } as NodeSpec,

    /// The text node.
    text: {
        group: "inline"
    } as NodeSpec,

    /// A hard line break, represented in the DOM as `<br>`.
    hard_break: {
        inline: true,
        group: "inline",
        selectable: false,
        parseDOM: [{ tag: "br" }],
        toDOM() { return brDOM }
    } as NodeSpec
}

// Marks.
const emDOM: DOMOutputSpec = ["em", 0],
    strongDOM: DOMOutputSpec = ["strong", 0];
/// [Specs](#model.MarkSpec) for the marks in the schema.
const marks = {
    /// An emphasis mark. Rendered as an `<em>` element. Has parse rules
    /// that also match `<i>` and `font-style: italic`.
    em: {
        parseDOM: [{ tag: "i" }, { tag: "em" }, { style: "font-style=italic" }],
        toDOM() { return emDOM }
    } as MarkSpec,

    /// A strong mark. Rendered as `<strong>`, parse rules also match
    /// `<b>` and `font-weight: bold`.
    strong: {
        parseDOM: [{ tag: "strong" },
        // This works around a Google Docs misbehavior where
        // pasted content will be inexplicably wrapped in `<b>`
        // tags with a font-weight normal.
        { tag: "b", getAttrs: (node: HTMLElement) => node.style.fontWeight != "normal" && null },
        { style: "font-weight", getAttrs: (value: string) => /^(bold(er)?|[5-9]\d{2,})$/.test(value) && null }],
        toDOM() { return strongDOM }
    } as MarkSpec,
}

export const almostTrivialSchema = new Schema({
    nodes: nodes,
    // marks: marks
})