"""Minimal BPMN 2.0 SVG renderer for report figures."""

FONT = "Helvetica, Arial, sans-serif"
FS = 1.35  # global font scale for print readability

def wrap_text(text, max_chars):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

class BPMN:
    def __init__(self, width, height):
        self.w, self.h = width, height
        self.body = []

    # ---------- containers ----------
    def pool(self, x, y, w, h, label, band=30):
        self.body.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" '
            f'stroke="#333" stroke-width="1.6"/>')
        self.body.append(
            f'<line x1="{x+band}" y1="{y}" x2="{x+band}" y2="{y+h}" '
            f'stroke="#333" stroke-width="1.2"/>')
        cx, cy = x + band / 2, y + h / 2
        self.body.append(
            f'<text x="{cx}" y="{cy}" font-family="{FONT}" font-size="{14*FS:.1f}" '
            f'font-weight="bold" text-anchor="middle" '
            f'transform="rotate(-90 {cx} {cy})">{label}</text>')

    def blackbox_pool(self, x, y, w, h, label):
        self.body.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#f5f5f5" '
            f'stroke="#333" stroke-width="1.6"/>')
        self.body.append(
            f'<text x="{x+w/2}" y="{y+h/2+5}" font-family="{FONT}" font-size="{14*FS:.1f}" '
            f'font-weight="bold" text-anchor="middle">{label}</text>')

    def lane(self, x, y, w, h, label, band=28):
        self.body.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" '
            f'stroke="#333" stroke-width="1"/>')
        self.body.append(
            f'<line x1="{x+band}" y1="{y}" x2="{x+band}" y2="{y+h}" '
            f'stroke="#999" stroke-width="0.8"/>')
        cx, cy = x + band / 2, y + h / 2
        self.body.append(
            f'<text x="{cx}" y="{cy}" font-family="{FONT}" font-size="{12.5*FS:.1f}" '
            f'text-anchor="middle" transform="rotate(-90 {cx} {cy})">{label}</text>')

    # ---------- icons ----------
    def _icon(self, kind, x, y, s=17):
        """Draw small marker icon with top-left at (x, y); s = size."""
        p = []
        if kind == "user":
            p.append(f'<circle cx="{x+s/2}" cy="{y+s*0.32}" r="{s*0.22}" '
                     f'fill="none" stroke="#555" stroke-width="1.2"/>')
            p.append(f'<path d="M {x+s*0.12} {y+s} Q {x+s/2} {y+s*0.5} {x+s*0.88} {y+s}" '
                     f'fill="none" stroke="#555" stroke-width="1.2"/>')
        elif kind == "gear":
            cx, cy, r = x + s/2, y + s/2, s*0.32
            p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#555" stroke-width="1.2"/>')
            import math
            for i in range(8):
                a = i * math.pi / 4
                x1, y1 = cx + r*math.cos(a), cy + r*math.sin(a)
                x2, y2 = cx + (r+s*0.18)*math.cos(a), cy + (r+s*0.18)*math.sin(a)
                p.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                         f'stroke="#555" stroke-width="1.2"/>')
        elif kind == "envelope":
            p.append(f'<rect x="{x}" y="{y+s*0.15}" width="{s}" height="{s*0.7}" '
                     f'fill="none" stroke="#555" stroke-width="1.2"/>')
            p.append(f'<path d="M {x} {y+s*0.15} L {x+s/2} {y+s*0.55} L {x+s} {y+s*0.15}" '
                     f'fill="none" stroke="#555" stroke-width="1.2"/>')
        elif kind == "table":
            p.append(f'<rect x="{x}" y="{y+s*0.1}" width="{s}" height="{s*0.8}" '
                     f'fill="none" stroke="#555" stroke-width="1.2"/>')
            p.append(f'<line x1="{x}" y1="{y+s*0.37}" x2="{x+s}" y2="{y+s*0.37}" stroke="#555" stroke-width="1"/>')
            p.append(f'<line x1="{x+s*0.33}" y1="{y+s*0.1}" x2="{x+s*0.33}" y2="{y+s*0.9}" stroke="#555" stroke-width="1"/>')
        self.body.extend(p)

    # ---------- nodes ----------
    def task(self, cx, cy, text, icon=None, w=150, h=82, fill="#ffffff"):
        x, y = cx - w/2, cy - h/2
        self.body.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" ry="10" '
            f'fill="{fill}" stroke="#333" stroke-width="1.6"/>')
        if icon:
            self._icon(icon, x + 6, y + 5)
        lines = wrap_text(text, 17)
        n = len(lines)
        y0 = cy - (n - 1) * 9
        for i, ln in enumerate(lines):
            self.body.append(
                f'<text x="{cx}" y="{y0 + i*18 + 5}" font-family="{FONT}" '
                f'font-size="{12.5*FS:.1f}" text-anchor="middle">{ln}</text>')
        return (cx, cy, w, h)

    def gateway(self, cx, cy, label=None, kind="xor", lpos="top", r=26):
        pts = f"{cx},{cy-r} {cx+r},{cy} {cx},{cy+r} {cx-r},{cy}"
        self.body.append(
            f'<polygon points="{pts}" fill="#fff" stroke="#333" stroke-width="1.6"/>')
        if kind == "xor":
            d = r * 0.38
            self.body.append(f'<line x1="{cx-d}" y1="{cy-d}" x2="{cx+d}" y2="{cy+d}" stroke="#333" stroke-width="2.2"/>')
            self.body.append(f'<line x1="{cx-d}" y1="{cy+d}" x2="{cx+d}" y2="{cy-d}" stroke="#333" stroke-width="2.2"/>')
        elif kind == "and":
            d = r * 0.5
            self.body.append(f'<line x1="{cx}" y1="{cy-d}" x2="{cx}" y2="{cy+d}" stroke="#333" stroke-width="2.4"/>')
            self.body.append(f'<line x1="{cx-d}" y1="{cy}" x2="{cx+d}" y2="{cy}" stroke="#333" stroke-width="2.4"/>')
        if label:
            self._node_label(cx, cy, r, label, lpos)
        return (cx, cy, 2*r, 2*r)

    def event(self, cx, cy, kind="start", icon=None, label=None, lpos="bottom", r=18):
        sw = 3.2 if kind == "end" else 1.6
        self.body.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff" stroke="#333" stroke-width="{sw}"/>')
        if kind == "timer":
            self.body.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r-3.5}" fill="none" stroke="#333" stroke-width="1.2"/>')
            rr = r - 7
            self.body.append(
                f'<circle cx="{cx}" cy="{cy}" r="{rr}" fill="none" stroke="#333" stroke-width="1.2"/>')
            self.body.append(f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy-rr*0.7}" stroke="#333" stroke-width="1.3"/>')
            self.body.append(f'<line x1="{cx}" y1="{cy}" x2="{cx+rr*0.55}" y2="{cy+rr*0.25}" stroke="#333" stroke-width="1.3"/>')
        if icon == "message":
            s = r * 0.95
            self._icon("envelope", cx - s/2, cy - s/2, s)
        if label:
            self._node_label(cx, cy, r, label, lpos)
        return (cx, cy, 2*r, 2*r)

    def _node_label(self, cx, cy, r, label, lpos):
        lines = wrap_text(label, 16)
        if lpos == "bottom":
            y0 = cy + r + 17
        elif lpos == "top":
            y0 = cy - r - 8 - (len(lines)-1)*17
        else:
            y0 = cy + r + 17
        for i, ln in enumerate(lines):
            self.body.append(
                f'<text x="{cx}" y="{y0 + i*17}" font-family="{FONT}" '
                f'font-size="{11.5*FS:.1f}" text-anchor="middle" fill="#111">{ln}</text>')

    # ---------- flows ----------
    def flow(self, points, label=None, loffset=(0, -6), msg=False):
        pstr = " ".join(f"{x},{y}" for x, y in points)
        if msg:
            self.body.append(
                f'<polyline points="{pstr}" fill="none" stroke="#555" stroke-width="1.4" '
                f'stroke-dasharray="6,5" marker-end="url(#openarrow)"/>')
            x0, y0 = points[0]
            self.body.append(f'<circle cx="{x0}" cy="{y0}" r="4" fill="#fff" stroke="#555" stroke-width="1.3"/>')
        else:
            self.body.append(
                f'<polyline points="{pstr}" fill="none" stroke="#333" stroke-width="1.5" '
                f'marker-end="url(#arrow)"/>')
        if label:
            lx = (points[0][0] + points[1][0]) / 2 + loffset[0]
            ly = (points[0][1] + points[1][1]) / 2 + loffset[1]
            self.body.append(
                f'<text x="{lx}" y="{ly}" font-family="{FONT}" font-size="{11.5*FS:.1f}" '
                f'font-style="italic" text-anchor="middle" fill="#111">{label}</text>')

    def annotation(self, x, y, text, w=180):
        lines = wrap_text(text, 30)
        h = len(lines) * 14 + 10
        self.body.append(
            f'<path d="M {x+12} {y} L {x} {y} L {x} {y+h} L {x+12} {y+h}" '
            f'fill="none" stroke="#777" stroke-width="1.2"/>')
        for i, ln in enumerate(lines):
            self.body.append(
                f'<text x="{x+6}" y="{y+16+i*14}" font-family="{FONT}" font-size="11" '
                f'fill="#333">{ln}</text>')

    def title(self, x, y, text):
        self.body.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{17*FS:.1f}" '
            f'font-weight="bold">{text}</text>')

    def save(self, path):
        svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}">',
            '<defs>',
            '<marker id="arrow" markerWidth="11" markerHeight="9" refX="10" refY="4.5" orient="auto">',
            '<polygon points="0 0, 11 4.5, 0 9" fill="#333"/></marker>',
            '<marker id="openarrow" markerWidth="12" markerHeight="10" refX="11" refY="5" orient="auto">',
            '<polyline points="1 1, 11 5, 1 9" fill="none" stroke="#555" stroke-width="1.3"/></marker>',
            '</defs>',
            f'<rect x="0" y="0" width="{self.w}" height="{self.h}" fill="#ffffff"/>',
        ]
        svg.extend(self.body)
        svg.append('</svg>')
        with open(path, "w") as f:
            f.write("\n".join(svg))
