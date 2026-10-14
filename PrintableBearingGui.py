# SPDX-License-Identifier: GPL-3.0-or-later
"""Task panel and command for 3D-printable bearings (ported from the macro dialog)."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

import BRselection as BRS
import PrintableBearing as PB
from BRutils import icon

TITLE = "Printable Bearing"
CUSTOM = "Custom"

# Tooltips for the panel's own controls. They describe how the panel behaves, so they
# live next to that code; what the bearing parameters mean is in PB.BEARING_DOCS / CAGE_DOCS.
UI_HELP = {
    "Races": "Groove selected body: cut the ball groove into the body the edge belongs to; the "
    "body itself becomes the races. On a bore, the bore is the bearing's inner diameter: a "
    "thin inner race is split off and the rest of the body is the outer race. On an outer "
    "surface it is the other way round. A plain ring becomes the inner and outer race. "
    "The other diameter and the height set where the groove goes: the other diameter "
    "starts %g mm from the selected one, the height is the length of the selected bore "
    "or surface.\n"
    "Create races: build a new ring with both races from the sizes below. The selected "
    "edge (e.g. the end of a shaft or a housing bore; the origin if nothing is selected) "
    "sets the bearing's position and axis." % PB.OTHER_DIAMETER_OFFSET,
    "EdgeIs": "Is the selected edge the bearing's inner or outer diameter? When grooving the "
    "selected body this is detected: a bore is the inner diameter, an outer surface the "
    "outer diameter. When creating races it is preset from the edge (end of a shaft: "
    "inner; housing bore: outer) and can be changed. That diameter is taken from the "
    "edge and locked.",
    "Reverse": "Build the bearing on the other side of the selected edge (or of the XY plane).",
    "Cage": "Snap-in cage that sits in the gap between the races and keeps the balls evenly "
    "spaced. Built as a separate 'Cage' body. Untick to leave it out.",
    "Balls": "Also model the balls, as a separate 'Balls' body, sized and spaced from the "
    "values above.",
    "Size": "Prefill the inner diameter, outer diameter and height from a catalog bearing "
    "(608, 6204, MR105, ...). With a selected edge, only sizes matching its diameter are "
    "listed. Custom: enter the sizes yourself.",
    "Preview": "Show the bearing in the 3D view while editing: the inner and outer diameter "
    "as labelled rings on both faces, and a see-through view of the races, balls and cage. "
    "It is only a preview; nothing is added to the document until OK.",
    "BallPreset": "Common balls to buy for printed bearings. Sets the ball diameter; "
    "airsoft BBs are nominally 6 mm but measure 5.95 mm.",
    "BallDiameter": PB.BEARING_DOCS["BallDiameter"]
    + " Default %g mm; it is not changed for you when the sizes change." % PB.DEFAULT_BALL_DIAMETER,
}


def get_selection():
    """Return (feature, global edge, global shape) for one selected circular edge,
    ("bearing", obj) for one selected standard Bearing, or None for no selection."""
    sel = Gui.Selection.getSelectionEx("", 0)
    if not sel:
        return None
    if len(sel) == 1 and not sel[0].SubElementNames:
        obj = sel[0].Object
        leaf = Gui.Selection.getSelection()[0] if Gui.Selection.getSelection() else obj
        if hasattr(leaf, "FullDesignation"):
            return ("bearing", leaf)
    if len(sel) != 1 or len(sel[0].SubElementNames) != 1:
        raise ValueError(
            "Select exactly one circular edge, one standard bearing, or nothing "
            "(to create races at the origin)."
        )
    top, subname = sel[0].Object, sel[0].SubElementNames[0]
    if not subname.split(".")[-1].startswith("Edge"):
        raise ValueError("The selection must be an edge.")
    # edge and shape share topology, so faces adjacent to the edge can be found
    edge, shape = BRS.resolve_edge(top, subname)
    if edge is None:
        raise ValueError("The selected edge is not circular.")
    return BRS.owner_object(top, subname), edge, shape


# preview colors, as in the macro's README images: races blue, cage orange, balls red
PREVIEW_COLORS = {
    "inner race": (0.35, 0.55, 0.85),
    "outer race": (0.35, 0.55, 0.85),
    "ball": (0.85, 0.2, 0.2),
    "cage": (0.95, 0.55, 0.1),
}
RING_COLORS = {"ID": (0.1, 0.75, 0.25), "OD": (0.9, 0.2, 0.75)}


class Preview:
    """Temporary scene-graph overlay in the active 3D view; never added to the document.

    Shows the ID and OD as labelled rings on both faces (drawn on top, so they are
    visible through the part) and a translucent ghost of races, balls and cage.
    """

    active = None  # the preview currently on screen, so a stale one can always be removed

    def __init__(self):
        from pivy import coin

        self.coin = coin
        self.view = Gui.ActiveDocument.ActiveView if Gui.ActiveDocument else None
        self.root = None

    @classmethod
    def clear_stale(cls):
        if cls.active is not None:
            cls.active.clear()

    def clear(self, *_):
        if self.root is not None and self.view is not None:
            try:
                self.view.getSceneGraph().removeChild(self.root)
            except Exception:
                pass  # the view may already be gone (document closed)
        self.root = None
        if Preview.active is self:
            Preview.active = None

    def show(self, placement, values, cage=True):
        self.clear()
        if self.view is None:
            return
        coin = self.coin
        root = coin.SoSeparator()
        xf = coin.SoTransform()
        xf.translation.setValue(*placement.Base)
        q = placement.Rotation.Q
        xf.rotation.setValue(coin.SbRotation(q[0], q[1], q[2], q[3]))
        root.addChild(xf)

        ghost = coin.SoSeparator()
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.COUNTERCLOCKWISE
        hints.creaseAngle = 0.6
        ghost.addChild(hints)
        tol = max(0.01, values["OD"] / 300)
        for role, shape in PB.preview_shapes(values, cage):
            ghost.addChild(self._mesh(shape, PREVIEW_COLORS[role], tol))
        root.addChild(ghost)

        rings = coin.SoAnnotation()  # drawn on top of everything
        style = coin.SoDrawStyle()
        style.lineWidth = 3
        rings.addChild(style)
        h = values["Height"] / 2
        for key in ("ID", "OD"):
            r = values[key] / 2
            if r <= 0:
                continue
            for z in (-h, h):
                rings.addChild(self._ring(r, z, RING_COLORS[key]))
            rings.addChild(
                self._label("%s Ø%.2f" % (key, values[key]), r, h, RING_COLORS[key], key == "ID")
            )
        root.addChild(rings)

        self.view.getSceneGraph().addChild(root)
        self.root = root
        Preview.active = self

    def _mesh(self, shape, rgb, tol):
        coin = self.coin
        points, triangles = shape.tessellate(tol)
        sep = coin.SoSeparator()
        mat = coin.SoMaterial()
        mat.diffuseColor.setValue(*rgb)
        mat.transparency.setValue(0.55)
        sep.addChild(mat)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), [(p.x, p.y, p.z) for p in points])
        sep.addChild(coords)
        faces = coin.SoIndexedFaceSet()
        index = []
        for a, b, c in triangles:
            index.extend((a, b, c, -1))
        faces.coordIndex.setValues(0, len(index), index)
        sep.addChild(faces)
        return sep

    def _ring(self, r, z, rgb, segments=96):
        import math

        coin = self.coin
        sep = coin.SoSeparator()
        mat = coin.SoBaseColor()
        mat.rgb.setValue(*rgb)
        sep.addChild(mat)
        pts = [
            (r * math.cos(2 * math.pi * i / segments), r * math.sin(2 * math.pi * i / segments), z)
            for i in range(segments + 1)
        ]
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(pts), pts)
        sep.addChild(coords)
        line = coin.SoLineSet()
        line.numVertices.setValue(len(pts))
        sep.addChild(line)
        return sep

    def _label(self, text, r, h, rgb, inner):
        import math

        coin = self.coin
        sep = coin.SoSeparator()
        color = coin.SoBaseColor()
        color.rgb.setValue(*rgb)
        sep.addChild(color)
        # ID label on one side, OD label on the opposite side, both on the top face and
        # just outside their ring so the text doesn't sit on the line
        a = math.radians(150 if inner else -30)
        rr = r * 1.06 + 0.5
        pos = coin.SoTranslation()
        pos.translation.setValue(rr * math.cos(a), rr * math.sin(a), h)
        sep.addChild(pos)
        font = coin.SoFont()
        font.size = 20
        sep.addChild(font)
        txt = coin.SoText2()
        txt.string = text
        sep.addChild(txt)
        return sep


class TaskPanel:
    """One panel for both modes, as the macro's dialog."""

    def __init__(
        self,
        edge=None,
        measured=None,
        create_inner=True,
        bearing=None,
        reverse=False,
        feature=None,
        body=None,
    ):
        """`edge`: the selected circular edge (global), or None.
        `measured`: measure_body() result if the selected body can be grooved, else None.
        `create_inner`: default for "Selected edge is" when creating races.
        `bearing`: a standard Bearing to replace (its size and placement are used).
        `reverse`: default for "Reverse direction" (set so the races go into the material).
        `feature`, `body`: the object owning the edge and its PartDesign Body (or None)."""
        self.edge, self.measured, self.create_inner = edge, measured, create_inner
        self.bearing = bearing
        self.feature, self.body = feature, body
        self._mode = None
        self.edge_dia = 2 * edge.Curve.Radius if edge else None

        self.form = QtGui.QWidget()
        self.form.setWindowTitle(TITLE)
        self.form.setWindowIcon(QtGui.QIcon(icon("PrintableBearing.svg")))
        form = QtGui.QFormLayout(self.form)

        def row(layout, label, widget, help_text):
            """Add a form row whose label and field both carry the help text as a tooltip."""
            help_text = PB.wrapped(help_text)
            widget.setToolTip(help_text)
            if label is None:
                layout.addRow(widget)
                return
            lbl = QtGui.QLabel(label)
            lbl.setToolTip(help_text)
            layout.addRow(lbl, widget)

        def spin(value, prefix="Ø "):
            s = QtGui.QDoubleSpinBox()
            s.setDecimals(2)
            s.setSingleStep(0.01)  # arrow keys / buttons step by the last shown digit
            s.setAccelerated(True)  # holding an arrow speeds up
            s.setRange(0.0, 10000)
            s.setPrefix(prefix)
            s.setSuffix(" mm")
            s.setValue(value)
            # report a typed value only on Enter / leaving the field (arrows step at once),
            # so nothing recomputes on every keystroke
            s.setKeyboardTracking(False)
            return s

        self.mode = QtGui.QComboBox()
        if measured:
            self.mode.addItem(PB.GROOVE)
        self.mode.addItem(PB.CREATE)
        row(form, "Races:", self.mode, UI_HELP["Races"])

        self.edge_is = QtGui.QComboBox()
        self.edge_is.addItems(["Inner diameter", "Outer diameter"])
        if edge:
            row(form, "Selected edge (Ø %.2f) is:" % self.edge_dia, self.edge_is, UI_HELP["EdgeIs"])

        self.size = QtGui.QComboBox()
        row(form, "Catalog size:", self.size, UI_HELP["Size"])

        d = self.edge_dia or 20.0
        self.id_ = spin(d)
        self.od = spin(PB.other_diameter(d, True))
        self.height = spin(PB.DEFAULT_HEIGHT, prefix="")
        row(form, "Inner diameter:", self.id_, PB.BEARING_DOCS["ID"])
        row(form, "Outer diameter:", self.od, PB.BEARING_DOCS["OD"])
        row(form, "Height:", self.height, PB.BEARING_DOCS["Height"])

        self.reverse = QtGui.QCheckBox("Reverse direction")
        self.reverse.setChecked(reverse)
        row(form, "", self.reverse, UI_HELP["Reverse"])

        self.ball_preset = QtGui.QComboBox()
        self.ball_preset.addItem(CUSTOM)
        for label, dia in PB.BALL_PRESETS:
            self.ball_preset.addItem(label, dia)
        row(form, "Ball preset:", self.ball_preset, UI_HELP["BallPreset"])
        self.ball = spin(PB.DEFAULT_BALL_DIAMETER)
        row(form, "Ball diameter:", self.ball, UI_HELP["BallDiameter"])
        self.num_balls = QtGui.QSpinBox()
        self.num_balls.setRange(1, 1000)
        self.num_balls.setValue(PB.DEFAULT_NUM_BALLS)
        self.num_balls.setKeyboardTracking(False)
        row(form, "Number of balls:", self.num_balls, PB.BEARING_DOCS["NumBalls"])

        # Cage options (checkable group = "create cage")
        self.cage = QtGui.QGroupBox("Cage")
        self.cage.setCheckable(True)
        self.cage.setChecked(True)
        cform = QtGui.QFormLayout(self.cage)
        self.cage_t = spin(PB.CAGE_DEFAULTS["CageThickness"], prefix="")
        self.cage_top = spin(PB.CAGE_DEFAULTS["CageTopOffset"], prefix="")
        self.pocket_clr = spin(PB.CAGE_DEFAULTS["PocketClearance"], prefix="")
        self.pocket_rise = spin(PB.CAGE_DEFAULTS["PocketRise"], prefix="")
        row(cform, "Cage thickness:", self.cage_t, PB.CAGE_DOCS["CageThickness"])
        row(cform, "Cage top offset:", self.cage_top, PB.CAGE_DOCS["CageTopOffset"])
        row(cform, "Pocket clearance:", self.pocket_clr, PB.CAGE_DOCS["PocketClearance"])
        row(cform, "Pocket rise:", self.pocket_rise, PB.CAGE_DOCS["PocketRise"])
        row(form, None, self.cage, UI_HELP["Cage"])

        self.balls = QtGui.QCheckBox("Create balls")
        self.balls.setChecked(False)
        row(form, "Balls:", self.balls, UI_HELP["Balls"])

        self.show_preview = QtGui.QCheckBox("Show preview")
        self.show_preview.setChecked(True)
        row(form, "", self.show_preview, UI_HELP["Preview"])
        # what is wrong with the current values, if anything (OK refuses them too)
        self.status = QtGui.QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #d03030;")
        form.addRow(self.status)

        Preview.clear_stale()
        self.preview = Preview()
        # however the panel goes away (OK, Cancel, another task replacing it, document
        # closed), its preview goes with it
        self.form.destroyed.connect(self.preview.clear)
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(120)  # coalesce bursts of edits (spin box arrows)
        self._preview_timer.timeout.connect(self.values_changed)

        self.mode.currentIndexChanged.connect(self.refresh)
        self.edge_is.currentIndexChanged.connect(self.refresh)
        for s in (self.id_, self.od, self.height):
            s.valueChanged.connect(self.sync_size)
        self.size.currentIndexChanged.connect(self.apply_size)
        self.ball_preset.currentIndexChanged.connect(self.apply_ball_preset)
        self.ball.valueChanged.connect(self.sync_ball_preset)

        for w in (
            self.id_,
            self.od,
            self.height,
            self.ball,
            self.cage_t,
            self.cage_top,
            self.pocket_clr,
            self.pocket_rise,
        ):
            w.valueChanged.connect(self.schedule_preview)
        self.num_balls.valueChanged.connect(self.schedule_preview)
        for w in (self.mode, self.edge_is):
            w.currentIndexChanged.connect(self.schedule_preview)
        for w in (self.reverse, self.show_preview):
            w.toggled.connect(self.schedule_preview)
        self.cage.toggled.connect(self.schedule_preview)

        if bearing is not None:
            # Replace a standard bearing: its size is fixed, it sits where the bearing was
            self.id_.setValue(bearing.BoreDiameter.Value)
            self.od.setValue(bearing.OuterDiameter.Value)
            self.height.setValue(bearing.Width.Value)
            for w in (self.id_, self.od, self.height, self.size, self.reverse):
                w.setEnabled(False)
        self.refresh()
        self.values_changed()

    # ------------------------------------------------------------ preview

    def schedule_preview(self, *_):
        self._preview_timer.start()

    def values_changed(self):
        self.update_status()
        self.update_preview()

    def update_status(self):
        """Say what is wrong with the values. Ball and cage sizes are never changed for
        the user: they keep their defaults (or what was typed) until edited."""
        o = self.options()
        try:
            PB.validate(o["values"], o["cage"], o["balls"])
            self.status.setText("")
            self.status.setVisible(False)
        except ValueError as e:
            self.status.setText(str(e))
            self.status.setVisible(True)

    def update_preview(self):
        if not self.show_preview.isChecked():
            self.preview.clear()
            return
        o = self.options()
        frame = PB.preview_frame(
            o["mode"], self.edge, self.measured, o["values"]["Height"], o["reverse"], self.bearing
        )
        try:
            self.preview.show(frame, o["values"], o["cage"])
        except Exception as e:  # a preview problem must never block the panel
            App.Console.PrintLog("Printable bearing preview: %s\n" % e)
            self.preview.clear()

    # ------------------------------------------------------------ catalog size / presets

    def fill_sizes(self):
        """Catalog sizes that fit the locked diameter (all of them without an edge)."""
        self.size.blockSignals(True)
        self.size.clear()
        self.size.addItem(CUSTOM)
        locked = self.locked_diameter()
        for name, d, D, B in PB.catalog_rows():
            if locked is not None:
                key, dia = locked
                if abs((d if key == "ID" else D) - dia) > 1e-6:
                    continue
            self.size.addItem("%s  (%gx%gx%g)" % (name, d, D, B), (d, D, B))
        self.size.blockSignals(False)
        self.sync_size()

    def locked_diameter(self):
        """("ID" or "OD", diameter) taken from the selected edge, or None."""
        if not self.edge:
            return None
        return ("ID" if self.edge_is.currentIndex() == 0 else "OD"), self.edge_dia

    def apply_size(self, index):
        data = self.size.itemData(index)
        if not data:
            return
        # with an edge, the list only holds sizes whose locked diameter matches it
        d, D, B = data
        self.id_.setValue(d)
        self.od.setValue(D)
        self.height.setValue(B)

    def apply_preset(self, d, D, B):
        """Start from a given size; a diameter locked by the selected edge is kept."""
        if self.mode.currentText() == PB.GROOVE:
            self.mode.setCurrentIndex(self.mode.findText(PB.CREATE))
        for w, val in ((self.id_, d), (self.od, D), (self.height, B)):
            if w.isEnabled():
                w.setValue(val)
        self.sync_size()

    def sync_size(self, *_):
        """Show the catalog size matching the current ID x OD x Height, or Custom."""
        v = {"ID": self.id_.value(), "OD": self.od.value(), "Height": self.height.value()}
        name = PB.catalog_match(v, tol=5e-3)
        index = 0
        for i in range(1, self.size.count()):
            if self.size.itemText(i).split()[0] == name:
                index = i
                break
        self.size.blockSignals(True)
        self.size.setCurrentIndex(index)
        self.size.blockSignals(False)

    def apply_ball_preset(self, index):
        dia = self.ball_preset.itemData(index)
        if dia:
            self.ball.setValue(dia)

    def sync_ball_preset(self, *_):
        index = 0
        for i in range(1, self.ball_preset.count()):
            if abs(self.ball_preset.itemData(i) - self.ball.value()) < 5e-3:
                index = i
                break
        self.ball_preset.blockSignals(True)
        self.ball_preset.setCurrentIndex(index)
        self.ball_preset.blockSignals(False)

    # ------------------------------------------------------------ macro dialog logic

    def refresh(self, *_):
        groove = self.mode.currentText() == PB.GROOVE
        mode_changed = self._mode != self.mode.currentText()
        self._mode = self.mode.currentText()
        m = self.measured

        if mode_changed and self.edge:
            # Each mode starts from its own defaults
            self.edge_is.blockSignals(True)
            inner_default = m["is_inner"] if groove else self.create_inner
            self.edge_is.setCurrentIndex(0 if inner_default else 1)
            self.edge_is.blockSignals(False)
            if groove:
                self.height.setValue(m["height"])
            elif self.bearing is None:
                self.height.setValue(PB.DEFAULT_HEIGHT)

        # Grooving the body: which diameter the edge is was detected
        self.edge_is.setEnabled(not groove)
        if self.bearing is None:
            self.reverse.setEnabled(not groove)
            self.height.setEnabled(True)
            self.size.setEnabled(not groove)

        inner = self.edge_is.currentIndex() == 0
        locked, other = (self.id_, self.od) if inner else (self.od, self.id_)
        if self.bearing is None:
            other.setEnabled(True)
        if self.edge:
            # The selected edge fixes one diameter
            locked.setValue(self.edge_dia)
            locked.setEnabled(False)
            # The other diameter starts 15 mm away (both modes); afterwards it is only
            # reset when it ends up on the wrong side of the locked one
            if (
                mode_changed
                or (inner and self.od.value() <= self.edge_dia)
                or (not inner and self.id_.value() >= self.edge_dia)
            ):
                other.setValue(PB.other_diameter(self.edge_dia, inner))
        elif self.bearing is None:
            locked.setEnabled(True)

        self.fill_sizes()

    def options(self):
        return {
            "mode": self.mode.currentText(),
            "is_inner": self.edge_is.currentIndex() == 0,
            "reverse": self.reverse.isChecked(),
            "cage": self.cage.isChecked(),
            "balls": self.balls.isChecked(),
            "values": {
                "ID": self.id_.value(),
                "OD": self.od.value(),
                "Height": self.height.value(),
                "BallDiameter": self.ball.value(),
                "NumBalls": self.num_balls.value(),
                "CageThickness": self.cage_t.value(),
                "CageTopOffset": self.cage_top.value(),
                "PocketClearance": self.pocket_clr.value(),
                "PocketRise": self.pocket_rise.value(),
            },
        }

    # ------------------------------------------------------------ task panel protocol

    def getStandardButtons(self):
        return QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel  # no int(): PySide6 enums

    def accept(self):
        """Check the values first; on a problem, say so and keep the panel open."""
        o = self.options()
        try:
            PB.validate(o["values"], o["cage"], o["balls"])
        except ValueError as e:
            QtGui.QMessageBox.warning(self.form, TITLE, str(e))
            return False
        self._preview_timer.stop()
        self.preview.clear()
        if self.build(o):
            Gui.Control.closeDialog()
            return True
        self.update_preview()
        return False

    def reject(self):
        self._preview_timer.stop()
        self.preview.clear()
        Gui.Control.closeDialog()
        return True

    def build(self, opts):
        """Create the bearing from the panel's options. Returns False on failure."""
        if self.bearing is not None:
            doc = self.bearing.Document
        elif self.feature is not None:
            doc = self.feature.Document
        else:
            doc = App.ActiveDocument or App.newDocument("Bearing")
        split = True
        doc.openTransaction("Printable bearing")
        try:
            if self.bearing is not None:
                PB.convert_bearing(self.bearing, opts["values"], opts["cage"], opts["balls"])
            elif opts["mode"] == PB.GROOVE:
                before = len(self.body.Shape.Solids)
                PB.groove_body(self.feature, self.edge, opts["values"], opts["cage"], opts["balls"])
                split = len(self.body.Shape.Solids) > before
            else:
                placement = PB.frame_placement(self.edge) if self.edge else App.Placement()
                PB.create_races(
                    doc, placement, opts["values"], opts["reverse"], opts["cage"], opts["balls"]
                )
        except Exception as e:
            doc.abortTransaction()
            App.Console.PrintError(str(e) + "\n")
            QtGui.QMessageBox.warning(Gui.getMainWindow(), TITLE, str(e))
            return False
        doc.commitTransaction()
        if Gui.ActiveDocument and Gui.ActiveDocument.ActiveView:
            # the macro's SendMsgToActiveView("ViewFit") is gone in 1.1
            Gui.ActiveDocument.ActiveView.fitAll()
        if not split:
            msg = (
                "The groove did not split the body into separate inner and outer races. "
                "Check the diameters and the height (the groove must cut through the body), "
                "or edit them on BearingParameters."
            )
            App.Console.PrintWarning(msg + "\n")
            QtGui.QMessageBox.warning(Gui.getMainWindow(), TITLE, msg)
        return True


