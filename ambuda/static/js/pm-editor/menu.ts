// Contents of the menu bar. https://github.com/prosemirror/prosemirror-menu
// Subset of https://github.com/ProseMirror/prosemirror-example-setup/blob/master/src/menu.ts
import { undoItem, redoItem, MenuElement } from "prosemirror-menu"
import { Schema } from "prosemirror-model"


type MenuItemResult = {
    /// An array of arrays of menu elements.
    fullMenu: MenuElement[][]
}

export function buildMenuItems(_schema: Schema): MenuItemResult {
    return {
        fullMenu: [[undoItem, redoItem]]
    };
}