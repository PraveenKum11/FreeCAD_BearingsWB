# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline supplier coverage, including the bearing components of wheel kits.

This is a dated catalog snapshot, not a price or availability service. No network
access is needed by the workbench. Loose-ball products are included as rolling elements.
"""

import csv
import os
import re

from BRutils import dataPath

_products = None
_index = None


def normalize(text):
    return re.sub(r"[\s-]", "", text.upper())


def products():
    global _products
    if _products is None:
        with open(os.path.join(dataPath, "tashev_catalog.csv"), encoding="utf-8", newline="") as f:
            _products = list(csv.DictReader(f))
    return _products


def lookup(text):
    """Exact supplier article number or designation; partial searches remain in BearingData."""
    global _index
    if _index is None:
        _index = {}
        for product in products():
            for key in {normalize(product["SKU"]), normalize(product["Designation"])}:
                _index.setdefault(key, []).append(product)
    key = normalize(text or "")
    return list(_index.get(key, ()))


def components(product):
    """(series, row name, closure) for each part, preserving kit/set quantities.

    Each CSV entry is series:name:closure[:quantity]; omitted quantity means one.
    """
    result = []
    for entry in product["Components"].split(";"):
        if entry:
            fields = entry.split(":")
            quantity = int(fields[3]) if len(fields) == 4 else 1
            if len(fields) not in (3, 4) or quantity < 1:
                raise ValueError("Invalid catalog component: " + entry)
            result.extend([tuple(fields[:3])] * quantity)
    return result


def targets(text):
    return {component for product in lookup(text) for component in components(product)}


def make_product(article, doc=None):
    """Insert all bearings or loose balls of a supplier article, as independent objects.

    Wheel-kit bearings have no published installed separation: each is placed at the
    origin for the caller to position. Separate kit seals, nuts and caps are excluded.
    Ball assortments preserve the manufacturer's quantities, excluding the storage box.
    """
    import BearingBase

    matches = lookup(article)
    if len(matches) != 1 or not components(matches[0]):
        raise ValueError("Use a unique article number from the supplier catalog")
    product = matches[0]
    result = []
    for series, name, closure in components(product):
        obj = BearingBase.make_bearing(
            series, name, doc=doc, Closure=closure, SupplierArticle=product["SKU"]
        )
        result.append(obj)
    return result