def open_panel(preset=None):
    """Read the selection and show the task panel. Returns the panel (or None).

    `preset`: (ID, OD, height) to start from, e.g. a size picked in Find bearing. With a
    selected edge, the diameter it locks stays the edge's.
    """

    def fail(msg):
        App.Console.PrintError(msg + "\n")
        QtGui.QMessageBox.warning(Gui.getMainWindow(), TITLE, msg)

    try:
        picked = get_selection()
    except ValueError as e:
        return fail(str(e))
    if picked and picked[0] == "bearing":
        panel = TaskPanel(bearing=picked[1])
        Gui.Control.showDialog(panel)
        return panel

    feature, edge, shape = picked if picked else (None, None, None)
    # "Groove selected body" only when the edge is on a PartDesign body we can measure
    measured = None
    body = PB.find_body(feature) if feature is not None else None
    if body is not None:
        try:
            measured = PB.measure_body(body, edge)
        except ValueError:
            measured = None
    # Creating races: the end of a shaft is the bearing's ID, a housing bore its OD
    create_inner = BRS.edge_side(shape, edge) != "outside" if shape is not None else True
    # The races are padded along the circle axis, whose sign is arbitrary: preset Reverse
    # so they go into the hole / onto the shaft (away from the face's outward normal)
    reverse = False
    if edge is not None and shape is not None:
        axis = App.Vector(edge.Curve.Axis)
        reverse = axis.dot(BRS.outward_normal(shape, edge)) > 0
    panel = TaskPanel(edge, measured, create_inner, reverse=reverse, feature=feature, body=body)
    if preset:
        panel.apply_preset(*preset)
    Gui.Control.showDialog(panel)
    return panel


class PrintableBearingCommand:
    def GetResources(self):
        return {
            "Pixmap": icon("PrintableBearing.svg"),
            "MenuText": "3D-printable bearing",
            "ToolTip": "3D-printable deep groove ball bearing: races, snap-in cage and balls as "
            "separate PartDesign bodies",
        }

    def IsActive(self):
        return App.ActiveDocument is not None and Gui.Control.activeDialog() is False

    def Activated(self):
        open_panel()


Gui.addCommand("Bearings_PrintableBearing", PrintableBearingCommand())
