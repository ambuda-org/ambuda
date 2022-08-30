// Keyboard shortcuts.
// Subset of https://github.com/ProseMirror/prosemirror-example-setup/blob/master/src/keymap.ts

import { undo, redo } from 'prosemirror-history';
import { undoInputRule } from 'prosemirror-inputrules';
import { Command } from 'prosemirror-state';
import { Schema } from 'prosemirror-model';

const mac = typeof navigator !== 'undefined' ? /Mac|iP(hone|[oa]d)/.test(navigator.platform) : false;

function buildKeymap(schema: Schema) {
  const keys = {};
  function bind(key: string, cmd: Command) {
    keys[key] = cmd;
  }

  bind('Mod-z', undo);
  bind('Shift-Mod-z', redo);
  if (!mac) bind('Mod-y', redo);

  bind('Backspace', undoInputRule);

  return keys;
}

export default buildKeymap;
