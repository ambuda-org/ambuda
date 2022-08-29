// Contents of the menu bar.
// Subset of https://github.com/ProseMirror/prosemirror-example-setup/blob/master/src/menu.ts
import { undoItem, redoItem, MenuElement } from "prosemirror-menu"
import { Schema } from "prosemirror-model"


type MenuItemResult = {
    /// An array of arrays of menu elements. For the menu bar:
    /// https://github.com/prosemirror/prosemirror-menu
    fullMenu: MenuElement[][]
}

export function buildMenuItems(_schema: Schema): MenuItemResult {
    let cut = <T>(arr: T[]) => arr.filter(x => x) as NonNullable<T>[];

    let r = {
        fullMenu: [[undoItem, redoItem]]
    };
    return r
}