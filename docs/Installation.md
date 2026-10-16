# Installation

The workbench needs **FreeCAD 1.0 or newer** (tested with 1.1).

## By hand

Until the workbench is in the Addon Manager, put the repository in FreeCAD's `Mod`
folder as `Bearings` and restart FreeCAD:

```sh
cd "<FreeCAD user data>/Mod"
git clone https://github.com/PraveenKum11/FreeCAD_BearingsWB.git Bearings
```

To find the folder, type `App.getUserAppDataDir()` in FreeCAD's Python console. It is,
for example, `~/Library/Application Support/FreeCAD/v1-1/` on macOS,
`~/.local/share/FreeCAD/v1-1/` on Linux and `%APPDATA%\FreeCAD\v1-1\` on Windows; `Mod`
is inside it (create it if it's missing).

After the restart, pick **Bearings** in the workbench selector.

![The Bearings and Bearing tools toolbars](images/wiki-toolbars.png)

## Updating

```sh
cd "<FreeCAD user data>/Mod/Bearings"
git pull
```

Restart FreeCAD afterwards. Documents made with an older version open and recompute
unchanged; new properties are added when a document is opened.

## For development

Link your clone instead of copying it, so FreeCAD loads your working copy (run from the
repository root):

```sh
ln -s "$PWD" "$HOME/Library/Application Support/FreeCAD/v1-1/Mod/Bearings"
```

See [[Development]].
