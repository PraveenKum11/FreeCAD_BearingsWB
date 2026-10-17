# SPDX-License-Identifier: GPL-3.0-or-later
"""GUI regression run: tests/gui/run_gui.sh tests/gui/gui_smoke.py <log> [timeout]

Drives the Find bearing and printable bearing panels in a real FreeCAD GUI session.
Screenshots go to $GUIKIT_SHOTS (default: the temp directory).
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # the workbench modules
import FreeCAD as App  # noqa: E402
import FreeCADGui as Gui  # noqa: E402
import Part  # noqa: E402

import BRselection as BRS  # noqa: E402
from guikit import finish, log, log_exc, pump, shot  # noqa: E402

OUT = os.environ.get("GUIKIT_SHOTS") or tempfile.gettempdir()
problems = []


def expect(cond, msg):
    log(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        problems.append(msg)


def circle_edge(shape, r, z):
    for i, e in enumerate(shape.Edges, 1):
        if (
            BRS.is_circular_edge(e)
            and abs(e.Curve.Radius - r) < 1e-6
            and abs(BRS.center_of(e.Curve).z - z) < 1e-6
        ):
            return "Edge%d" % i
    raise AssertionError("edge r=%g z=%g not found" % (r, z))


try:
    Gui.activateWorkbench("BearingsWorkbench")
    import BearingSearchGui as SG
    import PrintableBearingGui as PG

    cmds = [c for c in Gui.listCommands() if c.startswith("Bearings_")]
    expect(
        {"Bearings_PrintableBearing", "Bearings_Search", "Bearings_Insert_60"} <= set(cmds),
        "commands registered",
    )
    doc = App.newDocument("Smoke")
    sg = Gui.ActiveDocument.ActiveView.getSceneGraph()
    n0 = sg.getNumChildren()

    # printable on a hole edge: preview, catalog size, preset, direction into the plate
    plate = doc.addObject("Part::Feature", "Plate")
    plate.Shape = Part.makeBox(40, 40, 10, App.Vector(-20, -20, 0)).cut(
        Part.makeCylinder(11, 12, App.Vector(0, 0, -1))
    )
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, "Plate", circle_edge(plate.Shape, 11, 10))
    p = PG.open_panel()
    pump(0.3)
    expect(sg.getNumChildren() - n0 == 1, "create-mode preview shown")
    p.size.setCurrentIndex(
        [i for i in range(p.size.count()) if p.size.itemText(i).startswith("608")][0]
    )
    p.ball_preset.setCurrentIndex(
        [i for i in range(p.ball_preset.count()) if "4.5" in p.ball_preset.itemText(i)][0]
    )
    expect(p.reverse.isChecked(), "reverse preset so races go into the hole")
    pump(0.3)
    expect(
        p.num_balls.value() == 10 and "between 1 and 9" in p.status.text(),
        "4.5 mm balls: count not changed, status says 1..9: " + p.status.text(),
    )
    p.num_balls.setValue(9)
    pump(0.3)
    expect(not p.status.isVisible(), "status clears with 9 balls")
    expect(p.accept() is True, "printable accepted")
    pump(0.2)
    expect(sg.getNumChildren() == n0, "preview removed after OK")
    part = [o for o in doc.Objects if o.TypeId == "App::Part"][0]
    races = [o for o in part.Group if o.Label == "Races"][0]
    bb = races.Shape.BoundBox
    expect(part.Label == "Bearing 608 (22x8x7)", "label " + part.Label)
    expect(
        abs(bb.ZMin + part.Placement.Base.z - 3) < 0.01
        and abs(bb.ZMax + part.Placement.Base.z - 10) < 0.01,
        "races inside the plate",
    )

    # search and insert, then printable from search
    Gui.Selection.clearSelection()
    s = SG.open_panel()
    s.name.setText("F688-2RS")
    pump(0.1)
    expect(s.count.text() == "1 bearing", "search F688-2RS")
    s.insert()
    std = [o for o in doc.Objects if hasattr(o, "FullDesignation")][0]
    expect((std.Label, std.Flanged, std.Closure) == ("F688-2RS", True, "2RS"), "inserted F688-2RS")
    # linear bushing with a square flange: inserted as LMK8UU, no printable version
    s.name.setText("LMK8UU")
    pump(0.1)
    expect(
        s.table.item(0, 0).text() == "LMK8UU", "search LMK8UU shows " + s.table.item(0, 0).text()
    )
    expect(not s.print_btn.isEnabled(), "no printable version of a linear bushing")
    s.insert()
    lm = [o for o in doc.Objects if getattr(o, "Series", "") == "LM"][0]
    expect(
        (lm.Label, lm.Flanged, lm.FlangeShape) == ("LMK8UU", True, "Square"),
        "inserted %s %s %s" % (lm.Label, lm.Flanged, lm.FlangeShape),
    )
    doc.removeObject(lm.Name)
    expect(
        "Bearings_Insert_LM" in Gui.listCommands() and "Bearings_Insert_R" in Gui.listCommands(),
        "LM and R insert commands",
    )
    s.name.setText("")
    s.D.setValue(22)
    s.table.selectRow(
        [r for r in range(s.table.rowCount()) if s.table.item(r, 0).text() == "608"][0]
    )
    s.printable()
    pump(0.3)
    expect(bool(Gui.Control.activeDialog()), "printable panel opened from search")
    Gui.Control.closeDialog()
    pump(0.2)

    # convert a standard bearing
    std.Placement = App.Placement(App.Vector(70, 0, 0), App.Rotation())
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(std)
    p3 = PG.open_panel()
    pump(0.3)
    expect(sg.getNumChildren() - n0 == 1, "convert preview shown")
    # defaults stay as they are: 4 mm balls don't fit a 688 (wall 4 mm) -> reported, refused
    expect(
        p3.ball.value() == 4.0 and p3.num_balls.value() == 10, "convert keeps default ball/count"
    )
    expect(
        p3.status.isVisible() and "Ball diameter" in p3.status.text(),
        "status explains: " + p3.status.text(),
    )
    from PySide import QtGui as _QG

    import guikit

    n_dialogs = len(guikit.dialogs)
    expect(p3.accept() is False, "invalid values refused")
    # the warning is answered by guikit's message box stub: no window, no click needed
    warned = guikit.dialogs[n_dialogs:]
    expect(
        len(warned) == 1 and "Ball diameter" in warned[0],
        "OK on invalid values warns once: %s" % warned,
    )
    open_dialogs = [
        type(t).__name__
        for t in _QG.QApplication.topLevelWidgets()
        if t.isVisible() and isinstance(t, _QG.QDialog)
    ]
    expect(not open_dialogs and p3.form.isVisible(), "no dialog left open, panel still there")
    p3.ball_preset.setCurrentIndex(
        [i for i in range(p3.ball_preset.count()) if p3.ball_preset.itemText(i).startswith("3 mm")][
            0
        ]
    )
    pump(1.0)
    log("  after preset: ball", p3.ball.value(), "timer active:", p3._preview_timer.isActive())
    expect(
        not p3.status.isVisible(),
        "status clears once values fit (%r, ball %g)" % (p3.status.text(), p3.ball.value()),
    )
    expect(p3.accept() is True and not std.Visibility, "converted standard bearing")

    # groove a PartDesign hub with preview
    body = doc.addObject("PartDesign::Body", "Hub")
    disc = body.newObject("PartDesign::AdditiveCylinder", "Disc")
    disc.Radius, disc.Height = 20, 8
    bore = body.newObject("PartDesign::SubtractiveCylinder", "Bore")
    bore.Radius, bore.Height = 5, 8
    body.Placement = App.Placement(App.Vector(0, 70, 0), App.Rotation())
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, "Hub", "Bore." + circle_edge(bore.Shape, 5, 8))
    p4 = PG.open_panel()
    pump(0.3)
    expect(p4.mode.currentText() == "Groove selected body", "groove mode offered")
    expect(sg.getNumChildren() - n0 == 1, "groove preview shown")
    p4.od.setValue(30)
    pump(0.4)
    log("  status:", p4.status.text() or "(valid)")
    shot(os.path.join(OUT, "smoke_groove_preview.png"))
    log("  shot saved, accepting")
    ok = p4.accept()
    log("  accept returned", ok)
    expect(ok is True and len(body.Shape.Solids) == 2, "hub grooved into 2 races")
    expect(sg.getNumChildren() == n0, "no preview left behind")
    expect(not [o.Label for o in doc.Objects if "Invalid" in o.State], "no invalid objects")
    # --- typing does not update anything until Enter / leaving the field
    from PySide import QtCore, QtGui
    from PySide6.QtTest import QTest  # not in FreeCAD's PySide shim

    plate2 = doc.addObject("Part::Feature", "Plate2")
    plate2.Shape = Part.makeBox(40, 40, 10, App.Vector(-20, -80, 0)).cut(
        Part.makeCylinder(11, 12, App.Vector(0, -60, -1))
    )
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, "Plate2", circle_edge(plate2.Shape, 11, 10))
    p5 = PG.open_panel()
    pump(0.3)
    calls = []
    orig = p5.update_preview
    p5.update_preview = lambda: (calls.append(1), orig())
    edit = p5.id_.lineEdit()
    p5.id_.setFocus()
    pump(0.1)
    edit.selectAll()
    QTest.keyClicks(edit, "12.5")
    pump(0.5)
    expect(len(calls) == 0, "no preview update while typing (%d)" % len(calls))
    # leaving the field commits the value (Enter would press the task panel's OK, as in
    # every FreeCAD task panel)
    log(
        "  typed text %r, value still %g, app active: %s"
        % (edit.text(), p5.id_.value(), QtGui.QApplication.activeWindow() is not None)
    )
    # leave the field: a real focus-out event, which works even when FreeCAD isn't the
    # active app (Tab only moves focus inside an active window)
    QtGui.QApplication.sendEvent(
        p5.id_, QtGui.QFocusEvent(QtCore.QEvent.FocusOut, QtCore.Qt.TabFocusReason)
    )
    pump(0.5)
    expect(
        len(calls) == 1 and abs(p5.id_.value() - 12.5) < 1e-9,
        "one update on leaving the field (%d)" % len(calls),
    )
    # ball / cage / count stay at defaults whatever ID/OD do
    before = (
        p5.ball.value(),
        p5.num_balls.value(),
        p5.cage_t.value(),
        p5.cage_top.value(),
        p5.pocket_clr.value(),
        p5.pocket_rise.value(),
    )
    p5.id_.setValue(18.5)  # 1.75 mm wall: nothing fits any more
    p5.size.setCurrentIndex(
        [i for i in range(p5.size.count()) if p5.size.itemText(i).startswith("608")][0]
    )
    pump(0.4)
    after = (
        p5.ball.value(),
        p5.num_balls.value(),
        p5.cage_t.value(),
        p5.cage_top.value(),
        p5.pocket_clr.value(),
        p5.pocket_rise.value(),
    )
    expect(
        before == after == (4.0, 10, 1.5, 0.5, 0.35, 0.6),
        "ball/cage values untouched: %s" % (after,),
    )
    expect(not p5.status.isVisible(), "608 with defaults is valid")
    p5.reject()
    pump(0.2)
    expect(sg.getNumChildren() == n0, "no preview left after Cancel")
    # bill of materials of everything built above
    import BearingBOMGui

    bom = BearingBOMGui.open_panel()
    pump(0.3)
    items = {r["Item"]: r["Quantity"] for r in bom.items}
    # the F688-2RS was replaced by a printable bearing above, which hid it
    expect("F688-2RS" not in items, "BOM skips the hidden, replaced bearing: %s" % items)
    bom.skip_hidden.setChecked(False)
    pump(0.2)
    items = {r["Item"]: r["Quantity"] for r in bom.items}
    expect(items.get("F688-2RS") == 1, "BOM lists it when hidden objects are included")
    expect(
        any(k.startswith("Printable bearing") for k in items), "BOM lists the printable bearings"
    )
    expect(bom.table.rowCount() == len(bom.items) and bom.save_btn.isEnabled(), "BOM table filled")

    def sheets():
        return [o for o in doc.Objects if o.TypeId == "Spreadsheet::Sheet"]

    bom.sheet_btn.click()
    pump(0.3)
    sheet = sheets()[-1] if sheets() else None
    expect(
        sheet is not None and sheet.get("A1") == "Item" and Gui.Selection.isSelected(sheet),
        "BOM spreadsheet written and selected",
    )
    bom.sheet_btn.click()
    pump(0.3)
    expect(len(sheets()) == 2, "a second click adds a second sheet (%d)" % len(sheets()))
    bom.reject()
    pump(0.2)
    Gui.ActiveDocument.setEdit(sheet.Name)
    pump(0.5)
    Gui.getMainWindow().grab().save(os.path.join(OUT, "bom-sheet.png"))
    Gui.ActiveDocument.resetEdit()
    pump(0.2)
    expect(
        {"Bearings_Insert_72", "Bearings_Insert_73", "Bearings_Insert_511", "Bearings_BOM"}
        <= set(Gui.listCommands()),
        "angular, thrust and BOM commands",
    )
    # v0.4: one toolbar drop-down per family
    import BearingsCmd

    expect(
        set(BearingsCmd.GROUP_COMMANDS) <= set(Gui.listCommands())
        and "Bearings_Insert_NU2" in Gui.listCommands(),
        "family drop-downs registered",
    )
    from PySide import QtGui as _QG2

    bars = [
        t for t in Gui.getMainWindow().findChildren(_QG2.QToolBar) if t.windowTitle() == "Bearings"
    ]
    n_buttons = len([a for a in bars[0].actions() if a.isVisible()]) if bars else 0
    expect(n_buttons == len(BearingsCmd.GROUPS), "Bearings toolbar: %d buttons" % n_buttons)

    # settings dialog: the fit allowance, used by the printable bearing's catalog sizes
    import BearingData as BD
    import BearingSettingsGui

    expect("Bearings_Settings" in Gui.listCommands(), "settings command registered")
    prefs = App.ParamGet(BD.PREFS)
    saved = prefs.GetFloat("FitAllowance", BD.DEFAULT_FIT_ALLOWANCE)
    try:
        dlg = BearingSettingsGui.SettingsDialog(Gui.getMainWindow())
        dlg.allowance.setValue(0.0)
        dlg.accept()
        expect(BD.fit_allowance() == 0.0, "settings dialog saves the allowance")
        loose = App.newDocument("Loose")
        plate2 = loose.addObject("Part::Feature", "Plate")
        plate2.Shape = Part.makeBox(40, 40, 10, App.Vector(-20, -20, 0)).cut(
            Part.makeCylinder(11.1, 12, App.Vector(0, 0, -1))
        )
        loose.recompute()

        def printable_sizes():
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(loose.Name, "Plate", circle_edge(plate2.Shape, 11.1, 10))
            panel = PG.open_panel()
            pump(0.2)
            names = [panel.size.itemText(i).split()[0] for i in range(panel.size.count())]
            return panel, names

        p6, names = printable_sizes()
        expect("608" not in names, "no allowance: no catalog size for a 22.2 mm hole")
        p6.reject()
        pump(0.2)
        dlg.defaults()
        dlg.accept()
        p6, names = printable_sizes()
        expect("608" in names and "6201" not in names, "0.5 mm allowance lists 608")
        p6.size.setCurrentIndex(names.index("608"))
        pump(0.2)
        expect(abs(p6.od.value() - 22) < 1e-6, "catalog 608 sets OD 22 in the 22.2 hole")
        p6.reject()
        pump(0.2)
        App.closeDocument(loose.Name)
    finally:
        prefs.SetFloat("FitAllowance", saved)

    log("RESULT", "PASS" if not problems else "FAIL (%d)" % len(problems))
    log("OK")
except Exception:
    log_exc()
finally:
    finish()
