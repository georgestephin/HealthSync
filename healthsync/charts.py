"""Small server-side SVG chart helpers. No JavaScript library is needed, so charts work offline."""
from math import ceil
from markupsafe import Markup, escape


def pastel(color, mix=0.5):
    """Blend a #rrggbb colour with white, for soft chart fills."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(v + (255 - v) * mix) for v in (r, g, b))


def _empty():
    return Markup('<p class="empty">No data yet.</p>')


def _short(text, n):
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


def _svg(inner, w, h, label, cls="chart"):
    return Markup(f'<svg class="{cls}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">{inner}</svg>')


def _nice_max(top):
    """A tidy axis maximum with at most four gridline steps."""
    top = max(top, 1)
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if top / step <= 4:
            return step, int(ceil(top / step) * step)
    step = int(ceil(top / 4))
    return step, step * 4


def hbar(items, label, cycle=False, colors=None):
    """Horizontal bars. items = [(label, value)]; colors = optional list of CSS colours, one per bar."""
    if not items or not any(v for _, v in items):
        return _empty()
    W, ROW, LAB, RIGHT = 480, 30, 150, 40
    mx, parts = max(v for _, v in items), []
    for i, (lab, val) in enumerate(items):
        y, w = i * ROW, (W - LAB - RIGHT) * val / mx
        cls = f"c{i % 6}" if cycle else "c0"
        style = f' style="--c:{colors[i]}"' if colors else ""
        parts.append(f'<text class="ct" x="0" y="{y + 19}">{escape(_short(lab, 22))}</text>'
                     f'<rect class="cb {cls}"{style} x="{LAB}" y="{y + 6}" width="{w:.1f}" height="18" rx="4"><title>{escape(lab)}: {val}</title></rect>'
                     f'<text class="cv" x="{LAB + w + 8:.1f}" y="{y + 19}">{val}</text>')
    return _svg("".join(parts), W, len(items) * ROW, label)


def progress(items, label):
    """Bars against a full track. items = [(label, value, total)]; turns amber then red when nearly full."""
    if not items:
        return _empty()
    W, ROW, LAB, RIGHT = 480, 34, 130, 60
    full, parts = W - LAB - RIGHT, []
    for i, (lab, val, total) in enumerate(items):
        pct, y = (val / total if total else 0), i * ROW
        cls = "c3" if pct >= 0.9 else ("c2" if pct >= 0.75 else "c0")
        parts.append(f'<text class="ct" x="0" y="{y + 21}">{escape(_short(lab, 18))}</text>'
                     f'<rect class="track" x="{LAB}" y="{y + 8}" width="{full}" height="16" rx="8"/>'
                     f'<rect class="cb {cls}" x="{LAB}" y="{y + 8}" width="{full * pct:.1f}" height="16" rx="8"><title>{escape(lab)}: {val} of {total} beds occupied</title></rect>'
                     f'<text class="cv" x="{LAB + full + 10}" y="{y + 21}">{round(pct * 100)}%</text>')
    return _svg("".join(parts), W, len(items) * ROW, label)


def columns(items, label, w=480, h=220, classes=None):
    """Vertical columns with gridlines. items = [(label, value)]; classes = optional colour class per bar."""
    if not items or not any(v for _, v in items):
        return _empty()
    PL, PR, PT, PB = 34, 8, 16, 28
    step, ymax = _nice_max(max(v for _, v in items))
    pw, ph, parts = w - PL - PR, h - PT - PB, []
    for k in range(ymax // step + 1):
        v = k * step
        y = PT + ph - ph * v / ymax
        parts.append(f'<line class="grid" x1="{PL}" x2="{w - PR}" y1="{y:.1f}" y2="{y:.1f}"/><text class="cx" x="{PL - 6}" y="{y + 4:.1f}" text-anchor="end">{v}</text>')
    slot = pw / len(items)
    bw = min(slot * 0.56, 56)
    for i, (lab, val) in enumerate(items):
        x, bh = PL + slot * i + (slot - bw) / 2, ph * val / ymax
        parts.append(f'<rect class="cb {classes[i] if classes else "c0"}" x="{x:.1f}" y="{PT + ph - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="4"><title>{escape(lab)}: {val}</title></rect>'
                     f'<text class="cv" x="{x + bw / 2:.1f}" y="{PT + ph - bh - 5:.1f}" text-anchor="middle">{val}</text>'
                     f'<text class="cx" x="{x + bw / 2:.1f}" y="{h - 8}" text-anchor="middle">{escape(lab)}</text>')
    return _svg("".join(parts), w, h, label)


def donut(items, label, classes=None):
    """Donut chart. Returns {'svg': ..., 'legend': [...]} so the template can draw the legend as HTML."""
    items = [(l, v) for l, v in items if v]
    total = sum(v for _, v in items)
    if not total:
        return dict(svg=_empty(), legend=[])
    R, cum, parts, legend = 15.9155, 0.0, [], []
    for i, (lab, val) in enumerate(items):
        pct = val * 100 / total
        cls = f"c{(classes or {}).get(lab, i % 6)}"
        parts.append(f'<circle class="seg {cls}" cx="21" cy="21" r="{R}" stroke-width="6" stroke-dasharray="{pct:.3f} {100 - pct:.3f}" '
                     f'stroke-dashoffset="{25 - cum:.3f}"><title>{escape(lab)}: {val}</title></circle>')
        legend.append(dict(label=lab, value=val, pct=round(pct), cls=cls))
        cum += pct
    parts.append(f'<text class="dc" x="21" y="22.6" text-anchor="middle">{total}</text><text class="dl" x="21" y="27" text-anchor="middle">total</text>')
    return dict(svg=_svg("".join(parts), 42, 42, label, "chart donut"), legend=legend)


def stacked(items, series, label):
    """Horizontal stacked bars. items = [(label, [values...])], series = [(name, css_class)]."""
    items = [(l, vs) for l, vs in items if sum(vs)]
    if not items:
        return _empty()
    W, ROW, LAB, RIGHT = 480, 32, 170, 40
    mx, parts = max(sum(vs) for _, vs in items), []
    for i, (lab, vs) in enumerate(items):
        y, x = i * ROW, float(LAB)
        parts.append(f'<text class="ct" x="0" y="{y + 20}">{escape(_short(lab, 24))}</text>')
        for (name, cls), v in zip(series, vs):
            if v:
                w = (W - LAB - RIGHT) * v / mx
                parts.append(f'<rect class="cb {cls}" x="{x:.1f}" y="{y + 6}" width="{w:.1f}" height="20"><title>{escape(lab)}, {escape(name)}: {v}</title></rect>')
                x += w
        parts.append(f'<text class="cv" x="{x + 8:.1f}" y="{y + 20}">{sum(vs)}</text>')
    return _svg("".join(parts), W, len(items) * ROW, label)
