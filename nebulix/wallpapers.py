# SPDX-License-Identifier: CC-BY-SA-4.0
"""Generative SVG wallpapers (colored by the active accent) and PNG rasterizing via GdkPixbuf."""
import random
from html import escape as esc
from pathlib import Path

NAMES = ("orbit", "horizon", "circuit", "code")  # generators; config names are prefixed with "gen-"
SIZES = {"1080p": (1920, 1080), "1440p": (2560, 1440), "4k": (3840, 2160), "ultrawide": (3440, 1440)}


def _mix(a, b, t):
    pa, pb = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02X%02X%02X" % tuple(round(pa[i] * (1 - t) + pb[i] * t) for i in range(3))


def _head(w, h, extra=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<!-- SPDX-License-Identifier: CC-BY-SA-4.0 --><defs>{extra}</defs>')


def _glow(id_, sd):
    return (f'<filter id="{id_}" x="-50%" y="-50%" width="200%" height="200%">'
            f'<feGaussianBlur stdDeviation="{sd}"/></filter>')


def _vignette(w, h, c):
    return (f'<radialGradient id="vg" cx="50%" cy="50%" r="75%"><stop offset=".55" stop-color="{c}" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="{c}" stop-opacity=".85"/></radialGradient>', f'<rect width="{w}" height="{h}" fill="url(#vg)"/>')


def _stars(rnd, w, h, n, t, ymax=1.0, glow_id="gl"):
    out, cols = [], (t["fg-0"], t["fg-1"], t["cyan"], t["magenta"], t["purple"])
    pts = []
    for i in range(n):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h * ymax)
        big = rnd.random() < .06
        r = rnd.uniform(1.6, 2.8) * (h / 1080) if big else rnd.uniform(.5, 1.4) * (h / 1080)
        c = rnd.choice(cols) if big else t["fg-1"]
        o = rnd.uniform(.5, 1) if big else rnd.uniform(.15, .7)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="{c}" opacity="{o:.2f}"/>')
        if big:
            pts.append((x, y, c))
            s = r * 7
            out.append(f'<path d="M{x-s:.1f} {y:.1f}H{x+s:.1f}M{x:.1f} {y-s:.1f}V{y+s:.1f}" stroke="{c}" stroke-width="{.8*h/1080:.2f}" opacity=".5"/>')
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r*3:.2f}" fill="{c}" opacity=".35" filter="url(#{glow_id})"/>')
    return "".join(out), pts


def _nebula(w, h, seed, color, opacity, freq, cx="50%", cy="50%"):
    fid = f"nb{seed}"
    r, g, b = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return (f'<filter id="{fid}" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">'
            f'<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="5" seed="{seed}"/>'
            f'<feColorMatrix values="0 0 0 0 {r:.3f}  0 0 0 0 {g:.3f}  0 0 0 0 {b:.3f}  0 0 0 2.4 -0.95"/></filter>',
            f'<rect width="{w}" height="{h}" filter="url(#{fid})" opacity="{opacity}"/>')


def orbit(w, h, t, seed=7):
    rnd = random.Random(seed)
    cx, cy, R = w * .70, h * .42, min(w, h) * .19
    d1, b1 = _nebula(w, h, 3, t["purple"], .55, "0.0016 0.0022")
    d2, b2 = _nebula(w, h, 11, t["magenta"], .30, "0.0022 0.0016")
    d3, b3 = _nebula(w, h, 19, t["cyan"], .16, "0.003")
    vd, vb = _vignette(w, h, t["bg-0"])
    stars, pts = _stars(rnd, w, h, int(w * h / 5200), t)
    # constellations: link bright stars that are close
    lines = []
    for i, (x, y, c) in enumerate(pts):
        near = sorted(pts[:i] + pts[i + 1:], key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)[:1]
        for (x2, y2, _) in near:
            if (x - x2) ** 2 + (y - y2) ** 2 < (w * .16) ** 2:
                lines.append(f'<path d="M{x:.0f} {y:.0f}L{x2:.0f} {y2:.0f}" stroke="{t["fg-1"]}" stroke-width="{h/1080:.2f}" opacity=".22"/>')
    rx, ry = R * 2.45, R * .6
    ring = lambda: (f'<path fill-rule="evenodd" fill="url(#rg)" d="M{-rx:.0f} 0a{rx:.0f} {ry:.0f} 0 1 0 {2*rx:.0f} 0a{rx:.0f} {ry:.0f} 0 1 0 {-2*rx:.0f} 0Z'
                    f'M{-rx*.74:.0f} 0a{rx*.74:.0f} {ry*.74:.0f} 0 1 0 {2*rx*.74:.0f} 0a{rx*.74:.0f} {ry*.74:.0f} 0 1 0 {-2*rx*.74:.0f} 0Z"/>'
                    f'<ellipse rx="{rx*.87:.0f}" ry="{ry*.87:.0f}" fill="none" stroke="{t["magenta"]}" stroke-width="{h/540:.1f}" opacity=".55"/>')
    defs = (d1 + d2 + d3 + vd + _glow("gl", 3 * h / 1080) + _glow("gb", 40 * h / 1080) + _glow("gs", 9 * h / 1080) +
            f'<radialGradient id="bgp" cx="{cx/w:.2f}" cy="{cy/h:.2f}" r=".6"><stop offset="0" stop-color="{_mix(t["bg-2"], t["purple"], .45)}"/>'
            f'<stop offset=".45" stop-color="{t["bg-1"]}"/><stop offset="1" stop-color="{t["bg-0"]}"/></radialGradient>'
            f'<radialGradient id="pl" cx=".32" cy=".3" r=".85"><stop offset="0" stop-color="{_mix(t["purple"], t["fg-0"], .15)}"/>'
            f'<stop offset=".4" stop-color="{_mix(t["purple-dim"], t["bg-2"], .35)}"/><stop offset="1" stop-color="{t["bg-0"]}"/></radialGradient>'
            f'<linearGradient id="rg" x1="0" x2="1"><stop offset="0" stop-color="{t["magenta"]}" stop-opacity=".05"/>'
            f'<stop offset=".3" stop-color="{t["magenta"]}" stop-opacity=".45"/><stop offset=".7" stop-color="{t["purple"]}" stop-opacity=".5"/>'
            f'<stop offset="1" stop-color="{t["cyan"]}" stop-opacity=".08"/></linearGradient>'
            f'<clipPath id="ub"><rect x="{-rx*1.2:.0f}" y="{-ry*2:.0f}" width="{rx*2.4:.0f}" height="{ry*2:.0f}"/></clipPath>'
            f'<clipPath id="lb"><rect x="{-rx*1.2:.0f}" y="0" width="{rx*2.4:.0f}" height="{ry*2:.0f}"/></clipPath>'
            f'<clipPath id="pc"><circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R:.0f}"/></clipPath>'
            f'<linearGradient id="term" x1="0" y1="0" x2="1" y2="1"><stop offset=".35" stop-color="{t["bg-0"]}" stop-opacity="0"/>'
            f'<stop offset=".85" stop-color="{t["bg-0"]}" stop-opacity=".9"/></linearGradient>')
    body = (f'<rect width="{w}" height="{h}" fill="url(#bgp)"/>{b1}{b2}{b3}{stars}{"".join(lines)}'
            f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R*1.25:.0f}" fill="{t["purple"]}" opacity=".35" filter="url(#gb)"/>'
            f'<g transform="translate({cx:.0f} {cy:.0f}) rotate(-12)"><g clip-path="url(#ub)">{ring()}</g></g>'
            f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R:.0f}" fill="url(#pl)"/>'
            f'<g clip-path="url(#pc)"><circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R:.0f}" fill="url(#term)"/>'
            f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R-1.5:.0f}" fill="none" stroke="{t["cyan"]}" stroke-width="{R*.045:.1f}" opacity=".55" filter="url(#gs)" '
            f'transform="translate({-R*.05:.0f} {-R*.05:.0f})"/></g>'
            f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R:.0f}" fill="none" stroke="{t["purple"]}" stroke-width="{h/700:.1f}" opacity=".8"/>'
            f'<g transform="translate({cx:.0f} {cy:.0f}) rotate(-12)"><g clip-path="url(#lb)">{ring()}</g></g>'
            f'<circle cx="{w*.28:.0f}" cy="{h*.7:.0f}" r="{R*.16:.0f}" fill="url(#pl)"/>'
            f'<circle cx="{w*.28:.0f}" cy="{h*.7:.0f}" r="{R*.16:.0f}" fill="none" stroke="{t["cyan"]}" stroke-width="{h/900:.1f}" opacity=".5"/>{vb}')
    return _head(w, h, defs) + body + "</svg>"


