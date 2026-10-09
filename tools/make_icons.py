"""Generate the SVG icons in Icons/. Run with plain python3: python3 tools/make_icons.py"""

import math
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Icons")
SERIES = ["60", "62", "63", "68", "69", "MR"]


def bearing_svg(label=None, balls=8, badge="#1f6feb"):
    c = 32
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">',
        '<defs><radialGradient id="g" cx="40%" cy="35%" r="70%">'
        '<stop offset="0" stop-color="#f4f6fa"/><stop offset="1" stop-color="#8a93a3"/></radialGradient></defs>',
        f'<circle cx="{c}" cy="{c}" r="29" fill="url(#g)" stroke="#3b4250" stroke-width="2"/>',
        f'<circle cx="{c}" cy="{c}" r="21" fill="#2c3340" stroke="#3b4250" stroke-width="1.5"/>',
        f'<circle cx="{c}" cy="{c}" r="15" fill="url(#g)" stroke="#3b4250" stroke-width="1.5"/>',
        f'<circle cx="{c}" cy="{c}" r="8" fill="#ffffff" stroke="#3b4250" stroke-width="2"/>',
    ]
    for k in range(balls):
        a = 2 * math.pi * k / balls
        x, y = c + 18 * math.cos(a), c + 18 * math.sin(a)
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.2" fill="#e6e9ef" stroke="#3b4250" stroke-width="0.8"/>')
    if label:
        parts.append(f'<rect x="18" y="44" width="46" height="20" rx="4" fill="{badge}"/>')
        size = 15 if len(label) <= 2 else 12
        parts.append(f'<text x="41" y="59" font-family="Arial,Helvetica,sans-serif" font-size="{size}" '
                     f'font-weight="bold" fill="#ffffff" text-anchor="middle">{label}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def search_svg():
    """Small bearing under a magnifying glass."""
    body = bearing_svg(balls=7).split("\n")
    inner = "\n".join(l for l in body[1:-2])  # drop <svg>, </svg>
    return "\n".join([
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">',
        '<g transform="translate(2 2) scale(0.62)">', inner, "</g>",
        '<circle cx="40" cy="40" r="13" fill="#ffffff" fill-opacity="0.35" stroke="#1f6feb" stroke-width="5"/>',
        '<line x1="49.5" y1="49.5" x2="61" y2="61" stroke="#1f6feb" stroke-width="7" stroke-linecap="round"/>',
        "</svg>",
    ]) + "\n"


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "BearingsWB.svg"), "w") as f:
        f.write(bearing_svg())
    for s in SERIES:
        with open(os.path.join(OUT, f"Bearing_{s}.svg"), "w") as f:
            f.write(bearing_svg(s))
    with open(os.path.join(OUT, "PrintableBearing.svg"), "w") as f:
        f.write(bearing_svg("3D", balls=10, badge="#e8710a"))
    with open(os.path.join(OUT, "BearingSearch.svg"), "w") as f:
        f.write(search_svg())
    print("wrote", len(SERIES) + 3, "icons to", OUT)
