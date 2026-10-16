# SPDX-License-Identifier: GPL-3.0-or-later
"""Parametric bearing FeaturePython object, view provider and attachment."""

import re

import FreeCAD

import BearingData as BD
import BearingGeometry as BG
import BRselection as BRS
from BRutils import free_label, icon

V = FreeCAD.Vector
GROUP = "Bearing"
INFO = "Bearing info"
MATCH_TO = ["Housing", "Shaft"]


def edge_frame(obj, subname):
    """Return (center, outward normal, diameter, side) of a circular edge, or None.

    Everything is in global coordinates. `subname` may be a plain element ("Edge3") or a
    path from `obj` ("Body.Pad.Edge3"). The normal points out of the material (from an
    adjacent planar face). `side` is "outside" for a hole, "inside" for a shaft, or None.
    """
    edge, shape = BRS.resolve_edge(obj, subname)
    if edge is None:
        return None
    normal = BRS.outward_normal(shape, edge)
    return BRS.center_of(edge.Curve), normal, 2 * edge.Curve.Radius, BRS.edge_side(shape, edge)


def match_kind(series, frame):
    """Housing for a hole edge, Shaft for a shaft end; size heuristic if undetectable."""
    side = frame[3]
    if side == "outside":
        return "Housing"
    if side == "inside":
        return "Shaft"
    return BD.best_match_kind(series, frame[2])


