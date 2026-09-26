# CNC Box Creator

A desktop tool that turns box dimensions into CNC-ready cut files. Enter stock
thickness, tool diameter, joint sizing, and panel options in a GUI; get back a
folder of labeled SVG toolpath files — one per part plus a nested master layout —
ready to import into Carbide Create (or any CAM package that reads SVG) and cut
on a Shapeoko-class router.

Built to fabricate museum-style **shadowbox frames**: four rails joined with CNC-cut
box (finger) joints, a rabbeted front bezel with a display window, and a rabbeted
back panel. The project grew around a particular build for a kinetic artwork by artist
Joel Silverman — so it also supports motor pockets, access hatches, and cleats.

## What it generates

Each run writes a versioned output folder (`Box SVGs vNNN/`) containing:

- **Per-part SVGs** — perimeter, rabbet, and window/pocket operations as separate
  files per part (left/right/top/bottom rails, front bezel, back panel), so each
  toolpath can be assigned its own depth and tool in CAM.
- **A combined master layout** — all parts bin-packed onto 48×48-inch artboards
  (auto-rotated for best fit, expandable to 48×96). Each part's paths are grouped
  under its name, and each path's colour and name give the toolpath to apply:
  outside cut, hole, rabbet pocket, inside window cut or score. The layout carries
  no text.
- **`config.json`** — the exact parameters that produced the run, so any output
  set can be regenerated or audited later.
- **A Blender mockup script** (`OPEN_ME_IN_BLENDER.*.py`) that assembles the cut
  parts into a 3D preview of the finished box.

## Running it

```
cd "CNC Plans"
../venv/bin/python3 cnc_generator.py
```

Requires Python 3 with tkinter (present in the standard python.org installers)
and matplotlib, listed in `requirements.txt`. Create the project's own Python
environment once, from the project folder:

```
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

If a package fails to load, the generator prints the import error and stops; it
never installs anything itself. Settings persist between sessions in
`cnc_generator_settings.json`, which stays out of git;
`cnc_generator_settings.example.json` shows its format. The output folder must
already exist: choose it with Browse.

The generator understands the practical constraints of a real CNC workflow:
finger widths are recomputed to divide the rail evenly, joint fit tolerance is a
parameter rather than an afterthought, and every operation is labeled for the
person standing at the machine.

## Repository tour

```
CNC Plans/                   the live generator (cnc_generator.py, with
                             blender_generator.py and utils.py), its output
                             sets, and fabrication support files
  ARCHIVED PYTHON CODE/      earlier generator versions (v1.03 … v1.29)
  For Fabrication/           final DWG drawings sent to fabrication
  JOINERY_MATH_FIXES.md      notes on the joint-math corrections
ARCHIVED PYTHON CODE/        oldest archived version
PROJECT CLOSET/              reference material, incl. the Vectric Box Creator
                             gadget (Lua) this project outgrew
Full_Blind_Box_Joint.jpg     joinery reference photos
Woodcraft Example *.png      shadowbox style references
17HM19-2004S.STEP            CAD model of the stepper motor the housing pockets fit
```

## Author

Joel Silverman — [joelsilverman.com](https://joelsilverman.com) — Atlanta visual
artist. This tool was written to fabricate housings for kinetic sculpture; use
anything here that's useful for your own boxes.
