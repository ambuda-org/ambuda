// Subset of https://github.com/ProseMirror/prosemirror-example-setup/blob/master/src/menu.ts
import {
    Dropdown, joinUpItem, liftItem,
    selectParentNodeItem, undoItem, redoItem, icons, MenuItem, MenuElement, MenuItemSpec
} from "prosemirror-menu"
import { EditorState, Command } from "prosemirror-state"
import { Schema, NodeType, MarkType } from "prosemirror-model"
import { toggleMark } from "prosemirror-commands"

// Helpers to create specific types of items

function canInsert(state: EditorState, nodeType: NodeType) {
    let $from = state.selection.$from
    for (let d = $from.depth; d >= 0; d -= 1) {
        let index = $from.index(d)
        if ($from.node(d).canReplaceWith(index, index, nodeType)) return true
    }
    return false
}

function cmdItem(cmd: Command, options: Partial<MenuItemSpec>) {
    let passedOptions: MenuItemSpec = {
        label: options.title as string | undefined,
        run: cmd
    }
    for (let prop in options) (passedOptions as any)[prop] = (options as any)[prop]
    if (!options.enable && !options.select)
        passedOptions[options.enable ? "enable" : "select"] = state => cmd(state)

    return new MenuItem(passedOptions)
}

function markActive(state: EditorState, type: MarkType) {
    let { from, $from, to, empty } = state.selection
    if (empty) return !!type.isInSet(state.storedMarks || $from.marks())
    else return state.doc.rangeHasMark(from, to, type)
}

// Marking an item as strong, emphasis, etc.
function markItem(markType: MarkType, options: Partial<MenuItemSpec>) {
    let passedOptions: Partial<MenuItemSpec> = {
        active(state) { return markActive(state, markType) }
    }
    for (let prop in options) (passedOptions as any)[prop] = (options as any)[prop]
    return cmdItem(toggleMark(markType), passedOptions)
}

type MenuItemResult = {
    /// A menu item to toggle the [strong mark](#schema-basic.StrongMark).
    toggleStrong?: MenuItem

    /// A menu item to toggle the [emphasis mark](#schema-basic.EmMark).
    toggleEm?: MenuItem

    /// A menu item to set the current textblock to be a normal
    /// [paragraph](#schema-basic.Paragraph).
    makeParagraph?: MenuItem

    /// A menu item to insert a horizontal rule.
    insertHorizontalRule?: MenuItem

    /// A dropdown containing the `insertImage` and
    /// `insertHorizontalRule` items.
    insertMenu: Dropdown

    /// Array of block-related menu items.
    blockMenu: MenuElement[][]

    /// Inline-markup related menu items.
    inlineMenu: MenuElement[][]

    /// An array of arrays of menu elements for use as the full menu
    /// for, for example the [menu
    /// bar](https://github.com/prosemirror/prosemirror-menu#user-content-menubar).
    fullMenu: MenuElement[][]
}

// Relevant menu items, based on what's in schema.
export function buildMenuItems(schema: Schema): MenuItemResult {
    let r: MenuItemResult = {} as any
    let mark: MarkType | undefined
    if (mark = schema.marks.strong)
        r.toggleStrong = markItem(mark, { title: "Toggle strong style", icon: icons.strong })
    if (mark = schema.marks.em)
        r.toggleEm = markItem(mark, { title: "Toggle emphasis", icon: icons.em })

    let node: NodeType | undefined
    if (node = schema.nodes.horizontal_rule) {
        let hr = node
        r.insertHorizontalRule = new MenuItem({
            title: "Insert horizontal rule",
            label: "Horizontal rule",
            enable(state) { return canInsert(state, hr) },
            run(state, dispatch) { dispatch(state.tr.replaceSelectionWith(hr.create())) }
        })
    }

    let cut = <T>(arr: T[]) => arr.filter(x => x) as NonNullable<T>[]
    r.insertMenu = new Dropdown(cut([r.insertHorizontalRule]), { label: "Insert" })
    r.inlineMenu = [cut([r.toggleStrong, r.toggleEm])]
    r.blockMenu = [cut([joinUpItem, liftItem, selectParentNodeItem])]
    r.fullMenu = r.inlineMenu.concat([[r.insertMenu]], [[undoItem, redoItem]], r.blockMenu)

    return r
}