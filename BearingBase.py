# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parametric bearing FeaturePython object, view provider and attachment."""

import re

import FreeCAD

import BearingData as BD
import BearingGeometry as BG
from BRutils import icon, translate

V = FreeCAD.Vector
GROUP = "Bearing"
INFO = "Bearing info"
MATCH_TO = ["Housing", "Shaft"]


def _is_circular_edge(sub):
    return hasattr(sub, "Curve") and sub.Curve.isDerivedFrom("Part::GeomCircle")


def edge_frame(obj, subname):
    """Return (center, outward normal, diameter) of a circular edge of obj, or None.

    The normal comes from an adjacent planar face so it points out of the material.
    If there is none, it falls back to the circle axis.
    """
    import Part

    try:
        shape = obj.Shape
        edge = shape.getElement(subname)
    except Exception:
        return None
    if not _is_circular_edge(edge):
        return None
    circle = edge.Curve
    normal = V(circle.Axis)
    for face in shape.ancestorsOfType(edge, Part.Face):
        if isinstance(face.Surface, Part.Plane):
            u0, u1, v0, v1 = face.ParameterRange
            normal = face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
            break
    return V(circle.Center), normal.normalize(), 2 * circle.Radius


class BearingObject:
    def __init__(self, obj, series="60", attach_to=None):
        obj.Proxy = self
        self.face_colors = []
        # FreeCAD's initial label is not always equal to Name (e.g. after a GUI delete)
        self.auto_label = obj.Label
        self.auto_target = None

        obj.addProperty("App::PropertyEnumeration", "Series", GROUP,
                        translate("Bearings", "Bearing series"))
        obj.Series = list(BD.SERIES.keys())
        obj.Series = series
        obj.addProperty("App::PropertyEnumeration", "Designation", GROUP,
                        translate("Bearings", "Bearing size within the series ('Auto' matches the attached edge)"))
        obj.Designation = self._designation_list(series)
        obj.Designation = BD.AUTO if attach_to else BD.SERIES[series][2]
        obj.addProperty("App::PropertyEnumeration", "Closure", GROUP,
                        translate("Bearings", "Shields (Z) or rubber seals (RS); single closures sit on the top face"))
        obj.Closure = BD.CLOSURES
        obj.Closure = "Open"
        obj.addProperty("App::PropertyBool", "Flanged", GROUP,
                        translate("Bearings", "Flanged outer ring (F/MF variants, miniature sizes only)"))
        obj.addProperty("App::PropertyEnumeration", "DetailLevel", GROUP,
                        translate("Bearings", "Envelope: one solid; Standard: rings, balls, shields; Detailed: adds cage"))
        obj.DetailLevel = BG.DETAIL_LEVELS
        obj.DetailLevel = "Standard"
        obj.addProperty("App::PropertyEnumeration", "MatchTo", GROUP,
                        translate("Bearings", "With Designation 'Auto': match the edge to the bore (Shaft) or OD (Housing)"))
        obj.MatchTo = MATCH_TO
        obj.addProperty("App::PropertyLinkSub", "BaseObject", GROUP,
                        translate("Bearings", "Circular edge the bearing is attached to"))
        obj.addProperty("App::PropertyBool", "Invert", GROUP,
                        translate("Bearings", "Flip the bearing to the other side of the edge"))
        obj.addProperty("App::PropertyDistance", "Offset", GROUP,
                        translate("Bearings", "Shift along the bearing axis"))

        for name, tip in (
            ("BoreDiameter", "Bore diameter d"),
            ("OuterDiameter", "Outside diameter D"),
            ("Width", "Width B"),
            ("PitchDiameter", "Computed pitch diameter dm"),
            ("BallDiameter", "Computed ball diameter Dw"),
        ):
            obj.addProperty("App::PropertyLength", name, INFO, translate("Bearings", tip))
            obj.setEditorMode(name, 1)
        obj.addProperty("App::PropertyInteger", "BallCount", INFO,
                        translate("Bearings", "Computed number of balls"))
        obj.setEditorMode("BallCount", 1)
        obj.addProperty("App::PropertyString", "FullDesignation", INFO,
                        translate("Bearings", "Designation including flange and closure codes"))
        obj.setEditorMode("FullDesignation", 1)

        if attach_to:
            obj.BaseObject = attach_to
            frame = edge_frame(attach_to[0], attach_to[1][0])
            if frame:
                obj.MatchTo = BD.best_match_kind(series, frame[2])

    @staticmethod
    def _designation_list(series):
        return [BD.AUTO] + BD.designations(series)

    def onChanged(self, obj, prop):
        if prop == "Series" and "Restore" not in obj.State and hasattr(obj, "Designation"):
            current = obj.Designation
            names = self._designation_list(obj.Series)
            obj.Designation = names
            obj.Designation = current if current in names else BD.AUTO

    def _attached_frame(self, obj):
        if not obj.BaseObject:
            return None
        base, subs = obj.BaseObject
        if not subs:
            return None
        return edge_frame(base, subs[0])

    def execute(self, obj):
        frame = self._attached_frame(obj)
        if obj.BaseObject and frame is None:
            FreeCAD.Console.PrintWarning(
                translate("Bearings", "{}: attached element is not a circular edge\n").format(obj.Label))

        if obj.Designation == BD.AUTO:
            row = BD.auto_match(obj.Series, frame[2], obj.MatchTo) if frame else \
                BD.get_row(obj.Series, BD.SERIES[obj.Series][2])
        else:
            row = BD.get_row(obj.Series, obj.Designation)
        if row is None:
            row = BD.load_table(obj.Series)[0]

        flanged = obj.Flanged and row.has_flange
        if obj.Flanged and not row.has_flange:
            FreeCAD.Console.PrintWarning(
                translate("Bearings", "{}: no flanged variant of {} in the table, flange ignored\n")
                .format(obj.Label, row.name))

        shape, colors = BG.build(row, obj.Closure, flanged, obj.DetailLevel)
        self.face_colors = colors

        ins = BG.Internals(row.d, row.D, row.B)
        obj.BoreDiameter = row.d
        obj.OuterDiameter = row.D
        obj.Width = row.width(obj.Closure)
        obj.PitchDiameter = ins.dm
        obj.BallDiameter = ins.Dw
        obj.BallCount = ins.Z
        obj.FullDesignation = BD.full_designation(row, obj.Closure, flanged)
        self._update_label(obj)

        placement = obj.Placement
        if frame:
            center, normal, _ = frame
            if obj.Invert:
                normal = -normal
            placement = FreeCAD.Placement(center + normal * obj.Offset.Value,
                                          FreeCAD.Rotation(V(0, 0, 1), normal))
        obj.Shape = shape
        obj.Placement = placement

    def _update_label(self, obj):
        """Keep the label equal to the designation until the user renames the object.

        auto_label is the label we (or FreeCAD, at creation) last assigned, which may differ
        from both Name and the designation (e.g. "Bearing002" after a delete, or "608001"
        when FreeCAD makes labels unique). auto_target is the designation it was made from.
        """
        target = obj.FullDesignation
        auto = getattr(self, "auto_label", None)
        # FreeCAD's default labels ("Bearing", "Bearing002") also count as auto, which repairs
        # labels left stuck by v0.1's original Label == Name check
        if obj.Label not in (obj.Name, auto) and not re.fullmatch(r"Bearing\d*", obj.Label):
            return  # renamed by the user
        if getattr(self, "auto_target", None) != target or obj.Label != auto:
            obj.Label = target
            self.auto_label = obj.Label
            self.auto_target = target

    def dumps(self):
        return {"auto_label": getattr(self, "auto_label", None),
                "auto_target": getattr(self, "auto_target", None)}

    def loads(self, state):
        self.face_colors = []
        state = state if isinstance(state, dict) else {}
        self.auto_label = state.get("auto_label")
        # documents saved before auto_target existed stored the designation in auto_label
        self.auto_target = state.get("auto_target", self.auto_label)


class ViewProviderBearing:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def updateData(self, obj, prop):
        if prop != "Shape":
            return
        colors = getattr(obj.Proxy, "face_colors", None)
        if colors and len(colors) == len(obj.Shape.Faces):
            try:
                obj.ViewObject.DiffuseColor = colors
            except Exception:
                pass

    def getIcon(self):
        series = getattr(getattr(self, "Object", None), "Series", "60")
        return icon("Bearing_%s.svg" % series)

    def claimChildren(self):
        return []

    def dumps(self):
        return None

    def loads(self, state):
        return None


def make_bearing(series="60", designation=None, attach_to=None, doc=None, **props):
    """Create a bearing. attach_to is (object, ["EdgeN"]). Extra props are set on the object."""
    doc = doc or FreeCAD.ActiveDocument or FreeCAD.newDocument()
    obj = doc.addObject("Part::FeaturePython", "Bearing")
    BearingObject(obj, series, attach_to)
    if designation:
        obj.Designation = designation
    for k, v in props.items():
        setattr(obj, k, v)
    if FreeCAD.GuiUp:
        ViewProviderBearing(obj.ViewObject)
    obj.recompute()
    return obj
