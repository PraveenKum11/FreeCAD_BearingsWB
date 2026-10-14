# SPDX-License-Identifier: GPL-3.0-or-later
"""Helpers for GUI test scripts run by tests/gui/run_gui.sh.

Usage in a script next to this file:
    import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from guikit import log, pump, shot, finish
    try:
        ...
        log("OK")
    except Exception:
        log_exc()
    finally:
        finish()

finish() closes every document WITHOUT saving and exits the process immediately, so the
"save changes?" dialog can never block an unattended run.
"""

import os
import tempfile
import time
import traceback

LOG = os.environ.get("GUIKIT_LOG") or os.path.join(tempfile.gettempdir(), "guikit.log")
_f = open(LOG, "w")
dialogs = []  # texts of message boxes answered and modal dialogs closed by the guard


def _close_modals():
    """Close any modal dialog (message boxes, save prompts) so a run never blocks."""
    from PySide import QtGui

    found = []
    w = QtGui.QApplication.activeModalWidget()
    if w is not None:
        found.append(w)
    # window-modal message boxes (macOS sheets) are not reported as the active modal
    # widget, so also look for any visible dialog among the top-level windows
    for t in QtGui.QApplication.topLevelWidgets():
        if t.isVisible() and isinstance(t, (QtGui.QMessageBox, QtGui.QDialog)) and t not in found:
            if t.isModal() or isinstance(t, QtGui.QMessageBox):
                found.append(t)
    for w in found:
        text = w.text() if isinstance(w, QtGui.QMessageBox) else w.windowTitle()
        dialogs.append(text)
        log("[guard] closed dialog:", text.replace("\n", " ")[:200])
        w.reject() if hasattr(w, "reject") else w.close()


def install_modal_guard(interval_ms=300):
    from PySide import QtCore

    global _guard
    _guard = QtCore.QTimer()
    _guard.timeout.connect(_close_modals)
    _guard.start(interval_ms)


def install_message_box_stubs():
    """Answer QMessageBox.warning() & co. without showing anything.

    On macOS, Qt shows these static message boxes as native alerts, which aren't Qt
    widgets: the modal guard can't find or close them, and a run waits for a click. In
    test runs they log their text, record it in `dialogs` and return at once (OK, or the
    given default button). Other dialogs are kept non-native so the guard can close them.
    """
    from PySide import QtCore, QtGui

    QtGui.QApplication.setAttribute(QtCore.Qt.AA_DontUseNativeDialogs, True)
    box = QtGui.QMessageBox

    def stub(kind, default):
        def answer(parent, title, text, buttons=None, default_button=None, *args, **kwargs):
            dialogs.append(text)
            log("[guard] %s message box: %s" % (kind, str(text).replace("\n", " ")[:200]))
            return default_button or default

        return staticmethod(answer)

    box.warning = stub("warning", box.Ok)
    box.critical = stub("critical", box.Ok)
    box.information = stub("information", box.Ok)
    box.question = stub("question", box.Yes)


try:
    install_message_box_stubs()
    install_modal_guard()
except Exception:  # not in a GUI session
    pass


def log(*args):
    _f.write(" ".join(str(a) for a in args) + "\n")
    _f.flush()


def log_exc():
    log(traceback.format_exc())
    log("FAILED")


def pump(seconds):
    """Let the GUI process events (and redraw) for a while."""
    import FreeCADGui as Gui

    end = time.time() + seconds
    while time.time() < end:
        Gui.updateGui()


def shot(path, width=1200, height=800, iso=True):
    import FreeCADGui as Gui

    view = Gui.activeDocument().activeView()
    if iso:
        view.viewIsometric()
    pump(0.3)
    view.fitAll()
    pump(0.5)  # saveImage before a redraw gives a blank image
    view.saveImage(path, width, height, "White")


def finish(code=0):
    import FreeCAD as App

    try:
        import FreeCADGui as Gui

        if Gui.Control.activeDialog():
            Gui.Control.closeDialog()
    except Exception:
        pass
    for name in list(App.listDocuments()):
        try:
            App.closeDocument(name)  # no save prompt from the Python API
        except Exception:
            pass
    log("EXIT")
    _f.close()
    os._exit(code)  # skip Qt's close event (and its dialogs) entirely
