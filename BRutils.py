# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared paths and small helpers for the Bearings workbench."""

import os

wbPath = os.path.dirname(os.path.abspath(__file__))
iconPath = os.path.join(wbPath, "Icons")
dataPath = os.path.join(wbPath, "BRData")


def icon(name):
    return os.path.join(iconPath, name)
