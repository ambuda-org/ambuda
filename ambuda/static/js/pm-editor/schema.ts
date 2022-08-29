// The schema for the documents to be edited.
// A subset of prosemirror-schema-basic: https://github.com/ProseMirror/prosemirror-schema-basic

import { Schema, NodeSpec, DOMOutputSpec } from "prosemirror-model"

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

export const almostTrivialSchema = new Schema({
    nodes: nodes,
})