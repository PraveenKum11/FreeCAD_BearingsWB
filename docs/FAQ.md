# FAQ

**The bearing doesn't move with my part.**
It follows the edge it is attached to (`BaseObject`). If the part was remodelled and the
edge got a new number, select the new edge and set `BaseObject` again (FreeCAD's
toponaming limitation, as in other workbenches).

**The flanged bearing sits on the wrong side.**
Toggle `Invert`. In a hole, a flanged bearing's flange rests on the face you clicked.

**Why are there no cages on roller bearings?**
They aren't modelled yet; Detailed looks like Standard for roller and needle bearings.

**Are the dimensions exact?**
Boundary dimensions follow the standards and were cross-checked (see [[Data sources]]);
internal details are computed, so they are representative, not a maker's drawing.

**Can I print a standard bearing?**
Use a [[Printable bearings|printable bearing]] of the same size: select the standard one
and run 3D-printable bearing to replace it.

**Will documents still open without the workbench?**
Printable bearings are plain PartDesign and open anywhere. Standard bearings are
FeaturePython objects and need the workbench to recompute.
