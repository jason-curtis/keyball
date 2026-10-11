#!/usr/bin/env python3.12
"""Autoroute a converted Keyball61 Choc half with Freerouting, then add GND pours.

Usage: route.py <in.kicad_pcb> <out.kicad_pcb> <freerouting.jar> [passes]
"""
import os
import subprocess
import sys

import re

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert import sexpr_end, top_level_forms  # noqa: E402

MM = pcbnew.FromMM


def routing_copy(src, dst, keep_tracks=False):
    """KiCad's Specctra exporter chokes on the Keyball logo footprints and on the custom
    (arrow-shaped) solder-jumper pads. Route a copy without logos and with plain rect jumper
    pads; the routed wires are then imported into the real board."""
    text = open(src).read()
    if keep_tracks:  # second pass: keep the wiring, drop the GND pours
        text = "".join(text[a:b_] for a, b_ in _spans_without(text, "zone"))
    out, i = [], 0
    for j, k in list(top_level_forms(text, "footprint")):
        out.append(text[i:j])
        block = text[j:k]
        i = k
        if "keyball_logo" in block[:200]:
            continue
        if "smd custom" in block:
            def fix(m):
                pad = m.group(0)
                # replace the arrow-shaped custom pad by its exact bounding box
                pts = [(float(x), float(y)) for x, y in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", pad)]
                at = re.search(r"\(at ([-\d.]+) ([-\d.]+)\)", pad)
                if pts and at:
                    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
                    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
                    ax, ay = float(at.group(1)) + (x0 + x1) / 2, float(at.group(2)) + (y0 + y1) / 2
                    pad = pad[:at.start()] + f"(at {ax:.4f} {ay:.4f})" + pad[at.end():]
                    pad = re.sub(r"\(size [\d.]+ [\d.]+\)", f"(size {x1 - x0:.4f} {y1 - y0:.4f})", pad, count=1)
                pad = pad.replace("smd custom", "smd rect")
                for key in ("(primitives", "(options"):
                    a = pad.find(key)
                    if a >= 0:
                        pad = pad[:a] + pad[sexpr_end(pad, a):]
                return pad
            parts, a = [], 0
            for m in re.finditer(r"\(pad ", block):
                if m.start() < a:
                    continue
                e = sexpr_end(block, m.start())
                parts.append(block[a:m.start()])
                pad = block[m.start():e]
                parts.append(fix(re.match(r"(?s).*", pad)) if "smd custom" in pad else pad)
                a = e
            parts.append(block[a:])
            block = "".join(parts)
        out.append(block)
    out.append(text[i:])
    open(dst, "w").write("".join(out))
    return dst


def _spans_without(text, head):
    i = 0
    for j, k in top_level_forms(text, head):
        yield i, j
        i = k
    yield i, len(text)


def parse_sexpr(text):
    tokens = re.findall(r'\(|\)|"[^"]*"|[^\s()]+', text)
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(t.strip('"'))
    return stack[0][0]


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def import_ses(board, ses):
    """Minimal Specctra session importer (wires + vias). KiCad's own importer rejects the
    duplicated via padstacks Freerouting 1.9 writes."""
    root = parse_sexpr(open(ses).read())
    routes = find(root, "routes")[0]
    res = find(routes, "resolution")[0]
    scale = {"um": 1e-3, "mm": 1.0, "mil": 0.0254}[res[1]] / float(res[2])

    def pt(x, y):
        return pcbnew.VECTOR2I(MM(float(x) * scale), MM(-float(y) * scale))

    vias = {}
    for ps in find(find(routes, "library_out")[0], "padstack") if find(routes, "library_out") else []:
        m = re.search(r"(\d+):(\d+)_um", ps[1])
        if m:
            vias[ps[1]] = (int(m.group(1)) / 1000, int(m.group(2)) / 1000)
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    n_wire = n_via = 0
    for net in find(find(routes, "network_out")[0], "net"):
        ni = board.FindNet(net[1])
        for w in find(net, "wire"):
            path = find(w, "path")[0]
            layer, width = layers[path[1]], MM(float(path[2]) * scale)
            xy = path[3:]
            pts = [pt(xy[i], xy[i + 1]) for i in range(0, len(xy) - 1, 2)]
            for a, b_ in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(a)
                t.SetEnd(b_)
                t.SetWidth(width)
                t.SetLayer(layer)
                t.SetNet(ni)
                board.Add(t)
                n_wire += 1
        for vv in find(net, "via"):
            dia, drill = vias.get(vv[1], (0.6, 0.3))
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pt(vv[2], vv[3]))
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            via.SetWidth(MM(dia))
            via.SetDrill(MM(drill))
            via.SetNet(ni)
            board.Add(via)
            n_via += 1
    print(f"imported {n_wire} track segments, {n_via} vias")


EDGE_MM = 0.3  # copper to board edge / cut-out (JLC-safe)
DRU = """(version 1)
(rule "SK6812MINI-E pads hug their own reverse-mount cut-out (by design, as in Keyball61)"
  (constraint edge_clearance (min 0mm))
  (condition "A.Type == 'Pad' && A.memberOfFootprint('LED*')"))
"""


