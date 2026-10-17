# SPDX-License-Identifier: GPL-3.0-or-later
"""Supplier search, closure insertion, command registration and a visual sample.

Run in a separate FreeCAD GUI process, like gui_smoke.py. Uses GUIKIT_LOG / GUIKIT_SHOTS.
Safe mode is supported: register this checkout's workbench if it is not installed.
"""

import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests" / "gui")]

import BearingBase
import BearingCatalog as BC
import BearingData as BD
from guikit import finish, log, log_exc, pump, shot

try:
    if "BearingsWorkbench" not in Gui.listWorkbenches():
        script = ROOT / "InitGui.py"
        exec(
            compile(script.read_text(encoding="utf-8"), str(script), "exec"),
            {"Workbench": Gui.Workbench, "Gui": Gui},
        )
    Gui.activateWorkbench("BearingsWorkbench")
    import BearingsCmd
    import BearingSearchGui as Search

    commands = set(Gui.listCommands())
    assert all("Bearings_Insert_" + s in commands for s in BD.SERIES)
    assert {s for _, _, group in BearingsCmd.GROUPS for s in group} == set(BD.SERIES)
    assert all((ROOT / "Icons" / ("Bearing_" + s + ".svg")).exists() for s in BD.SERIES)
    doc = App.newDocument("CatalogSmoke")
    for series in BD.SERIES:
        Gui.Selection.clearSelection()
        Gui.runCommand("Bearings_Insert_" + series, 0)
        created = Gui.Selection.getSelection()
        assert len(created) == 1 and created[0].Series == series, series
        assert created[0].Shape.isValid(), series
        doc.removeObject(created[0].Name)
    Gui.Selection.clearSelection()
    log("ok every menu series inserts a valid model", len(BD.SERIES))
    panel = Search.open_panel()
    for text, name, closure in (
        ("056 GRP 222", "UCP205", "Open"),
        ("056 SKF 543", "608-2RS", "2RS"),
        ("NN 3015 SKMSP", "NN3015K", "Open"),
        ("056 PRZ 631", "Ball6mm", "Open"),
    ):
        panel.name.setText(text)
        pump(0.2)
        assert len(panel.results) == 1, text
        panel.insert()
        obj = Gui.Selection.getSelection()[0]
        assert obj.FullDesignation == name and obj.Closure == closure
        assert obj.Shape.isValid()
        log("ok insertion", text, name)
    panel.name.setText("VKBA 542")
    pump(0.2)
    assert {r.name for _, r in panel.results} == {"VKBA542-1", "VKBA542-2"}
    assert panel.product_btn.isEnabled()
    panel.insert_product()
    assert len(Gui.Selection.getSelection()) == 2
    panel.name.setText("VKBA 686")
    pump(0.2)
    panel.insert_product()
    assert len(Gui.Selection.getSelection()) == 2
    panel.name.setText("139 FRV 138")
    pump(0.2)
    assert len(panel.results) == 11 and panel.insert_btn.isEnabled()
    assert panel.product_btn.isEnabled() and "450 parts" in panel.product_btn.text()
    for product in BC.products():
        article = product["SKU"]
        expected = BC.components(product)
        panel.name.setText(article)
        pump(0.01)
        assert panel.results and panel.insert_btn.isEnabled(), article
        button = panel.product_btn if len(expected) > 1 else panel.insert_btn
        assert button.isEnabled(), article
        button.click()
        created = Gui.Selection.getSelection()
        assert Counter((o.Series, str(o.Designation), str(o.Closure)) for o in created) == Counter(
            expected
        ), article
        assert all(o.Shape.isValid() and o.SupplierArticle == article for o in created), article
        Gui.Selection.clearSelection()
        for obj in created:
            doc.removeObject(obj.Name)
        log("ok article GUI insertion", article, len(expected))
    log("ok all supplier articles inserted through GUI", len(BC.products()))
    Gui.Control.closeDialog()
    for obj in doc.Objects:
        obj.Visibility = False
    for series, pos in (
        ("UCP", (0, 0)),
        ("UCFL", (190, 0)),
        ("222", (0, 200)),
        ("NN30", (190, 200)),
        ("Wheel", (380, 200)),
        ("KR", (380, 0)),
    ):
        b = BearingBase.make_bearing(series, doc=doc)
        b.Placement.Base = App.Vector(pos[0], pos[1], 0)
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.activeDocument().activeView().viewIsometric()
    Gui.activeDocument().activeView().fitAll()
    pump(0.2)
    output = Path(os.environ.get("GUIKIT_SHOTS", tempfile.gettempdir()))
    output.mkdir(parents=True, exist_ok=True)
    shot(str(output / "catalog-smoke.png"))
    log("OK catalog GUI smoke")
except Exception:
    log_exc()
    finish(1)
else:
    finish(0)
