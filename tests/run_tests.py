# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless test suite (unittest). Run from the repository root with FreeCAD's freecadcmd:

    path/to/freecadcmd tests/run_tests.py

On macOS freecadcmd is FreeCAD.app/Contents/Resources/bin/freecadcmd. To run only some
tests, set BEARINGS_TESTS to test names (comma separated), for example
BEARINGS_TESTS=test_printable or BEARINGS_TESTS=test_printable.PreviewMatchesBuild.

The process exits with status 0 when every test passes, 1 otherwise.
"""

import os
import sys
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
for path in (ROOT, TESTS):
    if path not in sys.path:
        sys.path.insert(0, path)


def main():
    loader = unittest.TestLoader()
    names = [n.strip() for n in os.environ.get("BEARINGS_TESTS", "").split(",") if n.strip()]
    if names:
        suite = loader.loadTestsFromNames(names)
    else:
        suite = loader.discover(TESTS, pattern="test_*.py", top_level_dir=TESTS)
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    sys.stdout.flush()
    # freecadcmd ignores SystemExit from a script, so leave with the status directly
    os._exit(0 if result.wasSuccessful() else 1)


main()
