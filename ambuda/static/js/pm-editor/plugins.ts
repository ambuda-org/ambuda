// Subset of prosemirror-example-setup: https://github.com/ProseMirror/prosemirror-example-setup

import { Schema } from "prosemirror-model"
import { keymap } from "prosemirror-keymap"
import { history } from "prosemirror-history"
import { baseKeymap } from "prosemirror-commands"
import { Plugin } from "prosemirror-state"
import { dropCursor } from "prosemirror-dropcursor"
import { gapCursor } from "prosemirror-gapcursor"
import { menuBar } from "prosemirror-menu"
import { inputRules, smartQuotes, emDash, ellipsis } from "prosemirror-inputrules"

import { buildMenuItems } from "./menu"
import { buildKeymap } from "./keymap"

// An array of plugins.
export function plugins(schema: Schema) {
    const plugins = [
        // Input rules for smart quotes etc. See https://github.com/ProseMirror/prosemirror-inputrules for more.
        inputRules({ rules: smartQuotes.concat(ellipsis, emDash) }),
        // A keymap that defines keys to create and manipulate the nodes in the schema
        keymap(buildKeymap(schema)),
        // A keymap binding the default keys provided by the prosemirror-commands module
        keymap(baseKeymap),
        // The drop cursor plugin
        dropCursor(),
        // The gap cursor plugin
        gapCursor(),
        // The undo history plugin
        history(),
        // A custom plugin that adds a `menuContent` prop for the prosemirror-menu wrapper
        menuBar({
            floating: true,
            content: buildMenuItems(schema).fullMenu
        }),
        // and a CSS class that enables the additional styling defined in `style/style.css` in this package
        new Plugin({
            props: {
                attributes: { class: "ProseMirror-example-setup-style" }
            }
        })
    ];
    return plugins;
}