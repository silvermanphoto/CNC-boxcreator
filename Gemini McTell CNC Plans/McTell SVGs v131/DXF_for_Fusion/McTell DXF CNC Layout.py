# McTell DXF CNC Layout Importer — v131
#
# Imports DXF files from the McTell SVG-to-DXF conversion into Fusion 360
# as sketches on the XY plane, ready for CAM/CNC toolpath generation.
#
# Creates:
#   1. Master CNC layout sketch (all parts nested on 48x96" sheet)
#   2. Individual part components with per-operation sketches
#   3. Extrudes perimeters to stock thickness
#
# DXF layers → Fusion sketch organization:
#   PERIMETER / OUTSIDE_CUTS  →  profile cut (through)
#   RABBET                    →  pocket (partial depth)
#   WINDOW                    →  interior cutout (through)
#   HOLES                     →  drill operations
#   SCORE                     →  V-bit scoring

import adsk.core, adsk.fusion, adsk.cam
import traceback, os, datetime, json


# ─── Configuration ───────────────────────────────────────────────────────────

DXF_DIR = os.path.join(
    os.path.expanduser("~"),
    "Desktop",
    "2026 Files",
    "26-005 Gemini-created CNC Box Creator",
    "Gemini McTell CNC Plans",
    "McTell SVGs v131",
    "DXF_for_Fusion"
)

# Stock parameters from config.json (all mm, converted to cm for Fusion)
STOCK_THICKNESS_MM = 15.19936
STOCK_THICKNESS_CM = STOCK_THICKNESS_MM / 10.0
IN_TO_CM = 2.54

# Sheet size (inches)
SHEET_W = 48.0
SHEET_H = 96.0

# Part groups: each part and its operation DXF files
PART_GROUPS = {
    "Front Bezel": [
        "FRONT_BEZEL_PERIMETER.dxf",
        "FRONT_BEZEL_RABBETS.dxf",
        "FRONT_BEZEL_WINDOW.dxf",
    ],
    "Back Panel": [
        "BACK_PANEL_PERIMETER.dxf",
        "BACK_PANEL_RABBETS.dxf",
        "BACK_PANEL_HOLES_THROUGH.dxf",
        "BACK_PANEL_HATCH_CUT.dxf",
    ],
    "Left Rail": [
        "LEFT_RAIL_PERIMETER.dxf",
    ],
    "Right Rail": [
        "RIGHT_RAIL_PERIMETER.dxf",
    ],
    "Top Rail": [
        "TOP_RAIL_PERIMETER.dxf",
    ],
    "Bottom Rail": [
        "BOTTOM_RAIL_PERIMETER.dxf",
    ],
    "Hatch Lid": [
        "HATCH_LID.dxf",
    ],
    "Cleat Wall": [
        "CLEAT_WALL_PERIMETER.dxf",
        "CLEAT_WALL_HOLES_THROUGH.dxf",
        "CLEAT_WALL_HOLES_CSINK.dxf",
        "CLEAT_BEVEL_SCORE.dxf",
    ],
    "Cleat Box": [
        "CLEAT_BOX_PERIMETER.dxf",
        "CLEAT_BOX_HOLES_THROUGH.dxf",
        "CLEAT_BOX_HOLES_CSINK.dxf",
    ],
}


# ─── Logging ─────────────────────────────────────────────────────────────────

def make_log_path():
    desktop = os.path.expanduser("~/Desktop")
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(desktop, f"McTell_DXF_Import_{ts}.txt")

def log(path, msg):
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass


# ─── Main ────────────────────────────────────────────────────────────────────