def horizon(w, h, t, seed=5):
    rnd = random.Random(seed)
    hy = h * .62
    vd, vb = _vignette(w, h, t["bg-0"])
    stars, _ = _stars(rnd, w, h, int(w * h / 9000), t, ymax=.55)
    sx, sy, sr = w * .5, hy - h * .02, h * .24
    bars = "".join(f'<rect x="0" y="{sy + sr*(.18+.8*(k/9)**1.1):.0f}" width="{w}" height="{sr*(.012+.075*(k/9)**1.6):.1f}" fill="#000"/>' for k in range(10))
    def ridge(base, amp, n, col, op):
        pts, y = [], base
        for i in range(n + 1):
            y = max(base - amp, min(base, y + rnd.uniform(-amp * .28, amp * .28)))
            pts.append((w * i / n, y))
        d = "M0 %d " % hy + " ".join(f"L{x:.0f} {y:.0f}" for x, y in pts) + f" L{w} {hy:.0f}Z"
        line = "M" + " L".join(f"{x:.0f} {y:.0f}" for x, y in pts)
        return (f'<path d="{d}" fill="{t["bg-0"]}" opacity=".96"/>'
                f'<path d="{line}" fill="none" stroke="{col}" stroke-width="{h/540:.1f}" opacity="{op}" filter="url(#gl)"/>'
                f'<path d="{line}" fill="none" stroke="{col}" stroke-width="{h/900:.1f}" opacity="{min(1,op+.3)}"/>')
    grid = []
    for i in range(-30, 31):
        grid.append(f'M{w/2 + i*w*.018:.0f} {hy:.0f}L{w/2 + i*w*.20:.0f} {h}')
    for k in range(1, 16):
        y = hy + (h - hy) * (k / 15) ** 2.1
        grid.append(f'M0 {y:.0f}H{w}')
    defs = (vd + _glow("gl", 4 * h / 1080) + _glow("gb", 50 * h / 1080) +
            f'<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["bg-0"]}"/>'
            f'<stop offset=".7" stop-color="{_mix(t["bg-1"], t["purple-dim"], .45)}"/><stop offset="1" stop-color="{_mix(t["purple"], t["magenta"], .5)}"/></linearGradient>'
            f'<linearGradient id="sun" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["yellow"]}"/><stop offset=".45" stop-color="{t["magenta"]}"/>'
            f'<stop offset="1" stop-color="{t["purple"]}"/></linearGradient>'
            f'<mask id="sm"><rect width="{w}" height="{h}" fill="#fff"/>{bars}</mask>'
            f'<linearGradient id="gr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["purple"]}" stop-opacity=".95"/>'
            f'<stop offset="1" stop-color="{t["purple-dim"]}" stop-opacity=".25"/></linearGradient>'
            f'<linearGradient id="gd" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{_mix(t["bg-2"], t["purple-dim"], .4)}"/><stop offset="1" stop-color="{t["bg-0"]}"/></linearGradient>')
    body = (f'<rect width="{w}" height="{h}" fill="url(#sky)"/>{stars}'
            f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{sr*1.35:.0f}" fill="{t["magenta"]}" opacity=".45" filter="url(#gb)"/>'
            f'<circle cx="{sx:.0f}" cy="{sy:.0f}" r="{sr:.0f}" fill="url(#sun)" mask="url(#sm)"/>'
            f'{ridge(hy - h*.02, h*.17, 26, t["magenta"], .55)}{ridge(hy, h*.09, 40, t["cyan"], .4)}'
            f'<rect x="0" y="{hy:.0f}" width="{w}" height="{h-hy:.0f}" fill="url(#gd)"/>'
            f'<path d="{" ".join(grid)}" stroke="url(#gr)" stroke-width="{h/450:.1f}" fill="none" filter="url(#gl)"/>'
            f'<path d="{" ".join(grid)}" stroke="url(#gr)" stroke-width="{h/900:.1f}" fill="none"/>'
            f'<rect x="0" y="{hy-2:.0f}" width="{w}" height="{h/360:.1f}" fill="{t["fg-0"]}" opacity=".7" filter="url(#gl)"/>{vb}')
    return _head(w, h, defs) + body + "</svg>"


def circuit(w, h, t, seed=9):
    rnd = random.Random(seed)
    g = h / 36
    cols, rows = int(w / g), int(h / g)
    traces, nodes = [], []
    dirs = [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    for _ in range(int(w * h / 26000)):
        x, y = rnd.randrange(cols), rnd.randrange(rows)
        d = rnd.choice(dirs[:4])
        pts = [(x, y)]
        for _ in range(rnd.randint(6, 16)):
            for _ in range(rnd.randint(2, 6)):
                x += d[0]; y += d[1]
                pts.append((x, y))
            nd = rnd.choice([dirs[(dirs.index(d) + k) % 8] for k in (-1, 1)] if rnd.random() < .6 else [d])
            d = nd
        traces.append(pts)
        nodes.append(pts[0]); nodes.append(pts[-1])
    P = lambda p: f"{p[0]*g:.0f} {p[1]*g:.0f}"
    paths = ["M" + " L".join(P(p) for p in pts) for pts in traces]
    pulses = []
    for i, d in enumerate(rnd.sample(paths, max(1, len(paths) // 6))):
        c = (t["cyan"], t["magenta"], t["purple"])[i % 3]
        L = rnd.uniform(40, 110) * h / 1080
        pulses.append(f'<path d="{d}" stroke="{c}" stroke-width="{h/320:.1f}" fill="none" stroke-linecap="round" stroke-dasharray="{L:.0f} {L*rnd.uniform(5,12):.0f}" '
                      f'stroke-dashoffset="{-rnd.uniform(0,600):.0f}" filter="url(#gl)"/>'
                      f'<path d="{d}" stroke="{c}" stroke-width="{h/700:.1f}" fill="none" stroke-linecap="round" stroke-dasharray="{L:.0f} {L*8:.0f}" stroke-dashoffset="{-rnd.uniform(0,600):.0f}"/>')
    ncirc = "".join(f'<circle cx="{n[0]*g:.0f}" cy="{n[1]*g:.0f}" r="{g*.16:.1f}" fill="{t["bg-0"]}" stroke="{t["purple"]}" stroke-width="{h/540:.1f}" opacity=".85"/>' for n in nodes)
    cw, ch = w * .2, h * .28
    chx, chy = w * .56, h * .36
    pins = "".join(f'<rect x="{chx - g*.7:.0f}" y="{chy + k*ch/10 + ch/40:.0f}" width="{g*.7:.0f}" height="{ch/22:.0f}" fill="{t["purple"]}" opacity=".7"/>'
                   f'<rect x="{chx + cw:.0f}" y="{chy + k*ch/10 + ch/40:.0f}" width="{g*.7:.0f}" height="{ch/22:.0f}" fill="{t["purple"]}" opacity=".7"/>' for k in range(10))
    vd, vb = _vignette(w, h, t["bg-0"])
    defs = (vd + _glow("gl", 4 * h / 1080) + _glow("gb", 60 * h / 1080) +
            f'<radialGradient id="bgc" cx=".56" cy=".5" r=".7"><stop offset="0" stop-color="{_mix(t["bg-2"], t["purple-dim"], .3)}"/><stop offset="1" stop-color="{t["bg-0"]}"/></radialGradient>')
    body = (f'<rect width="{w}" height="{h}" fill="url(#bgc)"/>'
            f'<path d="{" ".join(paths)}" stroke="{t["purple"]}" stroke-width="{h/420:.1f}" fill="none" opacity=".4" stroke-linejoin="round"/>'
            f'{ncirc}{"".join(pulses)}'
            f'<rect x="{chx - cw*.1:.0f}" y="{chy - ch*.1:.0f}" width="{cw*1.2:.0f}" height="{ch*1.2:.0f}" rx="{g*.5:.0f}" fill="{t["purple"]}" opacity=".25" filter="url(#gb)"/>'
            f'{pins}<rect x="{chx:.0f}" y="{chy:.0f}" width="{cw:.0f}" height="{ch:.0f}" rx="{g*.35:.0f}" fill="{t["bg-1"]}" stroke="{t["purple"]}" stroke-width="{h/360:.1f}"/>'
            f'<rect x="{chx+cw*.12:.0f}" y="{chy+ch*.15:.0f}" width="{cw*.76:.0f}" height="{ch*.7:.0f}" rx="{g*.25:.0f}" fill="none" stroke="{t["magenta"]}" stroke-width="{h/700:.1f}" opacity=".7"/>'
            f'<text x="{chx+cw/2:.0f}" y="{chy+ch*.58:.0f}" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="{ch*.28:.0f}" fill="{t["fg-0"]}" opacity=".9">&gt;_</text>{vb}')
    return _head(w, h, defs) + body + "</svg>"


SNIPPET = [
    [("def", "purple"), (" render", "cyan"), ("(template):", "fg-1")],
    [("    for", "purple"), (" name, hex_ ", "fg-0"), ("in", "purple"), (" PALETTE:", "fg-0")],
    [("        template ", "fg-0"), ("=", "magenta"), (" template.replace(", "fg-1")],
    [("            f", "magenta"), ('"${name}"', "green"), (", hex_)", "fg-1")],
    [("    return", "purple"), (" template", "fg-0")],
    [("", "fg-0")],
    [("# nebulix: one palette, whole system", "fg-2")],
    [("apply", "cyan"), ("(", "fg-1"), ("accent", "yellow"), ("=", "magenta"), ('"purple"', "green"), (")", "fg-1")],
]


def code(w, h, t, seed=3):
    rnd = random.Random(seed)
    fs = h / 54
    cw = fs * .6
    ncol = int(w / (cw * 2.2))
    glyphs = "01{}[]<>/\\=+-*;:#$%&ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶｷﾑﾕﾗｾﾈｽﾀﾇﾍ"
    layers = []
    for depth, (blur, op) in enumerate([("b2", .35), ("b1", .55), (None, .9)]):
        cols = []
        for i in range(ncol // (3 - depth) + 2):
            x = rnd.uniform(0, w)
            n = rnd.randint(8, 26)
            y0 = rnd.uniform(-h * .1, h * .9)
            size = fs * (.8 + depth * .22)
            c = rnd.choice([t["purple"], t["purple"], t["magenta"], t["cyan"]])
            sp = "".join(f'<tspan x="{x:.0f}" y="{y0 + k*size*1.25:.0f}" fill-opacity="{max(.04, 1 - (n-1-k)/n*1.15) if k < n-1 else 1:.2f}"'
                         f'{" fill=\"" + t["fg-0"] + "\"" if k == n-1 else ""}>{esc(rnd.choice(glyphs))}</tspan>' for k in range(n))
            cols.append(f'<text font-family="JetBrains Mono, monospace" font-size="{size:.1f}" fill="{c}">{sp}</text>')
        layers.append(f'<g opacity="{op}"{f" filter=\"url(#{blur})\"" if blur else ""}>{"".join(cols)}</g>')
    pw, ph = min(w * .36, fs * 28), fs * 1.9 * (len(SNIPPET) + 3)
    px, py = (w - pw) / 2, (h - ph) / 2
    lines = []
    for i, ln in enumerate(SNIPPET):
        sp = "".join(f'<tspan fill="{t[c]}">{s.replace("&", "&amp;").replace("<", "&lt;")}</tspan>' for s, c in ln)
        lines.append(f'<text xml:space="preserve" x="{px+fs*1.2:.0f}" y="{py+fs*3.3+i*fs*1.7:.0f}" font-family="JetBrains Mono, monospace" font-size="{fs*1.05:.1f}">{sp}</text>')
    vd, vb = _vignette(w, h, t["bg-0"])
    defs = (vd + _glow("b1", 1.3 * h / 1080) + _glow("b2", 3 * h / 1080) + _glow("gb", 40 * h / 1080))
    body = (f'<rect width="{w}" height="{h}" fill="{t["bg-0"]}"/>{"".join(layers)}'
            f'<rect x="{px:.0f}" y="{py:.0f}" width="{pw:.0f}" height="{ph:.0f}" rx="{fs*.9:.0f}" fill="{t["purple"]}" opacity=".3" filter="url(#gb)"/>'
            f'<rect x="{px:.0f}" y="{py:.0f}" width="{pw:.0f}" height="{ph:.0f}" rx="{fs*.9:.0f}" fill="{t["bg-1"]}" fill-opacity=".93" stroke="{t["border"]}" stroke-width="{h/700:.1f}"/>'
            f'<circle cx="{px+fs*1.3:.0f}" cy="{py+fs*1.2:.0f}" r="{fs*.28:.1f}" fill="{t["red"]}"/><circle cx="{px+fs*2.2:.0f}" cy="{py+fs*1.2:.0f}" r="{fs*.28:.1f}" fill="{t["yellow"]}"/>'
            f'<circle cx="{px+fs*3.1:.0f}" cy="{py+fs*1.2:.0f}" r="{fs*.28:.1f}" fill="{t["green"]}"/>{"".join(lines)}{vb}')
    return _head(w, h, defs) + body + "</svg>"


GEN = {"orbit": orbit, "horizon": horizon, "circuit": circuit, "code": code}


def svg(name, w, h, tokens):
    return GEN[name](w, h, tokens)


def rasterize(svg_text, out_png):
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_png.with_suffix(".svg")
    tmp.write_text(svg_text)
    try:
        GdkPixbuf.Pixbuf.new_from_file(str(tmp)).savev(str(out_png), "png", [], [])
    finally:
        tmp.unlink(missing_ok=True)
