#!/usr/bin/env python3.12
"""Fab outputs for both Keyball61 Choc halves: gerbers + drill zip, JLCPCB BOM and CPL.

Usage: fab.py [pcb_dir] [out_dir]   (defaults: keyball61-choc/pcb, keyball61-choc/fab)

Assembly side: everything JLC places sits on the solder side (B.Cu on the right board, F.Cu
on the left board, which is mounted upside down), so each half is a single-sided job.
"""
import csv
import os
import shutil
import subprocess
import sys
import zipfile
from collections import defaultdict

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# value/footprint -> (comment, LCSC part, assembly class)
PARTS = {
    "Choc_V1_Hotswap": ("Kailh Choc v1 hotswap socket CPG135001S30", "C5333465", "SMT"),
    "D3_SMD_v2_BOTH": ("1N4148W SOD-123", "C81598", "SMT"),
    "YS-SK6812MINI-Keyball-TL": ("SK6812MINI-E reverse-mount RGB LED", "C5149201", "SMT"),
    "YS-SK6812MINI-Keyball-BL": ("SK6812MINI-E reverse-mount RGB LED", "C5149201", "SMT"),
    "R_0603_1608Metric": ("4.7k 0603 1%", "C23162", "SMT"),
    "TRRS_JACK_MJ4PP9": ("PJ-320A TRRS jack (check pinout vs MJ-4PP-9 footprint)", "C2884926", "THT-optional"),
    "ResetSW": ("Tactile switch 2-pin 6x3.5 (SKHLLCA010)", "C139766", "THT-optional"),
}
LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"


def solder_layer(fp):
    smd = [p for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    if smd and all(p.IsOnLayer(pcbnew.B_Cu) for p in smd):
        return "Bottom"
    return "Top"


def run(*cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def main(pcb_dir=os.path.join(ROOT, "pcb"), out_dir=os.path.join(ROOT, "fab")):
    for side in ("left", "right"):
        pcb = os.path.join(pcb_dir, side, f"keyball61_choc_{side}.kicad_pcb")
        out = os.path.join(out_dir, side)
        gdir = os.path.join(out, "gerbers")
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(gdir)
        run("kicad-cli", "pcb", "export", "gerbers", "--layers", LAYERS, "--no-protel-ext", "-o", gdir + "/", pcb)
        run("kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
            "--drill-origin", "absolute", "--excellon-units", "mm", "-o", gdir + "/", pcb)
        zpath = os.path.join(out, f"keyball61_choc_{side}_gerbers.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(os.listdir(gdir)):
                z.write(os.path.join(gdir, f), f)
        shutil.rmtree(gdir)

        b = pcbnew.LoadBoard(pcb)
        bom = defaultdict(list)
        cpl = []
        for fp in b.GetFootprints():
            name = str(fp.GetFPID().GetLibItemName())
            if name not in PARTS:
                continue
            comment, lcsc, cls = PARTS[name]
            ref = fp.GetReference()
            bom[(comment, name, lcsc, cls)].append(ref)
            p = fp.GetPosition()
            cpl.append([ref, f"{pcbnew.ToMM(p.x):.4f}mm", f"{-pcbnew.ToMM(p.y):.4f}mm",
                        solder_layer(fp), f"{fp.GetOrientationDegrees() % 360:.1f}"])
        with open(os.path.join(out, f"keyball61_choc_{side}_bom_jlc.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "Qty", "Assembly"])
            for (comment, name, lcsc, cls), refs in sorted(bom.items()):
                w.writerow([comment, ",".join(sorted(refs)), name, lcsc, len(refs), cls])
        with open(os.path.join(out, f"keyball61_choc_{side}_cpl_jlc.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
            w.writerows(sorted(cpl))
        print(side, {k[1]: len(v) for k, v in bom.items()}, "->", out)


if __name__ == "__main__":
    main(*sys.argv[1:])
