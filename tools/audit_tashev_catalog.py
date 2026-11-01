# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare the live supplier category with the checked-in coverage snapshot.

Run with ordinary Python: python tools/audit_tashev_catalog.py
Only the standard library is needed. This never changes dimension tables: a new
article needs its construction and dimensions checked before it is mapped.
"""

import csv
import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE = "https://tashev-galving.com"
ROOT_CATEGORY = "/cat/100116/lageri"
CATEGORIES = {
    "thrust": "/cat/201607/aksialni-sachmeni-lageri",
    "housing": "/cat/200812/lagerni-opori",
    "roller": "/cat/201606/rolkovi-lageri",
    "ball": "/cat/201604/sachmeni-lageri",
    "wheel": "/cat/300046/lageri-za-glavina-s-dalbok-kanal",
    "housed": "/cat/303477/lagerni-tela-s-lageri",
    "single_direction_thrust": "/cat/305046/aksialni-sachmeni-ednoredovi-lageri",
    "double_row_roller": "/cat/305132/dvuredovi-radialni-rolkovi-lageri",
    "needle": "/cat/311675/igleno-rolkovi-lageri",
    "tapered": "/cat/311676/konichni-rolkovi-lageri",
    "spherical": "/cat/311677/sferichni-rolkovi-lageri",
    "stud": "/cat/311678/rolkovi-lageri-s-shpilki",
    "single_row_ball": "/cat/311679/ednoredovi-sachmeni-lageri",
    "self_aligning_ball": "/cat/311680/dvuredovi-sachmeni-samonagazhdashti-se-lageri",
}


class ListingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.products = set()
        self.links = set()
        self.categories = set()
        self.anchor = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h2":
            self.in_title = "product-title" in attrs.get("class", "").split()
        if tag == "a" and attrs.get("href"):
            href = attrs["href"]
            self.anchor = href
            self.links.add(href)
            if self.in_title and href.startswith("/product/"):
                self.products.add(href.split("/")[2])
        # Category cards contain an image; global navigation/breadcrumb links do not.
        if tag == "img" and self.anchor.startswith("/cat/"):
            self.categories.add(self.anchor)

    def handle_endtag(self, tag):
        if tag == "h2":
            self.in_title = False
        if tag == "a":
            self.anchor = ""


def fetch(url):
    request = Request(url, headers={"User-Agent": "FreeCAD-BearingsWB catalog audit"})
    with urlopen(request, timeout=45) as response:
        parser = ListingParser()
        parser.feed(response.read().decode("utf-8"))
    if not parser.products and not parser.categories:
        raise ValueError(
            "No product/category cards in " + url + "; check for a changed page or access error"
        )
    return parser


def audit():
    path = Path(__file__).resolve().parent.parent / "BRData" / "tashev_catalog.csv"
    with path.open(encoding="utf-8", newline="") as f:
        snapshot = list(csv.DictReader(f))
    root = fetch(BASE + ROOT_CATEGORY)
    if not root.categories:
        raise ValueError("No subcategory menu found on the bearing category page")
    counts, live, pages = {}, set(root.products), 1
    category_names = {path: name for name, path in CATEGORIES.items()}
    pending_categories, visited_categories = set(root.categories), set()
    while pending_categories:
        path = min(pending_categories)
        pending_categories.remove(path)
        visited_categories.add(path)
        category = category_names.get(path, path)
        pending, visited, articles = {BASE + path + "?show=99"}, set(), set()
        while pending:
            url = min(pending)
            pending.remove(url)
            visited.add(url)
            parser = fetch(url)
            pending_categories.update(parser.categories - visited_categories)
            articles.update(parser.products)
            for link in parser.links:
                target = urljoin(BASE, link)
                parsed = urlparse(target)
                if (
                    parsed.netloc == "tashev-galving.com"
                    and parsed.path == path
                    and "show=99" in parsed.query
                    and "page=" in parsed.query
                    and target not in visited
                ):
                    pending.add(target)
        pages += len(visited)
        counts[category] = len(articles)
        live.update(articles)
    known = {p["SKU"] for p in snapshot}
    result = dict(
        categories=counts,
        pages=pages,
        live_articles=len(live),
        snapshot_articles=len(known),
        new_articles=sorted(live - known),
        removed_articles=sorted(known - live),
        new_categories=sorted(visited_categories - set(category_names)),
        removed_categories=sorted(set(category_names) - visited_categories),
    )
    print(json.dumps(result, indent=2))
    return int(
        any(
            result[key]
            for key in ("new_articles", "removed_articles", "new_categories", "removed_categories")
        )
    )


if __name__ == "__main__":
    sys.exit(audit())
