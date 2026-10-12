#!/usr/bin/env python3.12
"""Convert a Keyball61 (MX, 19.05 mm) half into a Keyball61 Choc (Choc v1, 18 x 17 mm) half.

Usage: convert.py right|left <in.kicad_pcb> <out.kicad_pcb>

What it does (KiCad 7 pcbnew API):
  * keeps every net, so the switch matrix, LED chain and Pro Micro pinout are unchanged
    and the stock keyball61 QMK keyboard definition still applies;
  * replaces each MX / MX+Choc hotswap footprint with a Choc v1 hotswap footprint;
  * re-grids finger columns to 18 mm (x) x 17 mm (y), anchored on column 5 / row 3 so the
    trackball notch, ball-PCB contact (J2) and thumb cluster keep their original geometry;
  * puts per-key LEDs under the Choc LED window, diodes at a fixed spot on the back,
    strips the unused front-side copper of the "BOTH" footprints;
  * regenerates the board outline and re-places the case standoff holes as M2 holes in
    the Choc key gaps;
  * removes all tracks/zones (routing is done afterwards by route.py).
"""
import math
import os
import sys

import pcbnew
from shapely import affinity
from shapely.geometry import MultiPoint, Point, Polygon, box
from shapely.ops import unary_union, voronoi_diagram

MM = pcbnew.FromMM
TOMM = pcbnew.ToMM
P = 19.05
CHOC_X, CHOC_Y = 18.0, 17.0
SX, SY = CHOC_X / P, CHOC_Y / P

SIDE = {
    # x0: x of column 1 (innermost finger column) in the original file.
    # flip: Keyball's left PCB is the same reversible design mounted upside down (see the
    # build-guide photo kb61_013.jpg), so on the left board switches enter from the file's
    # B side and sockets / diodes / LEDs are soldered on F.Cu.
    "right": dict(x0=117.96, flip=False),
    "left": dict(x0=118.91, flip=True),
}
FLIP = False  # set from SIDE in main()
ANCHOR_COL = 4  # column 5 stays put; columns 1..4 move outward, column 6 inward
INNER_DY = 1.0  # extra drop for the Pro Micro / OLED block and the inner key
LED_DY = 4.7  # Choc v1 LED window centre, south of switch centre
DIODE_OFS = (8.0, 1.6)  # diode on the back, vertical, right beside socket pad 2 (short hop)


