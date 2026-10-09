# SPDX-License-Identifier: LGPL-2.1-or-later
"""Task panel and command for 3D-printable bearings (ported from the macro dialog)."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

import BRselection as BRS
import PrintableBearing as PB
from BRutils import icon, translate

TITLE = "Printable Bearing"
CUSTOM = "Custom"


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


class TaskPanel:
    """One panel for both modes, as the macro's dialog."""

    def __init__(self, edge=None, measured=None, create_inner=True, bearing=None, reverse=False):
        """`measured`: measure_body() result if the selected body can be grooved, else None.
        `create_inner`: default for "Selected edge is" when creating races.
        `bearing`: a standard Bearing to replace (its size and placement are used).
        `reverse`: default for "Reverse direction" (set so the races go into the material)."""
        self.edge, self.measured, self.create_inner = edge, measured, create_inner
        self.bearing = bearing
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
            return s

        self.mode = QtGui.QComboBox()
        if measured:
            self.mode.addItem(PB.GROOVE)
        self.mode.addItem(PB.CREATE)
        row(form, "Races:", self.mode, PB.UI_HELP["Races"])

        self.edge_is = QtGui.QComboBox()
        self.edge_is.addItems(["Inner diameter", "Outer diameter"])
        if edge:
            row(form, "Selected edge (Ø %.2f) is:" % self.edge_dia, self.edge_is, PB.UI_HELP["EdgeIs"])

        self.size = QtGui.QComboBox()
        row(form, "Catalog size:", self.size, PB.UI_HELP["Size"])

        d = self.edge_dia or 20.0
        self.id_ = spin(d)
        self.od = spin(round(d * 1.6, 2))
        self.height = spin(round(d * 0.4, 2), prefix="")
        row(form, "Inner diameter:", self.id_, PB.BEARING_DOCS["ID"])
        row(form, "Outer diameter:", self.od, PB.BEARING_DOCS["OD"])
        row(form, "Height:", self.height, PB.BEARING_DOCS["Height"])

        self.reverse = QtGui.QCheckBox("Reverse direction")
        self.reverse.setChecked(reverse)
        row(form, "", self.reverse, PB.UI_HELP["Reverse"])

        self.ball_preset = QtGui.QComboBox()
        self.ball_preset.addItem(CUSTOM)
        for label, dia in PB.BALL_PRESETS:
            self.ball_preset.addItem(label, dia)
        row(form, "Ball preset:", self.ball_preset, PB.UI_HELP["BallPreset"])
        self.ball = spin(PB.DEFAULT_BALL_DIAMETER)
        row(form, "Ball diameter:", self.ball, PB.BEARING_DOCS["BallDiameter"])
        self.num_balls = QtGui.QSpinBox()
        self.num_balls.setRange(1, 1000)
        self.num_balls.setValue(PB.DEFAULT_NUM_BALLS)
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
        row(form, None, self.cage, PB.UI_HELP["Cage"])

        self.balls = QtGui.QCheckBox("Create balls")
        self.balls.setChecked(False)
        row(form, "Balls:", self.balls, PB.UI_HELP["Balls"])

        self.mode.currentIndexChanged.connect(self.refresh)
        self.edge_is.currentIndexChanged.connect(self.refresh)
        for s in (self.id_, self.od, self.height):
            s.editingFinished.connect(self.fit_sizes)
            s.editingFinished.connect(self.sync_size)
        self.size.currentIndexChanged.connect(self.apply_size)
        self.ball_preset.currentIndexChanged.connect(self.apply_ball_preset)
        self.ball.valueChanged.connect(self.limit_cage)
        self.ball.valueChanged.connect(self.sync_ball_preset)

        if bearing is not None:
            # Replace a standard bearing: its size is fixed, it sits where the bearing was
            self.id_.setValue(bearing.BoreDiameter.Value)
            self.od.setValue(bearing.OuterDiameter.Value)
            self.height.setValue(bearing.Width.Value)
            for w in (self.id_, self.od, self.height, self.size, self.reverse):
                w.setEnabled(False)
        self.refresh()

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
        self.fit_sizes()

    def apply_preset(self, d, D, B):
        """Start from a given size; a diameter locked by the selected edge is kept."""
        if self.mode.currentText() == PB.GROOVE:
            self.mode.setCurrentIndex(self.mode.findText(PB.CREATE))
        for w, val in ((self.id_, d), (self.od, D), (self.height, B)):
            if w.isEnabled():
                w.setValue(val)
        self.fit_sizes(reset=True)
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
            self.fit_sizes()

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

    def limit_cage(self, *_):
        """The cage can be at most as thick as the gap between the races (ball Ø / 2)."""
        import math

        self.cage_t.setMaximum(math.floor(self.ball.value() / 2 * 100) / 100)

    def fit_sizes(self, reset=False):
        v = PB.fit_values(self.options()["values"], reset)
        self.ball.setValue(v["BallDiameter"])
        self.cage_t.setValue(v["CageThickness"])
        self.num_balls.setValue(v["NumBalls"])

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
            if mode_changed and groove and m["other"]:
                other.setValue(m["other"])
            elif inner and self.od.value() <= self.edge_dia:
                self.od.setValue(round(self.edge_dia * 1.6, 2))
            elif not inner and self.id_.value() >= self.edge_dia:
                self.id_.setValue(round(self.edge_dia / 1.6, 2))
        elif self.bearing is None:
            locked.setEnabled(True)

        # A new mode starts from fresh sizes; otherwise only fix what no longer fits
        self.fit_sizes(reset=mode_changed)
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
        if build(o, self.edge, self.measured, self.bearing):
            Gui.Control.closeDialog()
            return True
        return False

    def reject(self):
        Gui.Control.closeDialog()
        return True


