// Adding basic functionality (like a menu bar and keyboard shortcuts) to the editor.
// Subset of prosemirror-example-setup: https://github.com/ProseMirror/prosemirror-example-setup

import { Schema } from "prosemirror-model"
import { keymap } from "prosemirror-keymap"
import { history } from "prosemirror-history"
import { baseKeymap } from "prosemirror-commands"
import { menuBar } from "prosemirror-menu"
import { inputRules } from "prosemirror-inputrules"

import { buildMenuItems } from "./menu"
import buildKeymap from "./keymap"

// An array of plugins.
export function plugins(schema: Schema) {
    const plugins = [
        inputRules({ rules: [] }),
        // Keys we defined
        keymap(buildKeymap(schema)),
        // The default keys provided by the prosemirror-commands module
        keymap(baseKeymap),
        // The undo history plugin
        history(),
        // A custom plugin that adds a `menuContent` prop for the prosemirror-menu wrapper
        menuBar({
            floating: true,
            content: buildMenuItems(schema).fullMenu
        }),
    ];
    return plugins;
}