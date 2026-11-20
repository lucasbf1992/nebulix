# SPDX-License-Identifier: GPL-3.0-or-later
"""Activate the Nebulix theme in VS Code (and Insiders/VSCodium) by editing `workbench.colorTheme`
in the user's settings.json in place. The file is JSONC (comments, trailing commas), so it is never
re-serialised: only the one key is replaced, inserted or removed."""
import json
import re
from pathlib import Path

from . import paths

KEY = "workbench.colorTheme"
# (settings dir under ~/.config, extensions dir under ~)
EDITORS = (("Code", ".vscode"), ("Code - Insiders", ".vscode-insiders"), ("VSCodium", ".vscode-oss"))
_SPACE = re.compile(r"\s+")


def installed_editors():
    """[(settings.json path, extensions dir)] for editors whose user dir exists."""
    return [(paths.conf_home() / name / "User" / "settings.json", paths.home() / ext)
            for name, ext in EDITORS if (paths.conf_home() / name / "User").is_dir()]


def _tokens(text):
    """[(kind, start, end, depth)] skipping whitespace and comments; kind is 'str', 'p' (punctuation) or 'o'."""
    out, i, n, depth = [], 0, len(text), 0
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(("str", i, j + 1, depth))
            i = j + 1
        elif c in "{}[],:":
            if c in "}]":
                depth -= 1
            out.append(("p", i, i + 1, depth))
            if c in "{[":
                depth += 1
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '{}[],:"/':
                j += 1
            j = max(j, i + 1)
            out.append(("o", i, j, depth))
            i = j
    return out


def _find(text, key=KEY):
    """Index of the key token at the top level of the root object, or None."""
    tk = _tokens(text)
    for k, (kind, s, e, d) in enumerate(tk):
        if kind == "str" and d == 1 and k + 2 < len(tk) and text[tk[k + 1][1]] == ":" and tk[k + 1][0] == "p" \
                and text[tk[k - 1][1]] in "{," and json.loads(text[s:e]) == key:
            return tk, k
    return tk, None


def get(text, key=KEY):
    tk, k = _find(text, key)
    if k is None:
        return None
    s, e = tk[k + 2][1], tk[k + 2][2]
    try:
        return json.loads(text[s:e])
    except ValueError:
        return None


def set_key(text, value, key=KEY):
    if not text.strip():
        return "{\n    " + json.dumps(key) + ": " + json.dumps(value) + "\n}\n"
    tk, k = _find(text, key)
    if k is not None:
        return text[:tk[k + 2][1]] + json.dumps(value) + text[tk[k + 2][2]:]
    if not tk or text[tk[0][1]] != "{" or tk[0][0] != "p":
        raise ValueError("settings.json não é um objeto JSON")
    empty = len(tk) > 1 and text[tk[1][1]] == "}"
    ins = "\n    " + json.dumps(key) + ": " + json.dumps(value) + ("" if empty else ",")
    return text[:tk[0][2]] + ins + text[tk[0][2]:]


def remove_key(text, key=KEY):
    tk, k = _find(text, key)
    if k is None:
        return text
    start, end = tk[k][1], tk[k + 2][2]
    if k + 3 < len(tk) and text[tk[k + 3][1]] == ",":
        end = tk[k + 3][2]
    elif text[tk[k - 1][1]] == ",":
        start = tk[k - 1][1]
    # swallow the now-empty line
    ls = text.rfind("\n", 0, start) + 1
    le = text.find("\n", end)
    le = len(text) if le < 0 else le + 1
    if not text[ls:start].strip() and not text[end:le].strip():
        start, end = ls, le
    return text[:start] + text[end:]


def apply_theme(st, label):
    """Set workbench.colorTheme to `label` in every installed editor; remembers the previous value in the state."""
    for f, _ in installed_editors():
        st.log(f"→ {f} ({KEY} = {label})")
        if st.dry:
            continue
        existed = f.exists()
        text = f.read_text() if existed else ""
        try:
            new = set_key(text, label)
        except ValueError as e:
            st.log(f"! {f}: {e}; não alterado")
            continue
        tag = f"vscode:{f}"
        if not any(m.split("\t", 1)[0] == tag for m in st.manifest):
            prev = get(text)
            st.manifest.append(f"{tag}\t{int(existed)}\t{json.dumps(prev)}")
        f.write_text(new)


def release(st):
    """vscode_theme went back to 'keep': put the previous value back and stop tracking."""
    for m in [m for m in st.manifest if m.startswith("vscode:")]:
        restore_entry(m, "undo", st.dry, st.log)
        if not st.dry:
            st.manifest.remove(m)


def restore_entry(entry, mode, dry=False, log=print):
    """undo: previous value (or no key, and no file if we created it). reset: the key is removed."""
    tag, existed, prev = entry.split("\t", 2)
    f = Path(tag[len("vscode:"):])
    log(f"{KEY} em {f} ← {'(removido)' if mode == 'reset' or prev == 'null' else prev}")
    if dry or not f.exists():
        return
    text = f.read_text()
    try:
        new = remove_key(text) if mode == "reset" or prev == "null" else set_key(text, json.loads(prev))
    except ValueError:
        return
    if existed == "0" and not new.strip().strip("{}").strip() and get(new) is None:
        f.unlink()  # we created the file and nothing else lives in it
    else:
        f.write_text(new)
