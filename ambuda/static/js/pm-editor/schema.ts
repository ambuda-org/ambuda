// The schema for the documents to be edited.
// A subset of prosemirror-schema-basic: https://github.com/ProseMirror/prosemirror-schema-basic

import { Schema, NodeSpec, DOMOutputSpec } from 'prosemirror-model';

const pDOM: DOMOutputSpec = ['p', 0];

/// Specs for the nodes defined in this schema.
const nodes = {
  /// NodeSpec The top level document node.
  doc: {
    content: 'block+',
  } as NodeSpec,

  /// A line on the page. Represented in the DOM as a `<p>` element.
  line: {
    content: 'inline*',
    group: 'block',
    parseDOM: [{ tag: 'p' }],
    toDOM() { return pDOM; },
  } as NodeSpec,

  /// A text node (contents of a line).
  text: {
    group: 'inline',
  } as NodeSpec,
};

const almostTrivialSchema = new Schema({
  nodes,
});

export default almostTrivialSchema;