def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface if app else None
    LOG = make_log_path()

    try:
        log(LOG, "=" * 60)
        log(LOG, "McTell DXF CNC Layout Importer v131")
        log(LOG, f"DXF source: {DXF_DIR}")
        log(LOG, f"Stock thickness: {STOCK_THICKNESS_MM:.3f} mm")
        log(LOG, "=" * 60)

        # Verify DXF directory exists
        if not os.path.isdir(DXF_DIR):
            raise FileNotFoundError(f"DXF directory not found:\n{DXF_DIR}")

        # List available DXFs
        dxf_files = [f for f in os.listdir(DXF_DIR) if f.endswith(".dxf")]
        log(LOG, f"Found {len(dxf_files)} DXF files")

        # Create new design document
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.DirectDesignType
        root = design.rootComponent
        root.name = "McTell CNC Layout v131"

        importMgr = app.importManager

        # ── Step 1: Import master layout ──────────────────────────────
        master_dxf = os.path.join(DXF_DIR, "MASTER_LAYOUT_COMBINED.dxf")
        if os.path.exists(master_dxf):
            log(LOG, "\n--- Importing master CNC layout ---")
            try:
                opts = importMgr.createDXF2DImportOptions(
                    master_dxf,
                    root.xYConstructionPlane
                )
                importMgr.importToTarget(opts)
                # Rename the sketch
                sketches = root.sketches
                if sketches.count > 0:
                    sk = sketches.item(sketches.count - 1)
                    sk.name = "MASTER CNC LAYOUT (48x96)"
                log(LOG, "  OK  Master layout imported")
            except Exception as e:
                log(LOG, f"  FAIL  Master layout: {e}")
        else:
            log(LOG, "  SKIP  No master layout DXF found")

        # ── Step 2: Import individual parts as components ─────────────
        log(LOG, "\n--- Importing individual parts ---")
        imported_count = 0
        failed = []

        for part_name, dxf_names in PART_GROUPS.items():
            log(LOG, f"\n  Component: {part_name}")

            # Create component for this part
            occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = part_name

            for dxf_name in dxf_names:
                dxf_path = os.path.join(DXF_DIR, dxf_name)
                if not os.path.exists(dxf_path):
                    log(LOG, f"    SKIP  {dxf_name} (not found)")
                    continue

                try:
                    opts = importMgr.createDXF2DImportOptions(
                        dxf_path,
                        comp.xYConstructionPlane
                    )
                    importMgr.importToTarget(opts)

                    # Rename sketch to operation type
                    if comp.sketches.count > 0:
                        sk = comp.sketches.item(comp.sketches.count - 1)
                        # Extract operation name from filename
                        op_name = dxf_name.replace(".dxf", "")
                        sk.name = op_name

                    imported_count += 1
                    log(LOG, f"    OK  {dxf_name}")
                except Exception as e:
                    failed.append(dxf_name)
                    log(LOG, f"    FAIL  {dxf_name}: {e}")

        # ── Step 3: Add stock boundary sketch ─────────────────────────
        log(LOG, "\n--- Adding stock boundary ---")
        try:
            sk_stock = root.sketches.add(root.xYConstructionPlane)
            sk_stock.name = "STOCK BOUNDARY (4x8 sheet)"
            lines = sk_stock.sketchCurves.sketchLines
            p0 = adsk.core.Point3D.create(0, 0, 0)
            p1 = adsk.core.Point3D.create(SHEET_W * IN_TO_CM, 0, 0)
            p2 = adsk.core.Point3D.create(SHEET_W * IN_TO_CM, SHEET_H * IN_TO_CM, 0)
            p3 = adsk.core.Point3D.create(0, SHEET_H * IN_TO_CM, 0)
            lines.addByTwoPoints(p0, p1)
            lines.addByTwoPoints(p1, p2)
            lines.addByTwoPoints(p2, p3)
            lines.addByTwoPoints(p3, p0)
            log(LOG, f"  OK  Stock boundary: {SHEET_W}\" x {SHEET_H}\"")
        except Exception as e:
            log(LOG, f"  FAIL  Stock boundary: {e}")

        # ── Summary ───────────────────────────────────────────────────
        log(LOG, "\n" + "=" * 60)
        log(LOG, f"Import complete: {imported_count} sketches imported")
        if failed:
            log(LOG, f"Failed: {', '.join(failed)}")
        log(LOG, f"Stock thickness for extrude: {STOCK_THICKNESS_CM:.4f} cm")
        log(LOG, f"Log saved to: {LOG}")
        log(LOG, "=" * 60)

        # Fit view
        vp = app.activeViewport
        vp.fit()

        if ui:
            msg = (
                f"McTell DXF CNC Layout imported successfully!\n\n"
                f"  {imported_count} operation sketches\n"
                f"  {len(PART_GROUPS)} part components\n"
                f"  Master layout on XY plane\n\n"
                f"Stock thickness for extrude: {STOCK_THICKNESS_MM:.3f} mm\n\n"
                f"Log: {LOG}"
            )
            if failed:
                msg += f"\n\nFailed imports: {', '.join(failed)}"
            ui.messageBox(msg, "McTell CNC Layout v131")

    except Exception as e:
        log(LOG, f"\nFATAL ERROR: {e}")
        log(LOG, traceback.format_exc())
        if ui:
            ui.messageBox(
                f"Error importing McTell DXFs:\n\n{e}\n\nSee log: {LOG}",
                "McTell CNC Layout — Error"
            )


def stop(context):
    pass
