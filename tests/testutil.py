# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared helpers for the headless tests."""

import os
import tempfile
import unittest

import FreeCAD
import Part

import BRselection as BRS

V = FreeCAD.Vector
TOL = 1e-3


def close(a, b, tol=TOL):
    return abs(a - b) <= tol


def tight_bb(shape):
    """Exact bounding box (Shape.BoundBox is loose around revolved arcs)."""
    return shape.optimalBoundingBox(False, False)


def plate_with_hole(doc, dia, thickness=10.0):
    box = Part.makeBox(40, 40, thickness, V(-20, -20, 0))
    hole = Part.makeCylinder(dia / 2, thickness + 2, V(0, 0, -1))
    obj = doc.addObject("Part::Feature", "Plate")
    obj.Shape = box.cut(hole)
    return obj


def find_circle(obj, radius, z):
    """Name ("EdgeN") of the circular edge of `obj` with this radius at height z."""
    for i, e in enumerate(obj.Shape.Edges, 1):
        if (
            BRS.is_circular_edge(e)
            and close(e.Curve.Radius, radius)
            and close(BRS.center_of(e.Curve).z, z)
        ):
            return "Edge%d" % i
    raise AssertionError("edge r=%g z=%g not found" % (radius, z))


def is_invalid(obj):
    # FeaturePython objects have no isError() in FreeCAD 1.1
    return "Invalid" in obj.State


class DocumentTest(unittest.TestCase):
    """A test case with a fresh document per test, closed afterwards."""

    def setUp(self):
        self.doc = FreeCAD.newDocument(type(self).__name__)

    def tearDown(self):
        if self.doc.Name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.doc.Name)

    def reopen(self):
        """Save the document to a temporary file, close it and open it again."""
        path = os.path.join(tempfile.mkdtemp(), self.doc.Name + ".FCStd")
        self.doc.saveAs(path)
        FreeCAD.closeDocument(self.doc.Name)
        self.doc = FreeCAD.openDocument(path)
        return self.doc
