// Adding basic functionality (like a menu bar and keyboard shortcuts) to the editor.
// Subset of prosemirror-example-setup: https://github.com/ProseMirror/prosemirror-example-setup

import { Schema } from 'prosemirror-model';
import { keymap } from 'prosemirror-keymap';
import { undo, redo, history } from "prosemirror-history"
import { baseKeymap } from 'prosemirror-commands';

// An array of plugins.
function plugins(_schema: Schema) {
  return [
    history(),
    keymap({ "Mod-z": undo, "Mod-y": redo }),
    keymap(baseKeymap),
  ];
}

export default plugins;
