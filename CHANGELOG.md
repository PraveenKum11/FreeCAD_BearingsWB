# Changelog

All notable changes to the Bearings workbench. Versions follow
[semantic versioning](https://semver.org/): a minor version adds features, a patch
version fixes bugs, a major version may break existing documents or scripts.

## 1.1.1 (2026-10-17)

### Fixed

- No more flickering stripes inside bearings in section and clipping views. Shields and
  seals of deep groove bearings, the seals and ball retainer of linear bushings, and
  neighbouring cage segments shared faces with each other; they now keep a 0.01 mm gap.
  Outer dimensions and placement are unchanged.

## 1.1.0 (2026-10-17)

### Added

- **Fit allowance**: a hole modelled a little larger than a bearing (22.2 mm for a 608) or
  a shaft a little smaller than its bore (7.98 mm) now gets that bearing. The outside
  diameter may be up to the allowance smaller than a hole, the bore up to it larger than a
  shaft, never the other way; the closest size wins. 0.5 mm by default.
- **Settings** dialog (Bearing tools → Settings, gear icon) to change the fit allowance.
- `FitClearance` in the Bearing info group: the clearance left to the attached edge,
  negative if a size picked by hand doesn't fit.
- 3D-printable bearings list catalog sizes that fit the selected edge with the same
  allowance.
- **Bearing BOM → Create spreadsheet** writes the list to a new spreadsheet in the
  document, with a total row; each click adds a new sheet.

### Changed

- `Auto` only uses a standard size that fits the edge. Before, it took the closest size
  without a limit, so a 13 mm shaft got a 6001 (12 mm bore). An `Auto` bearing whose edge
  later changes to a size the series doesn't have shows an error on recompute.
- When no size fits, the message names the edge, the nearest sizes below and above, and
  what to do next. Other selected edges still get their bearings.

### Fixed

- Copied or duplicated bearings are labelled `608_001`, `608_002` instead of `609`, `610`.
  A second printable bearing of the same size gets `_001` too.
- The install instructions use the real clone URL.

## 1.0.0 (2026-10-14)

First public release.

- Standard bearings: deep groove series 60, 62, 63, 68, 69, MR and inch R, with shields,
  seals and flanges; angular contact 72 / 73 B; thrust 511; self-aligning 12 / 13 / 22 /
  23; cylindrical NU / NJ; tapered 302 / 303 / 320; needle HK / NK; AXK thrust needle
  assemblies.
- LM linear ball bushings: plain, long, round-flanged (LMF) and square-flanged (LMK).
- Snap to a hole or a shaft end; the bearing stays attached. `Invert` and `Offset`.
- Detail levels Envelope, Standard and Detailed.
- Find bearing: search by name, size, bore, outside diameter or height.
- 3D-printable bearings: races, cage and balls as separate PartDesign bodies with a live
  preview; groove an existing body; replace a standard bearing.
- Bearing BOM with CSV export, including the balls printable bearings need.
- Wiki published from `docs/`.
