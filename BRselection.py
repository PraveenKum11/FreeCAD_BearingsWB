# SPDX-License-Identifier: LGPL-2.1-or-later
"""Selection and edge geometry helpers shared by standard and printable bearings.

Adapted from the DeepGrooveBallBearing macro. All edges and frames returned here are in
document (global) coordinates, resolved through parent containers (App::Part, Body).
"""

import FreeCAD as App
import Part

TOL = 1e-6


def center_of(circle):
    """Circle center (`Center` is deprecated in newer FreeCAD in favour of `Location`)."""
    return App.Vector(circle.Location if hasattr(circle, "Location") else circle.Center)


def is_circular_edge(shape):
    return hasattr(shape, "Curve") and isinstance(shape.Curve, Part.Circle)


def global_placement(obj):
    """Placement of `obj` in document coordinates, through its parent containers."""
    pl = obj.Placement
    parent = obj.getParentGeoFeatureGroup()
    while parent:
        pl = parent.Placement.multiply(pl)
        parent = parent.getParentGeoFeatureGroup()
    return pl


def parent_placement(obj):
    """Placement of the coordinate system `obj` lives in (its containers, not itself)."""
    pl = App.Placement()
    parent = obj.getParentGeoFeatureGroup()
    while parent:
        pl = parent.Placement.multiply(pl)
        parent = parent.getParentGeoFeatureGroup()
    return pl


def resolve_edge(obj, subname):
    """Return (global edge, global shape of the object owning it), or (None, None).

    `subname` is either an element ("Edge3") or a path from `obj` ("Body.Pad.Edge3"), as
    stored in a PropertyLinkSub or returned by getSelectionEx("", 0). The edge is taken
    from the owning shape so the two share topology (needed for ancestorsOfType).
    """
    path, _, element = subname.rpartition(".")
    path = path + "." if path else ""
    try:
        shape = Part.getShape(obj, path) if path else Part.getShape(obj)
        edge = shape.getElement(element)
    except Exception:
        return None, None
    if not is_circular_edge(edge):
        return None, None
    to_global = parent_placement(obj)
    if not to_global.isIdentity():
        shape = shape.copy()
        shape.Placement = to_global.multiply(shape.Placement)
        edge = shape.getElement(element)
    return edge, shape


def owner_object(obj, subname):
    """The object owning the element of `subname`, e.g. the Pad for "Body.Pad.Edge3"."""
    path = subname.rpartition(".")[0]
    return obj.getSubObject(path + ".", retType=1) if path else obj


def frame_placement(edge, axial_offset=0.0):
    """Global placement with X radial (through the edge), Z along the edge's axis,
    origin on the axis shifted `axial_offset` from the edge's plane."""
    circle = edge.Curve
    axis = App.Vector(circle.Axis).normalize()
    origin = center_of(circle) + axis * axial_offset

    # Radial direction: from the center to a point on the edge, with any axial part removed
    radial = edge.valueAt(edge.FirstParameter) - center_of(circle)
    radial = radial - axis * radial.dot(axis)
    radial.normalize()
    y = axis.cross(radial)

    return App.Placement(
        App.Matrix(
            radial.x, y.x, axis.x, origin.x,
            radial.y, y.y, axis.y, origin.y,
            radial.z, y.z, axis.z, origin.z,
            0, 0, 0, 1,
        )
    )


def outward_normal(shape, edge):
    """Normal of a planar face bounded by `edge`, pointing out of the material.

    Falls back to the circle axis when no planar face shares the edge.
    """
    try:
        faces = shape.ancestorsOfType(edge, Part.Face)
    except Part.OCCError:
        # edge is not a sub-shape of `shape` (e.g. a copy): match faces by geometry
        faces = [f for f in shape.Faces if any(e.isSame(edge) or _same_circle(e, edge) for e in f.Edges)]
    for face in faces:
        if isinstance(face.Surface, Part.Plane):
            u0, u1, v0, v1 = face.ParameterRange
            return face.normalAt((u0 + u1) / 2, (v0 + v1) / 2).normalize()
    return App.Vector(edge.Curve.Axis).normalize()


def _same_circle(a, b, tol=1e-6):
    if not (is_circular_edge(a) and is_circular_edge(b)):
        return False
    return (abs(a.Curve.Radius - b.Curve.Radius) < tol
            and (center_of(a.Curve) - center_of(b.Curve)).Length < tol)


def coaxial_cylinders(solid, edge):
    """Cylindrical faces of `solid` on the edge's axis, as (face, radius) pairs."""
    circle = edge.Curve
    center = center_of(circle)
    axis = App.Vector(circle.Axis).normalize()
    found = []
    for face in solid.Faces:
        surf = face.Surface
        if not isinstance(surf, Part.Cylinder):
            continue
        if abs(abs(App.Vector(surf.Axis).normalize().dot(axis)) - 1) > TOL:
            continue
        offset = center_of(surf) - center
        if (offset - axis * offset.dot(axis)).Length > 1e-4:
            continue  # parallel but not on the bearing axis
        found.append((face, surf.Radius))
    return found


def cylinder_side(solid, edge):
    """Find the cylindrical face the circular edge bounds and which side its material is on.

    Returns (side, lo, hi): side is "outside" for a bore (material radially outside the
    cylinder) or "inside" for a shaft / outer surface; lo..hi is the face's axial range
    measured from the edge's plane. (None, 0, 0) if there is no such face.
    """
    circle = edge.Curve
    center = center_of(circle)
    axis = App.Vector(circle.Axis).normalize()
    radial = edge.valueAt(edge.FirstParameter) - center
    radial = radial - axis * radial.dot(axis)
    radial.normalize()
    eps = min(0.01, circle.Radius * 0.01)

    for face, radius in coaxial_cylinders(solid, edge):
        if abs(radius - circle.Radius) > 1e-4:
            continue
        heights = [(v.Point - center).dot(axis) for v in face.Vertexes]
        if min(abs(h) for h in heights) > 1e-4:
            continue  # same diameter, but not the face this edge belongs to
        lo, hi = min(heights), max(heights)
        on_face = center + axis * ((lo + hi) / 2) + radial * circle.Radius
        outside = solid.isInside(on_face + radial * eps, 1e-7, False)
        inside = solid.isInside(on_face - radial * eps, 1e-7, False)
        if outside != inside:
            return ("outside" if outside else "inside"), lo, hi
    return None, 0.0, 0.0


def nearest_solid(shape, edge):
    return min(shape.Solids, key=lambda s: s.distToShape(edge)[0])


def edge_side(shape, edge):
    """"outside" (a bore / hole), "inside" (a shaft / outer surface) or None."""
    if shape is None or not shape.Solids:
        return None
    return cylinder_side(nearest_solid(shape, edge), edge)[0]


def selected_edges():
    """Selected circular edges as (root object, subname path) pairs.

    Resolve mode 0 gives the full path from a root object, so the stored link resolves
    to global coordinates no matter how deeply the edge's object is nested.
    """
    import FreeCADGui as Gui

    result = []
    for sel in Gui.Selection.getSelectionEx("", 0):
        for sub in sel.SubElementNames:
            if not sub.rpartition(".")[2].startswith("Edge"):
                continue
            edge, _ = resolve_edge(sel.Object, sub)
            if edge is not None:
                result.append((sel.Object, sub))
    return result