# set by Activated(): what the panel builds on
_context = {}


def build(opts, edge, measured, bearing):
    """Create the bearing from the panel's options. Returns False on failure."""
    feature, body = _context.get("feature"), _context.get("body")
    doc = feature.Document if feature else (App.ActiveDocument or App.newDocument("Bearing"))
    split = True
    doc.openTransaction("Printable bearing")
    try:
        if bearing is not None:
            PB.convert_bearing(bearing, opts["cage"], opts["balls"], opts["values"])
        elif opts["mode"] == PB.GROOVE:
            before = len(body.Shape.Solids)
            PB.groove_body(feature, edge, opts["values"], opts["cage"], opts["balls"])
            split = len(body.Shape.Solids) > before
        else:
            placement = PB.frame_placement(edge) if edge else App.Placement()
            PB.create_races(doc, placement, opts["values"], opts["reverse"], opts["cage"], opts["balls"])
    except Exception as e:
        doc.abortTransaction()
        App.Console.PrintError(str(e) + "\n")
        QtGui.QMessageBox.warning(Gui.getMainWindow(), TITLE, str(e))
        return False
    doc.commitTransaction()
    if Gui.ActiveDocument:
        Gui.SendMsgToActiveView("ViewFit")
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
    _context.clear()
    if picked and picked[0] == "bearing":
        panel = TaskPanel(bearing=picked[1])
        _context["feature"] = picked[1]
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
    _context.update(feature=feature, body=body)
    panel = TaskPanel(edge, measured, create_inner, reverse=reverse)
    if preset:
        panel.apply_preset(*preset)
    Gui.Control.showDialog(panel)
    return panel


class PrintableBearingCommand:
    def GetResources(self):
        return {
            "Pixmap": icon("PrintableBearing.svg"),
            "MenuText": translate("Bearings", "3D-printable bearing"),
            "ToolTip": translate(
                "Bearings",
                "3D-printable deep groove ball bearing: races, snap-in cage and balls as "
                "separate PartDesign bodies.\nSelect a circular edge (shaft end, housing bore "
                "or a bore to groove), a standard bearing to replace, or nothing.",
            ),
        }

    def IsActive(self):
        return App.ActiveDocument is not None and Gui.Control.activeDialog() is False

    def Activated(self):
        open_panel()


Gui.addCommand("Bearings_PrintableBearing", PrintableBearingCommand())