class BearingObject:
    def __init__(self, obj, series="60", attach_to=None):
        obj.Proxy = self
        self.face_colors = []
        # FreeCAD's initial label is not always equal to Name (e.g. after a GUI delete)
        self.auto_label = obj.Label
        self.auto_target = None
        self.owner = obj.Name

        obj.addProperty("App::PropertyEnumeration", "Series", GROUP, "Bearing series")
        obj.Series = list(BD.SERIES.keys())
        obj.Series = series
        obj.addProperty(
            "App::PropertyEnumeration",
            "Designation",
            GROUP,
            "Bearing size within the series ('Auto' matches the attached edge)",
        )
        obj.Designation = self._designation_list(series)
        obj.Designation = BD.AUTO if attach_to else BD.SERIES[series][2]
        obj.addProperty(
            "App::PropertyEnumeration",
            "Closure",
            GROUP,
            "Shields (Z) or rubber seals (RS); single closures sit on the top face",
        )
        obj.Closure = BD.CLOSURES
        obj.Closure = "Open"
        obj.addProperty(
            "App::PropertyBool",
            "Flanged",
            GROUP,
            "Flanged outer ring (F/MF/FR miniatures; LMF/LMK linear bushings)",
        )
        self._add_flange_shape(obj)
        self._add_variant(obj)
        obj.addProperty(
            "App::PropertyEnumeration",
            "DetailLevel",
            GROUP,
            "Envelope: one solid; Standard: rings, rolling elements, shields or seals; "
            "Detailed: adds a cage on ball bearings (linear bushings: Standard has the "
            "retainer, Detailed adds the balls; roller and needle bearings: as Standard)",
        )
        obj.DetailLevel = BG.DETAIL_LEVELS
        obj.DetailLevel = "Standard"
        obj.addProperty(
            "App::PropertyEnumeration",
            "MatchTo",
            GROUP,
            "With Designation 'Auto': match the edge to the bore (Shaft) or OD (Housing)",
        )
        obj.MatchTo = MATCH_TO
        obj.addProperty(
            "App::PropertyLinkSubGlobal",
            "BaseObject",
            GROUP,
            "Circular edge the bearing is attached to",
        )
        obj.addProperty(
            "App::PropertyBool", "Invert", GROUP, "Flip the bearing to the other side of the edge"
        )
        obj.addProperty("App::PropertyDistance", "Offset", GROUP, "Shift along the bearing axis")

        for name, tip in (
            ("BoreDiameter", "Bore diameter d"),
            ("OuterDiameter", "Outside diameter D"),
            ("Width", "Width B"),
            ("PitchDiameter", "Computed pitch diameter dm"),
            ("BallDiameter", "Computed ball diameter Dw"),
        ):
            obj.addProperty("App::PropertyLength", name, INFO, tip)
            obj.setEditorMode(name, 1)
        obj.addProperty("App::PropertyInteger", "BallCount", INFO, "Computed number of balls")
        obj.setEditorMode("BallCount", 1)
        obj.addProperty(
            "App::PropertyString",
            "FullDesignation",
            INFO,
            "Designation including flange and closure codes",
        )
        obj.setEditorMode("FullDesignation", 1)

        if attach_to:
            obj.BaseObject = attach_to
            frame = edge_frame(attach_to[0], attach_to[1][0])
            if frame:
                obj.MatchTo = match_kind(series, frame)
        self._update_editor_modes(obj)

    @staticmethod
    def _add_flange_shape(obj):
        obj.addProperty(
            "App::PropertyEnumeration",
            "FlangeShape",
            GROUP,
            "Flanged linear bushings: Round (LMF) or Square (LMK)",
        )
        obj.FlangeShape = BD.FLANGE_SHAPES
        obj.FlangeShape = "Round"

    @staticmethod
    def _add_variant(obj):
        obj.addProperty(
            "App::PropertyEnumeration",
            "Variant",
            GROUP,
            "Cylindrical roller bearings: NU (ribs on the outer ring only) or NJ (one rib on "
            "the inner ring too). AXK: with or without an AS washer on each side",
        )
        BearingObject._set_variants(obj)

    @staticmethod
    def _set_variants(obj):
        """The Variant choices of the series' family (keeps the current one if it fits)."""
        if not hasattr(obj, "Variant"):
            return
        choices = BD.VARIANTS.get(BD.family(obj.Series), ["Standard"])
        current = obj.Variant if obj.Variant in choices else choices[0]
        obj.Variant = choices
        obj.Variant = current

    @staticmethod
    def _update_editor_modes(obj):
        """Show only the properties that apply to the series' family."""
        kind = BD.family(obj.Series)
        linear = kind == "linear"
        if hasattr(obj, "Closure"):
            # LM bushings are always UU; most other families come open only
            obj.setEditorMode("Closure", 2 if kind in BD.NO_CLOSURES else 0)
        if hasattr(obj, "Flanged"):
            obj.setEditorMode("Flanged", 0 if kind in ("deepgroove", "linear") else 2)
        if hasattr(obj, "Variant"):
            obj.setEditorMode("Variant", 0 if kind in BD.VARIANTS else 2)
        if hasattr(obj, "FlangeShape"):
            obj.setEditorMode("FlangeShape", 0 if linear else 2)
        if hasattr(obj, "PitchDiameter"):
            obj.setEditorMode("PitchDiameter", 2 if linear else 1)

    @staticmethod
    def _designation_list(series):
        return [BD.AUTO] + BD.designations(series)

    def onChanged(self, obj, prop):
        if prop == "Series" and "Restore" not in obj.State and hasattr(obj, "Designation"):
            current = obj.Designation
            names = self._designation_list(obj.Series)
            obj.Designation = names
            obj.Designation = current if current in names else BD.AUTO
            self._set_variants(obj)
            self._update_editor_modes(obj)

    def onDocumentRestored(self, obj):
        # documents from before linear bushings / v0.4 have no FlangeShape / Variant
        if not hasattr(obj, "FlangeShape"):
            self._add_flange_shape(obj)
        if not hasattr(obj, "Variant"):
            self._add_variant(obj)
        if getattr(self, "owner", None) is None:  # documents from before copy detection
            self.owner = obj.Name
        self._update_editor_modes(obj)

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
                "{}: attached element is not a circular edge\n".format(obj.Label)
            )

        if obj.Designation == BD.AUTO and frame:
            row = BD.auto_match(obj.Series, frame[2], obj.MatchTo)
            if row is None:
                raise ValueError(BD.no_fit_message(obj.Series, frame[2], obj.MatchTo))
        elif obj.Designation == BD.AUTO:
            row = BD.get_row(obj.Series, BD.SERIES[obj.Series][2])
        else:
            row = BD.get_row(obj.Series, obj.Designation)
        if row is None:
            row = BD.load_table(obj.Series)[0]

        flanged = obj.Flanged and row.has_flange
        if obj.Flanged and not row.has_flange:
            FreeCAD.Console.PrintWarning(
                "{}: no flanged variant of {} in the table, flange ignored\n".format(
                    obj.Label, row.name
                )
            )

        flange_shape = getattr(obj, "FlangeShape", "Round")
        variant = getattr(obj, "Variant", None)
        shape, colors = BG.build(row, obj.Closure, flanged, obj.DetailLevel, flange_shape, variant)
        self.face_colors = colors

        ins = BG.internals(row)
        obj.BoreDiameter = row.d
        obj.OuterDiameter = row.D
        obj.Width = row.width(obj.Closure) + (2 * BD.AS_WASHER if variant == "AXK + 2 AS" else 0.0)
        obj.PitchDiameter = ins.dm
        obj.BallDiameter = ins.Dw
        obj.BallCount = ins.Z
        obj.FullDesignation = BD.full_designation(row, obj.Closure, flanged, flange_shape, variant)
        self._update_label(obj)

        placement = obj.Placement
        if frame:
            center, normal = frame[0], frame[1]
            offset = obj.Offset.Value
            if obj.Invert:
                normal = -normal
            elif flanged and obj.MatchTo == "Housing":
                # in a hole the flange rests on the face and only the body goes in
                offset += row.C1
            placement = FreeCAD.Placement(
                center + normal * offset, FreeCAD.Rotation(V(0, 0, 1), normal)
            )
            # the frame is global; express it in the container the bearing lives in
            placement = BRS.parent_placement(obj).inverse().multiply(placement)
        obj.Shape = shape
        obj.Placement = placement

    def _update_label(self, obj):
        """Keep the label equal to the designation until the user renames the object.

        The first 608 is "608", further ones "608_001", "608_002", ... Labels must be
        unique, and left to itself FreeCAD makes them so by incrementing a trailing number:
        a second "608" would become "609", which reads as another bearing.

        auto_label is the label we (or FreeCAD, at creation) last assigned, which may differ
        from Name (e.g. "Bearing002" after a delete). auto_target is the designation it was
        made from.
        """
        target = obj.FullDesignation
        auto = getattr(self, "auto_label", None)
        owner = getattr(self, "owner", None)
        if owner is not None and owner != obj.Name:
            # a copy (copy & paste, duplicate): its state is the original's, and FreeCAD
            # made its label unique by bumping a trailing number ("634" -> "635"). Such a
            # label is still ours to set; a renamed original's copy keeps its label.
            self.owner = obj.Name
            if auto and re.sub(r"\d+$", "", obj.Label) == re.sub(r"\d+$", "", auto):
                auto = obj.Label
                self.auto_label = auto
        # FreeCAD's default labels ("Bearing", "Bearing002") also count as auto, which repairs
        # labels left stuck by v0.1's original Label == Name check
        if obj.Label not in (obj.Name, auto) and not re.fullmatch(r"Bearing\d*", obj.Label):
            return  # renamed by the user
        # also relabels auto labels from before the counter ("609" for a second 608)
        current = re.fullmatch(re.escape(target) + r"(_\d{3,})?", obj.Label)
        if getattr(self, "auto_target", None) != target or obj.Label != auto or not current:
            obj.Label = free_label(obj, target)
            self.auto_label = obj.Label
            self.auto_target = target

    def dumps(self):
        return {
            "auto_label": getattr(self, "auto_label", None),
            "auto_target": getattr(self, "auto_target", None),
            "owner": getattr(self, "owner", None),
        }

    def loads(self, state):
        self.face_colors = []
        state = state if isinstance(state, dict) else {}
        self.auto_label = state.get("auto_label")
        # documents saved before auto_target existed stored the designation in auto_label
        self.auto_target = state.get("auto_target", self.auto_label)
        self.owner = state.get("owner")


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
            except Exception as e:
                FreeCAD.Console.PrintLog("%s: face colors not applied: %s\n" % (obj.Label, e))

    def getIcon(self):
        series = getattr(getattr(self, "Object", None), "Series", "60")
        return icon("Bearing_%s.svg" % series)

    def claimChildren(self):
        return []

    def dumps(self):
        return None

    def loads(self, state):
        return None


def check_fit(series, attach_to, match_to=None):
    """None if the series has a size for the attached edge (or it is not a circle), else
    the reason it has none."""
    frame = edge_frame(attach_to[0], attach_to[1][0])
    if frame is None:
        return None
    match_to = match_to or match_kind(series, frame)
    if BD.auto_match(series, frame[2], match_to):
        return None
    return BD.no_fit_message(series, frame[2], match_to)


def make_bearing(series="60", designation=None, attach_to=None, doc=None, **props):
    """Create a bearing. attach_to is (object, ["EdgeN"]). Extra props are set on the object.

    Without a designation the size comes from the attached edge; ValueError if the series
    has no standard size for it."""
    if attach_to and designation in (None, BD.AUTO):
        reason = check_fit(series, attach_to, props.get("MatchTo"))
        if reason:
            raise ValueError(reason)
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
