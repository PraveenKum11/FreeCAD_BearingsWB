# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate the SVG icons in Icons/. Run with plain python3: python3 tools/make_icons.py"""

import math
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Icons")
SERIES = ["60", "62", "63", "68", "69", "MR", "R", "72", "73"]


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
        parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.2" fill="#e6e9ef" stroke="#3b4250" stroke-width="0.8"/>'
        )
    if label:
        parts.append(f'<rect x="18" y="44" width="46" height="20" rx="4" fill="{badge}"/>')
        size = 15 if len(label) <= 2 else 12
        parts.append(
            f'<text x="41" y="59" font-family="Arial,Helvetica,sans-serif" font-size="{size}" '
            f'font-weight="bold" fill="#ffffff" text-anchor="middle">{label}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def linear_svg(label="LM", badge="#1f6feb"):
    """Linear ball bushing seen from the side: a sleeve with grooves on a shaft."""
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">',
        '<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#f4f6fa"/><stop offset="0.5" stop-color="#c3c9d3"/>'
        '<stop offset="1" stop-color="#8a93a3"/></linearGradient></defs>',
        # shaft
        '<rect x="2" y="25" width="60" height="12" rx="2" fill="url(#s)" stroke="#3b4250" stroke-width="1.5"/>',
        # sleeve
        '<rect x="12" y="12" width="40" height="38" rx="3" fill="url(#s)" stroke="#3b4250" stroke-width="2"/>',
        # retaining ring grooves
        '<rect x="18" y="12" width="3" height="38" fill="#5b6475"/>',
        '<rect x="43" y="12" width="3" height="38" fill="#5b6475"/>',
        # seals at both ends
        '<rect x="12" y="20" width="3" height="22" fill="#2c3340"/>',
        '<rect x="49" y="20" width="3" height="22" fill="#2c3340"/>',
    ]
    if label:
        parts.append(f'<rect x="18" y="44" width="46" height="20" rx="4" fill="{badge}"/>')
        parts.append(
            f'<text x="41" y="59" font-family="Arial,Helvetica,sans-serif" font-size="13" '
            f'font-weight="bold" fill="#ffffff" text-anchor="middle">{label}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def thrust_svg(label="511", badge="#1f6feb"):
    """Thrust ball bearing seen from the side: two washers with balls between them."""
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">',
        '<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#f4f6fa"/><stop offset="1" stop-color="#8a93a3"/></linearGradient></defs>',
        '<rect x="3" y="8" width="58" height="11" rx="2" fill="url(#s)" stroke="#3b4250" stroke-width="2"/>',
        '<rect x="3" y="33" width="58" height="11" rx="2" fill="url(#s)" stroke="#3b4250" stroke-width="2"/>',
        # the bore through both washers
        '<rect x="24" y="8" width="16" height="36" fill="#ffffff" stroke="#3b4250" stroke-width="1.5"/>',
    ]
    for x in (13.5, 50.5):
        parts.append(
            f'<circle cx="{x}" cy="26" r="7" fill="#e6e9ef" stroke="#3b4250" stroke-width="1.2"/>'
        )
    if label:
        parts.append(f'<rect x="18" y="44" width="46" height="20" rx="4" fill="{badge}"/>')
        parts.append(
            f'<text x="41" y="59" font-family="Arial,Helvetica,sans-serif" font-size="13" '
            f'font-weight="bold" fill="#ffffff" text-anchor="middle">{label}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def bom_svg():
    """A parts list with a small bearing: the bill of materials."""
    body = bearing_svg(balls=6).split("\n")
    inner = "\n".join(body[1:-2])  # drop <svg>, </svg>
    rows = "".join(
        f'<rect x="30" y="{y}" width="28" height="4" rx="2" fill="#3b4250"/>' for y in (12, 22, 32)
    )
    return (
        "\n".join(
            [
                '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">',
                '<rect x="4" y="4" width="56" height="56" rx="5" fill="#ffffff" stroke="#3b4250" stroke-width="2"/>',
                rows,
                '<g transform="translate(6 30) scale(0.42)">',
                inner,
                "</g>",
                '<rect x="30" y="44" width="20" height="4" rx="2" fill="#1f6feb"/>',
                "</svg>",
            ]
        )
        + "\n"
    )


def search_svg():
    """Small bearing under a magnifying glass."""
    body = bearing_svg(balls=7).split("\n")
    inner = "\n".join(body[1:-2])  # drop <svg>, </svg>
    return (
        "\n".join(
            [
                '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">',
                '<g transform="translate(2 2) scale(0.62)">',
                inner,
                "</g>",
                '<circle cx="40" cy="40" r="13" fill="#ffffff" fill-opacity="0.35" stroke="#1f6feb" stroke-width="5"/>',
                '<line x1="49.5" y1="49.5" x2="61" y2="61" stroke="#1f6feb" stroke-width="7" stroke-linecap="round"/>',
                "</svg>",
            ]
        )
        + "\n"
    )


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "BearingsWB.svg"), "w") as f:
        f.write(bearing_svg())
    for s in SERIES:
        with open(os.path.join(OUT, f"Bearing_{s}.svg"), "w") as f:
            f.write(bearing_svg(s))
    with open(os.path.join(OUT, "Bearing_LM.svg"), "w") as f:
        f.write(linear_svg())
    with open(os.path.join(OUT, "Bearing_511.svg"), "w") as f:
        f.write(thrust_svg())
    with open(os.path.join(OUT, "PrintableBearing.svg"), "w") as f:
        f.write(bearing_svg("3D", balls=10, badge="#e8710a"))
    with open(os.path.join(OUT, "BearingBOM.svg"), "w") as f:
        f.write(bom_svg())
    with open(os.path.join(OUT, "BearingSearch.svg"), "w") as f:
        f.write(search_svg())
    print("wrote", len(SERIES) + 6, "icons to", OUT)
