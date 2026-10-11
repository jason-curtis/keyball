#!/usr/bin/env python3.12
"""Acrylic case layers for Keyball61 Choc, generated from the routed PCBs.

Usage: plates.py [pcb_dir] [out_dir]   (defaults: keyball61-choc/pcb, keyball61-choc/case)

Stack (top to bottom), plate-less like other hotswap Choc builds:
    Choc switches -> main PCB (1.6 mm) -> M2 x 4 mm hex standoffs -> 2 mm acrylic bottom
held by M2 x 4 low-profile screws on both ends. Keyball's 3 mm acrylic middle layer is not
reproduced: at 18 x 17 mm pitch the back-side sockets/LEDs/diodes leave no room for webs,
so it fell apart into slivers. Standoffs clear the 1.85 mm sockets with room to spare.

The right-hand bottom plate fills the trackball notch, and the ball case screws to it. The ball-case
holes come from Yowkees' Keyball61_Rev1_BallSide_Bottom_Acryl_Clear2mm.dxf, mapped into PCB
coordinates (X = 287.212 - x*25.4/72, Y = y*25.4/72 - 18.498, which matches all 8 spacer holes
to 0.13 mm). They stay valid because convert.py keeps the notch geometry fixed.
"""
import os
import sys

import ezdxf
import pcbnew
from shapely.geometry import box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import convert  # noqa: E402

BALL_CASE = [  # (x, y, diameter) in PCB mm, right half only
    (150.66, 132.48, 11.74),
    (161.36, 124.49, 2.4),
    (161.36, 140.47, 2.4),
]
NOTCH_FILL = box(119.5, 115.0, 176.5, 147.0)


def write_dxf(path, geom, circles):
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    for poly in polys:
        for ring in [poly.exterior, *poly.interiors]:
            # DXF is y-up; mirror y so the drawing reads like the PCB (viewed from the top)
            msp.add_lwpolyline([(x, -y) for x, y in ring.coords], close=True)
    for x, y, d in circles:
        msp.add_circle((x, -y), d / 2)
    doc.saveas(path)


def main(pcb_dir=os.path.join(ROOT, "pcb"), out_dir=os.path.join(ROOT, "case")):
    os.makedirs(out_dir, exist_ok=True)
    for side in ("left", "right"):
        convert.FLIP = convert.SIDE[side]["flip"]
        b = pcbnew.LoadBoard(os.path.join(pcb_dir, side, f"keyball61_choc_{side}.kicad_pcb"))
        outline = convert.board_polygon(b)
        holes = [convert.pos(f) for f in b.GetFootprints() if str(f.GetFPID().GetLibItemName()).startswith("MountingHole_2.2mm_M2")
                 and f.GetValue() == "M2"]

        # bottom plate
        bottom = outline
        circles = [(x, y, 2.2) for x, y in holes]
        if side == "right":
            bottom = unary_union([outline, NOTCH_FILL]).buffer(2, join_style=1).buffer(-2, join_style=1)
            circles += BALL_CASE
        write_dxf(os.path.join(out_dir, f"keyball61_choc_{side}_bottom_2mm.dxf"), bottom, circles)

        print(f"{side}: bottom plate {bottom.area / 100:.0f} cm2, {len(holes)} M2 holes")


if __name__ == "__main__":
    main(*sys.argv[1:])
