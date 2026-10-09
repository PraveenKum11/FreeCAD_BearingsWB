# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared paths and small helpers for the Bearings workbench."""

import os

import FreeCAD

wbPath = os.path.dirname(os.path.abspath(__file__))
iconPath = os.path.join(wbPath, "Icons")
dataPath = os.path.join(wbPath, "BRData")

translate = FreeCAD.Qt.translate
QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP


def isGuiLoaded():
    return FreeCAD.GuiUp


def icon(name):
    return os.path.join(iconPath, name)
