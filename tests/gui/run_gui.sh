#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Run a FreeCAD GUI test script unattended.
#   tests/gui/run_gui.sh tests/gui/gui_smoke.py logfile [timeout_seconds]
# The workbench must be installed (linked into FreeCAD's Mod folder, see README.md).
# FREECAD names the FreeCAD GUI executable; by default the macOS app in /Applications,
# or `freecad` on the PATH.
# Waits until the script logs OK / FAILED / EXIT, then makes sure that FreeCAD process is
# gone (kills it after a short grace period, or at the timeout). Prints the log.
script="$1"; logf="$2"; timeout="${3:-180}"
if [ -n "$FREECAD" ]; then
  FC="$FREECAD"
elif [ -x /Applications/FreeCAD.app/Contents/MacOS/FreeCAD ]; then
  FC=/Applications/FreeCAD.app/Contents/MacOS/FreeCAD
else
  FC=freecad
fi
rm -f "$logf"
GUIKIT_LOG="$logf" "$FC" "$script" >"$logf.out" 2>&1 &
pid=$!
i=0
while [ $i -lt "$timeout" ]; do
  kill -0 $pid 2>/dev/null || break
  if [ -f "$logf" ] && grep -qE "^(EXIT|FAILED)$" "$logf"; then break; fi
  sleep 1; i=$((i + 1))
done
sleep 2
if kill -0 $pid 2>/dev/null; then
  echo "[run_gui] FreeCAD (pid $pid) still running after ${i}s, killing it"
  kill $pid 2>/dev/null; sleep 2; kill -9 $pid 2>/dev/null
fi
cat "$logf" 2>/dev/null
grep -iE "traceback" "$logf.out" >/dev/null && echo "[run_gui] tracebacks in FreeCAD output: $logf.out"
[ "$i" -ge "$timeout" ] && echo "[run_gui] TIMEOUT after ${timeout}s"
exit 0