def v(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def pos(fp):
    p = fp.GetPosition()
    return TOMM(p.x), TOMM(p.y)


def rot(x, y, deg):
    # KiCad rotation: positive angle is counter-clockwise on screen (y down)
    a = math.radians(-deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def is_switch(fp):
    n = str(fp.GetFPID().GetLibItemName())
    return n.startswith("CherryMX") or n.startswith("MX&Choc")


# ---------------------------------------------------------------- footprints
LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pcb", "keyball61_choc.pretty")


def load_fp(name):
    fp = pcbnew.FootprintLoad(LIB, name)
    fp.SetFPID(pcbnew.LIB_ID("keyball61_choc", name))
    return fp


def make_choc(board, ref, value, center, angle, nets):
    fp = load_fp("Choc_V1_Hotswap")
    fp.SetReference(ref)
    fp.SetValue(value)
    for p in fp.Pads():
        if nets.get(p.GetNumber()) is not None:
            p.SetNet(nets[p.GetNumber()])
    board.Add(fp)
    fp.SetPosition(v(*center))
    if FLIP:
        # KiCad mirrors a flipped footprint top-to-bottom; the switch entering from the back
        # needs a left-right mirror, which is the same thing turned 180 degrees.
        fp.Flip(v(*center), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        angle += 180
    fp.SetOrientationDegrees(angle)
    return fp


STRIP_FRONT = set()
NO_LOCAL_CLEARANCE = set()  # Keyball's cut jumpers: copper bridges by design


def mark_deleted(fp):
    """BOARD.Remove() breaks the KiCad 7 SWIG proxies; rename now, drop from the saved file."""
    fp.SetReference("__DEL__" + fp.GetReference())


def strip_front_copper(fp):
    """'BOTH' footprints carry mirrored pads on F.Cu for reversible use; keep only B.Cu.

    Removing pads through the KiCad 7 SWIG API corrupts its object proxies, so the refs are
    collected here and the pads are dropped from the saved file by drop_front_pads()."""
    STRIP_FRONT.add(fp.GetReference())


def sexpr_end(text, i):
    d = 0
    while True:
        c = text[i]
        if c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return i + 1
        elif c == '"':
            i = text.index('"', i + 1)
        i += 1


def top_level_forms(text, head):
    """Yield (start, end) of depth-1 forms starting with `(head ` (KiCad 7 or 9 formatting)."""
    import re

    for m in re.finditer(r"\n[\t ]+\(" + head + r" ", text):
        yield m.start(), sexpr_end(text, m.start() + m.group(0).index("("))


def drop_front_pads(path, refs, flip=False):
    """Post-process the saved board: drop __DEL__ footprints, F-side copper/silk of 'BOTH'
    footprints listed in `refs`, and graphics parked on User.9."""
    import re

    top, bot = ("B", "F") if flip else ("F", "B")  # 'top' = switch side of the board
    text = open(path).read()
    out, i = [], 0
    for j, k in list(top_level_forms(text, "footprint")):
        if j < i:
            continue
        out.append(text[i:j])
        block = text[j:k]
        m = re.search(r'\((?:fp_text reference|property "Reference") "([^"]*)"', block)
        ref = m.group(1) if m else ""
        i = k
        if ref.startswith("__DEL__"):
            continue
        if ref in NO_LOCAL_CLEARANCE:
            block = re.sub(r"\s*\(clearance [\d.]+\)", "", block)
        if ref in refs:
            parts, a = [], 0
            for mm_ in re.finditer(r"\((pad|fp_line|fp_circle|fp_arc|fp_poly|fp_rect) ", block):
                s0 = mm_.start()
                if s0 < a:
                    continue
                e0 = sexpr_end(block, s0)
                item = block[s0:e0]
                lay = re.search(r"\(layers? ([^)]*)\)", item)
                lay = lay.group(1) if lay else ""
                if mm_.group(1) == "pad":
                    kill = f'"{top}.Cu"' in lay and f'"{bot}.Cu"' not in lay and "*.Cu" not in lay
                else:
                    kill = f'"{top}.SilkS"' in lay or f'"{top}.Fab"' in lay
                if kill:
                    parts.append(block[a:s0].rstrip(" \t"))
                    a = e0
            parts.append(block[a:])
            block = "".join(parts)
        out.append(block)
    out.append(text[i:])
    text = "".join(out)
    out, i = [], 0
    for j, k in list(top_level_forms(text, "gr_[a-z]+")):
        out.append(text[i:j])
        if '(layer "User.9")' not in text[j:k]:
            out.append(text[j:k])
        i = k
    out.append(text[i:])
    open(path, "w").write("".join(out))


def make_m2_hole(board, ref, center):
    fp = load_fp("MountingHole_2.2mm_M2")
    fp.SetReference("MH" + ref.lstrip("J"))
    board.Add(fp)
    fp.SetPosition(v(*center))
    return fp


def strip_routing(src, tmp):
    """Copy the board without top-level segment/arc/via/zone forms; routing is redone later."""
    text = open(src).read()
    out, i, depth = [], 0, 0
    drop = ("(segment", "(via", "(zone", "(arc")
    while i < len(text):
        if depth == 1 and text.startswith(drop, i):
            i = sexpr_end(text, i)
            continue
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == '"':
            j = text.index('"', i + 1)
            out.append(text[i:j + 1])
            i = j + 1
            continue
        out.append(ch)
        i += 1
    open(tmp, "w").write("".join(out))
    return tmp


# ------------------------------------------------------------------ geometry
def board_polygon(board):
    ps = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(ps)
    ol = ps.Outline(0)
    pts = [(TOMM(ol.CPoint(i).x), TOMM(ol.CPoint(i).y)) for i in range(ol.PointCount())]
    return Polygon(pts).buffer(0)


NUDGE = {"YS-SK6812MINI-Keyball-BL", "D3_SMD_v2_BOTH", "Jumper_NEW", "Jumper", "JP025", "JP06",
         "R_0603_1608Metric", "1pin_conn", "ResetSW"}


def fp_keepouts(fp, with_housing=False, socket=False):
    """Rough keep-out shapes (pads, holes, cut-outs) of a footprint in board mm, per side.

    Returns {"F": geom, "B": geom}; through holes and cut-outs land on both sides."""
    sides = {"F": [], "B": []}
    if str(fp.GetFPID().GetLibItemName()).startswith("R_0603"):  # keep resistor courtyards apart
        cx, cy = pos(fp)
        crt = affinity.rotate(box(-1.6, -0.85, 1.6, 0.85), -fp.GetOrientationDegrees(), origin=(0, 0))
        sides["B" if fp.IsFlipped() else "F"].append(affinity.translate(crt, cx, cy))
    gone = pcbnew.B_Cu if FLIP else pcbnew.F_Cu  # side whose pads drop_front_pads() removes
    for p in fp.Pads():
        if (fp.GetReference() in STRIP_FRONT and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
                and p.IsOnLayer(gone)):
            continue
        x, y = TOMM(p.GetPosition().x), TOMM(p.GetPosition().y)
        sx, sy = TOMM(p.GetSize().x), TOMM(p.GetSize().y)
        if p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE:
            g = Point(x, y).buffer(max(sx, TOMM(p.GetDrillSize().x)) / 2)
        else:
            r = box(-sx / 2, -sy / 2, sx / 2, sy / 2)
            r = affinity.rotate(r, -p.GetOrientationDegrees(), origin=(0, 0))
            g = affinity.translate(r, x, y)
        through = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
        if through or p.IsOnLayer(pcbnew.F_Cu):
            sides["F"].append(g)
        if through or p.IsOnLayer(pcbnew.B_Cu):
            sides["B"].append(g)
    for g in fp.GraphicalItems():
        if g.GetLayer() == pcbnew.Edge_Cuts:
            bb = g.GetBoundingBox()
            r = box(TOMM(bb.GetX()), TOMM(bb.GetY()), TOMM(bb.GetRight()), TOMM(bb.GetBottom()))
            sides["F"].append(r)
            sides["B"].append(r)
    cx, cy = pos(fp)
    fl = fp.IsFlipped()
    if socket and is_choc(fp):
        sk = box(-9.6, -7.3, 4.6, -2.4) if fl else box(-4.6, -7.3, 9.6, -2.4)
        key_angle = fp.GetOrientationDegrees() - (180 if fl else 0)  # see make_choc()
        sk = affinity.rotate(sk, -key_angle, origin=(0, 0))
        sides["F" if fl else "B"].append(affinity.translate(sk, cx, cy))
    if with_housing and is_choc(fp):
        h = affinity.rotate(box(-7.0, -7.0, 7.0, 7.0), -fp.GetOrientationDegrees(), origin=(0, 0))
        sides["B" if fl else "F"].append(affinity.translate(h, cx, cy))
    return {k: unary_union(v_) for k, v_ in sides.items()}


# ---------------------------------------------------------------------- main
def main(side, src, dst):
    global FLIP
    cfg = SIDE[side]
    x0 = cfg["x0"]
    FLIP = cfg["flip"]
    b = pcbnew.LoadBoard(strip_routing(src, dst + ".tmp.kicad_pcb"))
    orig_poly = board_polygon(b)
    drawings = list(b.Drawings())  # grab proxies before any edit (KiCad 7 SWIG quirk)

    # Specctra (autorouter) needs unique references without spaces/wildcards
    seen = {}
    for f in b.GetFootprints():
        r = f.GetReference()
        nr = r.replace(" ", "_").replace("*", "X")
        if r.isdigit() and "SK6812" in str(f.GetFPID().GetLibItemName()):
            nr = "LED" + r  # Keyball numbers its LEDs "1".."37"; DRC rules need a pattern
        seen[nr] = seen.get(nr, 0) + 1
        if seen[nr] > 1:
            nr = f"{nr}_{seen[nr]}"
        if nr != r:
            f.SetReference(nr)
        if str(f.GetFPID().GetLibItemName()) in ("JP025", "JP06", "Jumper_NEW", "Jumper"):
            f.SetAttributes(f.GetAttributes() | pcbnew.FP_ALLOW_SOLDERMASK_BRIDGES)  # jumpers bridge by design
            if str(f.GetFPID().GetLibItemName()) in ("JP025", "JP06"):
                NO_LOCAL_CLEARANCE.add(nr)

    # 2. classify switches and compute their new positions
    sws = [f for f in b.GetFootprints() if is_switch(f)]
    cols = {}
    kind = {}
    for f in sws:
        x, y = pos(f)
        name = str(f.GetFPID().GetLibItemName())
        if name.startswith("MX&Choc"):
            kind[f.GetReference()] = "thumb"
        elif x < x0 - 10:
            kind[f.GetReference()] = "inner"
        else:
            c = round((x - x0) / P)
            kind[f.GetReference()] = "col"
            cols.setdefault(c, []).append(f)
    new = {}  # ref -> (x, y, angle, dx, dy, scaled)
    dx_col = {c: (ANCHOR_COL - c) * (P - CHOC_X) for c in cols}
    for c, fs in cols.items():
        fs.sort(key=lambda f: pos(f)[1])
        y3 = pos(fs[3])[1]
        for f in fs:
            x, y = pos(f)
            ny = y3 + (y - y3) * SY
            new[f.GetReference()] = (x + dx_col[c], ny, 0.0, dx_col[c], ny - y, True)
    dx_inner = dx_col[0]
    for f in sws:
        r = f.GetReference()
        x, y = pos(f)
        if kind[r] == "inner":
            new[r] = (x + dx_inner, y + INNER_DY, 0.0, dx_inner, INNER_DY, False)
        elif kind[r] == "thumb":
            new[r] = (x, y, f.GetOrientationDegrees(), 0.0, 0.0, False)

    # anchors used to drag everything else along (and to warp the outline)
    anchors = []  # (orig_xy, dx, dy, scaled)
    for f in sws:
        x, y = pos(f)
        n = new[f.GetReference()]
        anchors.append(((x, y), n[3], n[4], n[5]))

    def region(x, y):
        if x < x0 - 9.0 and y < 104.5:
            return "inner"
        if side == "right" and 175.0 < x < 186.5 and y > 116.5:
            return "ball"
        if y > 116.5 and x < (x0 + 8 if side == "right" else 145.0):
            return "thumb"
        return None

    def displacement(x, y):
        rg = region(x, y)
        if rg == "inner":
            return dx_inner, INNER_DY
        if rg in ("ball", "thumb"):
            return 0.0, 0.0
        (ax, ay), dx, dy, sc = min(anchors, key=lambda a: (a[0][0] - x) ** 2 + (a[0][1] - y) ** 2)
        if sc:  # follow the column's scaling, not only its translation
            return dx + (x - ax) * (SX - 1), dy + (y - ay) * (SY - 1)
        return dx, dy

    # 2b. keep every assembled SMD part on the solder side (single-sided JLC assembly):
    #     the I2C pull-ups R1/R2 originally sat on opposite faces (the nudge pass unstacks them)
    solder = pcbnew.F_Cu if FLIP else pcbnew.B_Cu
    for f in b.GetFootprints():
        if str(f.GetFPID().GetLibItemName()) == "R_0603_1608Metric":
            if not any(p.IsOnLayer(solder) for p in f.Pads()):
                f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)

    # 3. per-key LEDs and diodes follow their switch
    # per-key diode: its non-ROW net is a switch pad-2 net shared by exactly diode + switch
    netpads = {}
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname():
                netpads.setdefault(p.GetNetname(), set()).add(f.GetReference())
    sw_by_net2 = {}
    for f in sws:
        for p in f.Pads():
            n = p.GetNetname()
            if p.GetNumber() == "2" and n and len(netpads[n]) == 2:
                sw_by_net2[n] = f

    moved = set()
    for f in list(b.GetFootprints()):
        name = str(f.GetFPID().GetLibItemName())
        ref = f.GetReference()
        x, y = pos(f)
        if name.startswith("D3_SMD"):
            nets = {p.GetNetname() for p in f.Pads()}
            sw = next((sw_by_net2[n] for n in nets if n in sw_by_net2), None)
            strip_front_copper(f)
            if sw is None:  # column / handedness diodes: handled with the misc parts
                continue
            nx, ny, ang = new[sw.GetReference()][:3]
            ox, oy = rot(-DIODE_OFS[0] if FLIP else DIODE_OFS[0], DIODE_OFS[1], ang)
            f.SetPosition(v(nx + ox, ny + oy))
            f.SetOrientationDegrees(ang + 90)
            moved.add(ref)
        elif name == "YS-SK6812MINI-Keyball-TL":
            sw = min(sws, key=lambda s: (pos(s)[0] - x) ** 2 + (pos(s)[1] - y) ** 2)
            nx, ny, ang = new[sw.GetReference()][:3]
            ox, oy = rot(0, LED_DY, ang)
            strip_front_copper(f)
            f.SetPosition(v(nx + ox, ny + oy))
            moved.add(ref)
        elif name == "YS-SK6812MINI-Keyball-BL":
            strip_front_copper(f)

    # 4. swap switch footprints
    for f in sws:
        ref = f.GetReference()
        nets = {}
        for p in f.Pads():
            if p.GetNumber() in ("1", "2") and p.GetNetname():
                nets[p.GetNumber()] = p.GetNet()
        nx, ny, ang = new[ref][:3]
        mark_deleted(f)
        make_choc(b, ref, "Choc_V1", (nx, ny), ang, nets)
        moved.add(ref)

    # 5. everything else rides along with its region / nearest key
    holes = []
    for f in list(b.GetFootprints()):
        ref = f.GetReference()
        if ref in moved or ref.startswith("__DEL__"):
            continue
        name = str(f.GetFPID().GetLibItemName())
        x, y = pos(f)
        if name == "MountingHole_4.3mm_M4":
            holes.append((ref, x, y))
            mark_deleted(f)
            continue
        dx, dy = displacement(x, y)
        f.SetPosition(v(x + dx, y + dy))

    for d in drawings:
        if d.GetLayer() == pcbnew.Edge_Cuts:
            d.SetLayer(pcbnew.User_9)  # deleted from the saved file
            continue
        bb = d.GetBoundingBox()
        cx, cy = TOMM(bb.GetCenter().x), TOMM(bb.GetCenter().y)
        dx, dy = displacement(cx, cy)
        d.Move(v(dx, dy))
        if isinstance(d, pcbnew.PCB_TEXT) and "Keyball61" in d.GetText():
            d.SetText("Keyball61 Choc v0.1")

    # 6. new outline: warp the original outline with the keys, add choc key cells
    pts = MultiPoint([a[0] for a in anchors] + [
        (x0 - 20, 50), (x0 - 20, 70), (x0 - 20, 95), (x0 - 25, 140), (x0 - 10, 145)])
    cells = voronoi_diagram(pts, envelope=orig_poly.envelope.buffer(30))
    pieces = []
    for cell in cells.geoms:
        piece = cell.intersection(orig_poly)
        if piece.is_empty:
            continue
        rp = piece.representative_point()
        rg = region(rp.x, rp.y)
        if rg == "inner":
            pieces.append(affinity.translate(piece, dx_inner, INNER_DY))
            continue
        if rg in ("ball", "thumb"):
            pieces.append(piece)
            continue
        (ax, ay), dx, dy, sc = min(anchors, key=lambda a: (a[0][0] - rp.x) ** 2 + (a[0][1] - rp.y) ** 2)
        if sc:
            piece = affinity.scale(piece, SX, SY, origin=(ax, ay))
        pieces.append(affinity.translate(piece, dx, dy))
    for r, (nx, ny, ang, *_r) in new.items():
        c = affinity.rotate(box(-CHOC_X / 2, -CHOC_Y / 2, CHOC_X / 2, CHOC_Y / 2), -ang, origin=(0, 0))
        if kind[r] == "col":
            pieces.append(affinity.translate(c, nx, ny))
        # the hotswap socket pad reaches 9.6 mm sideways, past the 9 mm key cell
        sk = box(-10.4, -8.1, 5.4, -1.6) if FLIP else box(-5.4, -8.1, 10.4, -1.6)  # socket + 0.8 mm
        pieces.append(affinity.translate(affinity.rotate(sk, -ang, origin=(0, 0)), nx, ny))
    if side == "right":  # the strip carrying the ball-PCB contact (J2) keeps its original shape
        pieces.append(orig_poly.intersection(box(175.0, 116.5, 186.5, 200)))
    outline = unary_union(pieces)
    outline = outline.buffer(3.0, join_style=1).buffer(-3.0, join_style=1)  # fill gaps, fillet inside corners
    if side == "right":
        notch = box(118.5, 115.9, 175.75, 200).difference(orig_poly)
        outline = outline.difference(notch)
    outline = outline.buffer(-1.0, join_style=1).buffer(1.0, join_style=1)  # round outside corners
    if outline.geom_type != "Polygon":
        outline = max(outline.geoms, key=lambda g: g.area)
    outline = outline.simplify(0.02)
    shp = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_POLY)
    shp.SetLayer(pcbnew.Edge_Cuts)
    shp.SetWidth(MM(0.1))
    shp.SetFilled(False)
    chain = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in list(outline.exterior.coords)[:-1]:
        chain.Append(MM(x), MM(y))
    chain.SetClosed(True)
    sps = pcbnew.SHAPE_POLY_SET()
    sps.AddOutline(chain)
    shp.SetPolyShape(sps)
    b.Add(shp)

    # 7. nudge small parts that now overlap something on the same side of the board
    fps = [f for f in b.GetFootprints() if not f.GetReference().startswith("__DEL__")]
    ko = {f.GetReference() + "#" + str(i): (f, fp_keepouts(f, socket=True)) for i, f in enumerate(fps)}
    edge_ok = outline.buffer(-0.3)
    movable = {k for k, (f, _) in ko.items() if
               (f.GetReference() not in moved and str(f.GetFPID().GetLibItemName()) in NUDGE)
               or (f.GetReference() in moved and str(f.GetFPID().GetLibItemName()).startswith("D3"))}

    from shapely.prepared import prep

    edge_prep = prep(edge_ok)

    def others_of(key):
        return {sd: prep(unary_union([o[sd] for k, (_, o) in ko.items() if k != key and not o[sd].is_empty]).buffer(0.25))
                for sd in "FB"}

    def clash(shp, oth):
        for sd in "FB":
            if not shp[sd].is_empty and oth[sd].intersects(shp[sd]):
                return True
        allg = unary_union([shp["F"], shp["B"]])
        return not allg.is_empty and not edge_prep.contains(allg)

    for key in sorted(movable):
        f, mine = ko[key]
        oth = others_of(key)
        if not clash(mine, oth):
            continue
        found = None
        x, y = pos(f)
        for turn in (0, 90):
            base = {sd: affinity.rotate(g, -turn, origin=(x, y)) for sd, g in mine.items()}
            for step in range(1, 201):
                rr = step * 0.1
                n = max(8, step * 2)
                for k in range(n):
                    a_ = 2 * math.pi * k / n
                    dx, dy = rr * math.cos(a_), rr * math.sin(a_)
                    cand = {sd: affinity.translate(g, dx, dy) for sd, g in base.items()}
                    if not clash(cand, oth):
                        found = (dx, dy, cand, turn)
                        break
                if found:
                    break
            if found:
                break
        if found:
            f.SetPosition(v(x + found[0], y + found[1]))
            if found[3]:
                f.SetOrientationDegrees(f.GetOrientationDegrees() + found[3])
            ko[key] = (f, found[2])
            print(f"nudged {f.GetReference()} by ({found[0]:.2f},{found[1]:.2f}) rot {found[3]}")
        else:
            print(f"!! {f.GetReference()} at ({x:.1f},{y:.1f}) still overlaps; fix by hand")

    # 8. M2 standoff holes: start where the M4 hole would have moved, then search nearby for
    #    the spot that best clears (front) switch housings for an M2 screw head and
    #    (back) sockets / LEDs / diodes for a standoff or the acrylic spacer around it.
    fps = [f for f in b.GetFootprints() if not f.GetReference().startswith("__DEL__")]
    housings = unary_union([affinity.translate(affinity.rotate(box(-7, -7, 7, 7), -f.GetOrientationDegrees(), origin=(0, 0)), *pos(f))
                            for f in fps if is_choc(f)])
    kos = [fp_keepouts(f, socket=True) for f in fps]
    sw_side, solder_side = ("B", "F") if FLIP else ("F", "B")
    front = unary_union([k[sw_side] for k in kos])
    back = unary_union([k[solder_side] for k in kos])
    inside = outline.buffer(-2.2)
    NEED_HEAD, NEED_BACK, NEED_CU = 1.9, 2.0, 1.5
    for ref, x, y in holes:
        dx, dy = displacement(x, y)
        sx, sy = x + dx, y + dy
        def score(qx, qy):
            q = Point(qx, qy)
            if not inside.contains(q):
                return None
            return min(housings.distance(q) - NEED_HEAD, back.distance(q) - NEED_BACK,
                       front.distance(q) - NEED_CU) - 0.01 * math.hypot(qx - sx, qy - sy)

        best, best_s = None, -9.0
        for i in range(-32, 33):  # 0.25 mm grid over +-8 mm, then refine at 0.05 mm
            for j in range(-32, 33):
                sc = score(sx + i * 0.25, sy + j * 0.25)
                if sc is not None and sc > best_s:
                    best, best_s = (sx + i * 0.25, sy + j * 0.25), sc
        if best is not None:
            cx, cy = best
            for i in range(-5, 6):
                for j in range(-5, 6):
                    sc = score(cx + i * 0.05, cy + j * 0.05)
                    if sc is not None and sc > best_s:
                        best, best_s = (cx + i * 0.05, cy + j * 0.05), sc
        if best is None:
            print(f"!! {ref}: no room for an M2 hole near ({sx:.1f},{sy:.1f}), dropped")
            continue
        q = Point(best)
        if best_s < -0.1:  # an M2 head would hit a switch housing: fewer standoffs beats that
            print(f"{ref}: dropped (best spot only clears {housings.distance(q):.2f} mm to a housing)")
            continue
        make_m2_hole(b, ref, best)
        flag = "" if best_s >= -0.06 else "  !! tight"
        print(f"{ref}: M2 hole at ({best[0]:.2f},{best[1]:.2f}) head {housings.distance(q):.2f} back {back.distance(q):.2f} "
              f"cu {front.distance(q):.2f}{flag}")

    b.Save(dst)
    drop_front_pads(dst, STRIP_FRONT, FLIP)
    print("saved", dst, "outline bbox", [round(c, 1) for c in outline.bounds])


def is_choc(fp):
    return str(fp.GetFPID().GetLibItemName()) == "Choc_V1_Hotswap"


if __name__ == "__main__":
    main(*sys.argv[1:4])
