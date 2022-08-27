// Subset of https://github.com/ProseMirror/prosemirror-example-setup/blob/master/src/keymap.ts

import {
    setBlockType, chainCommands, toggleMark, exitCode,
    joinUp, joinDown, lift, selectParentNode
} from "prosemirror-commands"
import { undo, redo } from "prosemirror-history"
import { undoInputRule } from "prosemirror-inputrules"
import { Command } from "prosemirror-state"
import { Schema } from "prosemirror-model"

const mac = typeof navigator != "undefined" ? /Mac|iP(hone|[oa]d)/.test(navigator.platform) : false

export function buildKeymap(schema: Schema) {
    let keys: { [key: string]: Command } = {}, type
    function bind(key: string, cmd: Command) {
        keys[key] = cmd
    }

    bind("Mod-z", undo)
    bind("Shift-Mod-z", redo)
    if (!mac) bind("Mod-y", redo)
    /// * **Backspace** to undo an input rule
    bind("Backspace", undoInputRule)

    /// * **Alt-ArrowUp** to `joinUp`
    bind("Alt-ArrowUp", joinUp)
    /// * **Alt-ArrowDown** to `joinDown`
    bind("Alt-ArrowDown", joinDown)
    /// * **Mod-BracketLeft** to `lift`
    bind("Mod-BracketLeft", lift)
    /// * **Escape** to `selectParentNode`
    bind("Escape", selectParentNode)

    if (type = schema.marks.strong) {
        /// * **Mod-b** for toggling [strong](#schema-basic.StrongMark)
        bind("Mod-b", toggleMark(type))
        bind("Mod-B", toggleMark(type))
    }
    if (type = schema.marks.em) {
        /// * **Mod-i** for toggling [emphasis](#schema-basic.EmMark)
        bind("Mod-i", toggleMark(type))
        bind("Mod-I", toggleMark(type))
    }
    /// * **Mod-Enter** to insert a hard break
    if (type = schema.nodes.hard_break) {
        let br = type, cmd = chainCommands(exitCode, (state, dispatch) => {
            if (dispatch) dispatch(state.tr.replaceSelectionWith(br.create()).scrollIntoView())
            return true
        })
        bind("Mod-Enter", cmd)
        bind("Shift-Enter", cmd)
        if (mac) bind("Ctrl-Enter", cmd)
    }
    /// * **Ctrl-Shift-0** for making the current textblock a paragraph
    if (type = schema.nodes.paragraph)
        bind("Shift-Ctrl-0", setBlockType(type))
    /// * **Mod-_** to insert a horizontal rule
    if (type = schema.nodes.horizontal_rule) {
        let hr = type
        bind("Mod-_", (state, dispatch) => {
            if (dispatch) dispatch(state.tr.replaceSelectionWith(hr.create()).scrollIntoView())
            return true
        })
    }

    return keys
}