def dru_for(board):
    """Project rules. Keyball's 3-pad cut jumpers (JP025/JP06) are normally closed: their copper
    bridges the pads until you cut it, so their internal spacing is exempt."""
    refs = sorted(f.GetReference() for f in board.GetFootprints()
                  if str(f.GetFPID().GetLibItemName()) in ("JP025", "JP06"))
    cond = " || ".join(f"A.memberOfFootprint('{r}')" for r in refs)
    rule = ('(rule "Keyball 3-pad solder jumpers (as designed)"\n  (constraint clearance (min 0mm))\n'
            f'  (condition "{cond}"))\n') if refs else ""
    return DRU + rule


def dsn_edge_margin(dsn, margin_um):
    """Freerouting keeps the class clearance (0.2 mm) from the boundary and cut-outs; push both
    by `margin_um` so copper ends up EDGE_MM from every edge."""
    from shapely.geometry import Polygon

    text = open(dsn).read()

    def coords(body):
        nums = [float(x) for x in body.split()]
        return list(zip(nums[0::2], nums[1::2]))

    def fmt(poly):
        pts = list(poly.exterior.coords)[:-1]
        return "  ".join(f"{x:.1f} {y:.1f}" for x, y in pts)

    m = re.search(r"\(boundary\s*\(path pcb 0([^()]*)\)", text)
    poly = Polygon(coords(m.group(1))).buffer(-margin_um, join_style=2)
    text = text[:m.start(1)] + "  " + fmt(poly) + "\n      " + text[m.end(1):]
    out, i = [], 0
    for m in re.finditer(r"\(keepout \"\" \(polygon signal 0([^()]*)\)", text):
        poly = Polygon(coords(m.group(1))).buffer(margin_um, join_style=2)
        out.append(text[i:m.start(1)])
        out.append("  " + fmt(poly) + "\n      ")
        i = m.end(1)
    out.append(text[i:])
    open(dsn, "w").write("".join(out))


def set_rules(brd):
    brd.GetDesignSettings().m_CopperEdgeClearance = MM(EDGE_MM)
    nc = brd.GetDesignSettings().m_NetSettings.GetDefaultNetclass()
    nc.SetTrackWidth(MM(0.25))
    nc.SetClearance(MM(0.2))
    nc.SetViaDrill(MM(0.3))
    nc.SetViaDiameter(MM(0.6))


def freeroute(board_file, base, jar, passes, keep_tracks):
    rb = pcbnew.LoadBoard(routing_copy(board_file, base + ".routing.kicad_pcb", keep_tracks))
    set_rules(rb)
    dsn, ses = base + ".dsn", base + ".ses"
    if not pcbnew.ExportSpecctraDSN(rb, dsn):
        sys.exit("DSN export failed")
    dsn_edge_margin(dsn, (EDGE_MM - 0.2) * 1000)

    # wider power tracks: move VCC/GND out of the default class into a 0.5 mm class
    text = open(dsn).read()
    m = re.search(r"\(class kicad_default([^()]*)", text)
    members = m.group(1).split()
    power = [n for n in ("VCC", "GND") if n in members]
    if power:
        rest = " ".join(n for n in members if n not in power)
        text = text[:m.start(1)] + " " + rest + "\n      " + text[m.end(1):]
        cls = ("    (class power " + " ".join(power) +
               "\n      (circuit (use_via \"Via[0-1]_600:300_um\"))\n      (rule (width 500) (clearance 200))\n    )\n")
        i = text.rindex("  )\n  (wiring")
        text = text[:i] + cls + text[i:]
        open(dsn, "w").write(text)
    # Freerouting 1.9 opens a (hidden) window even in batch mode: give it a virtual display
    cmd = ["java", "-jar", os.path.abspath(jar), "-de", dsn, "-do", ses, "-mp", passes]
    if not os.environ.get("DISPLAY"):
        cmd = ["xvfb-run", "-a"] + cmd
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    return ses


def main(src, dst, jar, passes="40"):
    """Two Freerouting passes: the second starts from the first one's wiring and mops up
    connections the first left open."""
    base = os.path.splitext(os.path.abspath(dst))[0]
    src = os.path.abspath(src)
    ses = freeroute(src, base + ".pass1", jar, passes, keep_tracks=False)
    mid = pcbnew.LoadBoard(src)
    set_rules(mid)
    import_ses(mid, ses)
    mid.Save(base + ".pass1.kicad_pcb")
    ses = freeroute(base + ".pass1.kicad_pcb", base + ".pass2", jar, "20", keep_tracks=True)

    b = pcbnew.LoadBoard(src)
    set_rules(b)
    import_ses(b, ses)

    # GND pour on both layers, inside the board outline
    gnd = b.GetNetcodeFromNetname("GND")
    bb = b.GetBoardEdgesBoundingBox()
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(b)
        z.SetLayer(layer)
        z.SetNetCode(gnd)
        z.SetLocalClearance(MM(0.3))
        z.SetMinThickness(MM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(MM(0.3))
        z.SetThermalReliefSpokeWidth(MM(0.4))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in ((bb.GetX(), bb.GetY()), (bb.GetRight(), bb.GetY()),
                     (bb.GetRight(), bb.GetBottom()), (bb.GetX(), bb.GetBottom())):
            ol.Append(x, y)
        b.Add(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(dst)
    open(os.path.splitext(dst)[0] + ".kicad_dru", "w").write(dru_for(b))
    print("saved", dst)


if __name__ == "__main__":
    main(*sys.argv[1:])
