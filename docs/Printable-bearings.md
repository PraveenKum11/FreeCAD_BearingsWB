# Printable bearings

**Bearing tools → 3D-printable bearing** designs a deep groove ball bearing to print:
the inner and outer races, a snap-in cage and, if you want them, the balls. Use bought
steel balls or airsoft BBs; everything else comes off the printer.

![Printable bearing cut away and turning](images/printable-turntable.gif)

## Step by step

![Select a hole edge, open the panel, pick 6808 and 4.5 mm balls, set 24 balls, OK](images/printable-workflow.gif)

1. Select a circular edge (a hole, a shaft end, a bore to groove, or a standard bearing
   to replace), or nothing to build at the origin.
2. Run the command. The task panel opens next to the 3D view, and a **live preview**
   shows the inner and outer diameter as labelled rings and a see-through bearing.
3. Pick a **catalog size** (608, 625, 6204, …; with a selected edge, only sizes that fit
   it, allowing the fit allowance from **Bearing tools → Settings**, so a 22.2 mm hole
   still lists the 608) or type ID, OD and height.
4. Pick a **ball preset** (3 mm, 1/8", 4 mm, 4.5 mm BB, 5 mm, 6 mm airsoft = 5.95 mm,
   6 mm, 1/4") or type the ball diameter, and the number of balls. A red status line says
   what doesn't fit; nothing is resized behind your back.
5. OK.

![The task panel next to the 3D view, previewing a 608 in a 22 mm hole](images/printable-panel.png)

## Three ways to start

- **Create races**: a new bearing at the edge or at the origin, in a Part named after
  its size ("Bearing 608 (22x8x7)"). Reverse direction is preset so it goes into the hole
  or onto the shaft.
- **Groove selected body**: select the bore of a PartDesign body; the ball groove is cut
  into it and your part becomes the outer race (pulleys, wheels, gears with a built-in
  bearing).

  ![A disc grooved so that it becomes the outer race](images/groove-body.png)

- **Replace a standard bearing**: select one and run the command; the printable bearing
  takes its size and place, and the standard one is hidden.

  ![A standard 6204-2RS and the printable 6204 that replaces it](images/convert.png)

## The parts

Races, cage and balls are separate PartDesign bodies, so each exports and prints on its
own. They are plain PartDesign features driven by expressions, so the bearing keeps
working in FreeCAD without the workbench.

![The Races, Cage and Balls bodies](images/printable-bodies.png)

## Changing it later

Every value lives on the **BearingParameters** datum in the races body:

| Parameter | Meaning |
|---|---|
| `ID`, `OD`, `Height` | Bore, outside diameter, axial width |
| `BallDiameter`, `NumBalls` | The balls; the gap between the races is half the ball diameter |
| `CageThickness` | Radial cage thickness, at most the gap |
| `CageTopOffset` | Larger = shorter cage |
| `PocketClearance` | Extra pocket diameter so the balls turn freely |
| `PocketRise` | Smaller = narrower pocket mouth, the balls snap in |

For new races, the **PrintableBearing** object next to the bodies keeps the Part's label
in step with the size and flags values that don't work.

The design comes from the
[DeepGrooveBallBearing macro](https://github.com/PraveenKum11/freecad-deep-groove-ball-bearing),
which is still available for printing bearings without the whole workbench.
