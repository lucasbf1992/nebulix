# SPDX-License-Identifier: GPL-3.0-or-later
"""Generators for formats that are not simple text templates."""
import json
from pathlib import Path


def _w(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def ptyxis(P, T, dist):
    a = P["ansi"]["normal"] + P["ansi"]["bright"]
    lines = ["[Palette]", "Name=Nebulix", "", "[Dark]",
             f"Foreground={T['fg-0']}", f"Background={T['bg-0']}", f"Cursor={T['magenta']}",
             f"Cursor_Foreground={T['bg-0']}" if False else f"Cursor={T['magenta']}"]
    lines = lines[:-1]
    lines += [f"Color{i}={c}" for i, c in enumerate(a)]
    lines += ["", "[Light]", f"Foreground={T['fg-0']}", f"Background={T['bg-0']}"]
    lines += [f"Color{i}={c}" for i, c in enumerate(a)]
    _w(dist / "terminal/nebulix.palette", "\n".join(lines) + "\n")


def gnome_terminal(P, T, dist):
    a = P["ansi"]["normal"] + P["ansi"]["bright"]
    pal = ", ".join(f"'{c}'" for c in a)
    txt = f"""[/]
visible-name='Nebulix'
use-theme-colors=false
foreground-color='{T['fg-0']}'
background-color='{T['bg-0']}'
bold-color-same-as-fg=true
cursor-colors-set=true
cursor-background-color='{T['magenta']}'
cursor-foreground-color='{T['bg-0']}'
highlight-colors-set=true
highlight-background-color='{T['purple']}'
highlight-foreground-color='{T['bg-0']}'
palette=[{pal}]
font='JetBrainsMono Nerd Font 11'
use-system-font=false
"""
    _w(dist / "terminal/nebulix-gnome-terminal.dconf", txt)


def vscode(P, T, dist):
    b = T
    ui = {
        "editor.background": b["bg-0"], "editor.foreground": b["fg-0"],
        "editorLineNumber.foreground": b["fg-2"], "editorLineNumber.activeForeground": b["purple"],
        "editor.selectionBackground": b["purple"] + "59", "editor.lineHighlightBackground": b["bg-1"],
        "editorCursor.foreground": b["magenta"], "editorWhitespace.foreground": b["border"],
        "editorIndentGuide.background1": b["bg-2"], "editorIndentGuide.activeBackground1": b["border"],
        "editor.findMatchBackground": b["magenta"] + "55", "editor.wordHighlightBackground": b["purple"] + "33",
        "editorBracketMatch.border": b["magenta"], "editorBracketMatch.background": b["bg-3"],
        "editorGroupHeader.tabsBackground": b["bg-0"], "tab.activeBackground": b["bg-0"],
        "tab.inactiveBackground": b["bg-0"], "tab.activeForeground": b["fg-0"],
        "tab.inactiveForeground": b["fg-2"], "tab.activeBorderTop": b["purple"], "tab.border": b["bg-0"],
        "sideBar.background": b["bg-0"], "sideBar.foreground": b["fg-1"], "sideBar.border": b["bg-2"],
        "sideBarTitle.foreground": b["fg-1"], "sideBarSectionHeader.background": b["bg-0"],
        "activityBar.background": b["bg-0"], "activityBar.foreground": b["purple"],
        "activityBar.inactiveForeground": b["fg-2"], "activityBar.activeBorder": b["purple"],
        "activityBarBadge.background": b["magenta"], "activityBarBadge.foreground": b["bg-0"],
        "statusBar.background": b["purple"], "statusBar.foreground": b["bg-0"],
        "statusBar.noFolderBackground": b["purple-dim"], "statusBar.debuggingBackground": b["magenta"],
        "titleBar.activeBackground": b["bg-0"], "titleBar.activeForeground": b["fg-1"],
        "titleBar.inactiveBackground": b["bg-0"], "titleBar.border": b["bg-2"],
        "panel.background": b["bg-0"], "panel.border": b["border"],
        "panelTitle.activeForeground": b["fg-0"], "panelTitle.activeBorder": b["purple"],
        "terminal.background": b["bg-0"], "terminal.foreground": b["fg-0"],
        "terminalCursor.foreground": b["magenta"], "terminal.selectionBackground": b["purple"] + "59",
        "list.activeSelectionBackground": b["bg-3"], "list.activeSelectionForeground": b["fg-0"],
        "list.hoverBackground": b["bg-2"], "list.inactiveSelectionBackground": b["bg-2"],
        "list.highlightForeground": b["magenta"],
        "input.background": b["bg-2"], "input.border": b["border"], "input.foreground": b["fg-0"],
        "input.placeholderForeground": b["fg-2"], "focusBorder": b["purple"],
        "button.background": b["purple"], "button.foreground": b["bg-0"], "button.hoverBackground": b["purple-dim"],
        "dropdown.background": b["bg-2"], "dropdown.border": b["border"],
        "badge.background": b["magenta"], "badge.foreground": b["bg-0"],
        "scrollbarSlider.background": b["border"] + "88", "scrollbarSlider.hoverBackground": b["purple"] + "88",
        "editorWidget.background": b["bg-2"], "editorSuggestWidget.background": b["bg-2"],
        "editorSuggestWidget.selectedBackground": b["bg-3"], "peekViewEditor.background": b["bg-1"],
        "gitDecoration.modifiedResourceForeground": b["yellow"], "gitDecoration.untrackedResourceForeground": b["green"],
        "gitDecoration.deletedResourceForeground": b["red"], "editorError.foreground": b["red"],
        "editorWarning.foreground": b["yellow"], "editorInfo.foreground": b["cyan"],
        "textLink.foreground": b["cyan"], "menu.background": b["bg-2"], "menu.selectionBackground": b["bg-3"],
    }
    for i, n in enumerate(["Black", "Red", "Green", "Yellow", "Blue", "Magenta", "Cyan", "White"]):
        ui[f"terminal.ansi{n}"] = P["ansi"]["normal"][i]
        ui[f"terminal.ansiBright{n}"] = P["ansi"]["bright"][i]

    def tk(scope, fg, style=None):
        s = {"foreground": fg}
        if style:
            s["fontStyle"] = style
        return {"scope": scope, "settings": s}
    tokens = [
        tk(["comment", "punctuation.definition.comment"], b["fg-2"], "italic"),
        tk(["string", "string.quoted"], b["green"]),
        tk(["constant.numeric", "constant.language", "constant.character.escape"], b["yellow"]),
        tk(["keyword", "storage", "storage.type", "keyword.control"], b["purple"]),
        tk(["keyword.operator"], b["magenta"]),
        tk(["entity.name.function", "support.function", "meta.function-call"], b["cyan"]),
        tk(["entity.name.type", "entity.name.class", "support.class", "support.type"], b["blue"]),
        tk(["variable", "variable.other"], b["fg-0"]),
        tk(["variable.parameter"], b["fg-1"], "italic"),
        tk(["variable.language", "entity.name.tag"], b["red"]),
        tk(["entity.other.attribute-name"], b["yellow"], "italic"),
        tk(["punctuation", "meta.brace"], b["fg-1"]),
        tk(["markup.heading", "entity.name.section"], b["purple"], "bold"),
        tk(["markup.bold"], b["fg-0"], "bold"), tk(["markup.italic"], b["fg-0"], "italic"),
        tk(["markup.inline.raw", "markup.fenced_code"], b["green"]),
        tk(["markup.underline.link", "string.other.link"], b["cyan"]),
        tk(["support.type.property-name.json"], b["purple"]),
    ]
    theme = {"name": "Nebulix Dark", "type": "dark", "colors": ui, "tokenColors": tokens,
             "semanticHighlighting": True}
    d = dist / "vscode/nebulix-theme"
    _w(d / "themes/nebulix-color-theme.json", json.dumps(theme, indent=2, ensure_ascii=False) + "\n")
    pkg = {
        "name": "nebulix-theme", "displayName": "Nebulix", "description": "Dark purple theme for developers.",
        "version": P["version"], "publisher": "nebulix", "license": "MIT",
        "engines": {"vscode": "^1.80.0"}, "categories": ["Themes"],
        "contributes": {"themes": [{"label": "Nebulix Dark", "uiTheme": "vs-dark",
                                    "path": "./themes/nebulix-color-theme.json"}]},
    }
    _w(d / "package.json", json.dumps(pkg, indent=2) + "\n")
    _w(d / "LICENSE", "MIT License\n\nCopyright (c) Nebulix contributors\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the \"Software\"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.\n")


def nvim(P, T, dist):
    b = T
    hl = {
        "Normal": (b["fg-0"], b["bg-0"]), "NormalFloat": (b["fg-0"], b["bg-2"]), "CursorLine": (None, b["bg-1"]),
        "LineNr": (b["fg-2"], None), "CursorLineNr": (b["purple"], None), "Visual": (None, b["bg-3"]),
        "Comment": (b["fg-2"], None, "italic"), "String": (b["green"], None), "Number": (b["yellow"], None),
        "Constant": (b["yellow"], None), "Keyword": (b["purple"], None), "Statement": (b["purple"], None),
        "Function": (b["cyan"], None), "Type": (b["blue"], None), "Identifier": (b["fg-0"], None),
        "Operator": (b["magenta"], None), "PreProc": (b["magenta"], None), "Special": (b["cyan"], None),
        "Pmenu": (b["fg-0"], b["bg-2"]), "PmenuSel": (b["fg-0"], b["bg-3"]), "Search": (b["bg-0"], b["magenta"]),
        "StatusLine": (b["bg-0"], b["purple"]), "StatusLineNC": (b["fg-2"], b["bg-2"]),
        "VertSplit": (b["border"], None), "WinSeparator": (b["border"], None),
        "ErrorMsg": (b["red"], None), "WarningMsg": (b["yellow"], None), "Todo": (b["bg-0"], b["yellow"]),
        "DiffAdd": (None, b["bg-2"]), "DiffDelete": (b["red"], None), "DiffChange": (None, b["bg-3"]),
        "MatchParen": (b["magenta"], b["bg-3"]), "Cursor": (b["bg-0"], b["magenta"]),
        "DiagnosticError": (b["red"], None), "DiagnosticWarn": (b["yellow"], None),
        "DiagnosticInfo": (b["cyan"], None), "DiagnosticHint": (b["blue"], None),
    }
    out = ["-- SPDX-License-Identifier: MIT", "-- Nebulix colorscheme (generated by build.py)",
           "vim.cmd('highlight clear')", "if vim.fn.exists('syntax_on') == 1 then vim.cmd('syntax reset') end",
           "vim.o.termguicolors = true", "vim.o.background = 'dark'", "vim.g.colors_name = 'nebulix'", "local hl = vim.api.nvim_set_hl"]
    for name, v in hl.items():
        fg, bgc = v[0], v[1]
        parts = []
        if fg:
            parts.append(f"fg = '{fg}'")
        if bgc:
            parts.append(f"bg = '{bgc}'")
        if len(v) > 2:
            parts.append(f"{v[2]} = true")
        out.append(f"hl(0, '{name}', {{ {', '.join(parts)} }})")
    for i, c in enumerate(P["ansi"]["normal"] + P["ansi"]["bright"]):
        out.append(f"vim.g.terminal_color_{i} = '{c}'")
    _w(dist / "nvim/colors/nebulix.lua", "\n".join(out) + "\n")


def generate(P, T, dist):
    for f in (ptyxis, gnome_terminal, vscode, nvim):
        f(P, T, dist)
