# SPDX-License-Identifier: GPL-3.0-or-later
"""Template engine.

  ${purple}  ${purple|rgb}  ${purple|a35}  ${purple|nohash}  ${radius}  ${name}  ${version}
  /*@if key=value*/ ... /*@end*/   block kept only when config[key] == value
  #@if key=value ... #@end          same, for line-comment formats (toml, conf)
"""
import re

from . import __version__

RX = re.compile(r"\$\{([\w-]+)(?:\|(rgb|nohash|a(\d+)))?\}")
IF = re.compile(r"(?:/\*|#)@if (\w+)=(\w+)\*?/?\n?(.*?)(?:/\*|#)@end\*?/?\n?", re.S)


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def render(text, tokens, cfg, where=""):
    text = IF.sub(lambda m: m.group(3) if str(cfg.get(m.group(1))) == m.group(2) else "", text)

    def sub(m):
        key, mod, alpha = m.groups()
        if key == "name":
            return "Nebulix"
        if key == "version":
            return __version__
        if key not in tokens:
            raise KeyError(f"token desconhecido ${{{key}}} em {where}")
        v = tokens[key]
        if mod is None:
            return v
        if mod == "rgb":
            return ", ".join(map(str, _rgb(v)))
        if mod == "nohash":
            return v.lstrip("#")
        r, g, b = _rgb(v)
        return f"rgba({r}, {g}, {b}, {int(alpha) / 100:g})"
    return RX.sub(sub, text)
