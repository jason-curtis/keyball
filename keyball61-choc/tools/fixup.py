#!/usr/bin/env python3.12
"""Finish the few connections Freerouting leaves open with a small grid A* router.

Usage: fixup.py <board.kicad_pcb>   (edits the board in place, refills zones)

For every "unconnected items" pair KiCad's DRC reports, search a 0.1 mm grid on both copper
layers around the pair. Obstacles are every other net's copper, holes, cut-outs and the board
edge, each inflated by clearance + half the track width. Vias are allowed where both layers are
free for the via pad. The path is added as 0.2 mm tracks (0.4 mm on GND/VCC) and 0.6/0.3 mm vias.
"""
import heapq
import json
import os
import subprocess
import sys

import numpy as np
import pcbnew
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert import cutout_box  # noqa: E402

MM = pcbnew.FromMM
TOMM = pcbnew.ToMM
GRID = 0.1
CLEAR = 0.15 + 0.02
EDGE = 0.3 + 0.02
VIA_D, VIA_DRILL = 0.6, 0.3
LAYERS = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}


def polyset_to_shapely(ps):
    polys = []
    for i in range(ps.OutlineCount()):
        ol = ps.Outline(i)
        pts = [(TOMM(ol.CPoint(k).x), TOMM(ol.CPoint(k).y)) for k in range(ol.PointCount())]
        if len(pts) >= 3:
            polys.append(Polygon(pts).buffer(0))
    return unary_union(polys)


def copper(board, layer):
    """Obstacles on one layer: (hard {net: geom}, holes geom, soft [(net, track, geom)]).

    Hard = pads and vias, soft = tracks (the router may rip those up)."""
    hard, holes, soft = {}, [], []

    def add(net, g):
        hard.setdefault(net, []).append(g)

    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetDrillSize().x > 0:
                holes.append(Point(TOMM(p.GetPosition().x), TOMM(p.GetPosition().y)).buffer(TOMM(p.GetDrillSize().x) / 2))
            if p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH and p.IsOnLayer(layer):
                add(p.GetNetname(), polyset_to_shapely(p.GetEffectivePolygon(layer)))
        cut = cutout_box(fp)
        if cut is not None:
            holes.append(cut)
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            c = Point(TOMM(t.GetPosition().x), TOMM(t.GetPosition().y))
            add(t.GetNetname(), c.buffer(TOMM(t.GetWidth(layer)) / 2))
            holes.append(c.buffer(TOMM(t.GetDrillValue()) / 2))
        elif t.GetLayer() == layer:
            st, en = t.GetStart(), t.GetEnd()
            ln = LineString([(TOMM(st.x), TOMM(st.y)), (TOMM(en.x), TOMM(en.y))])
            w = TOMM(t.GetWidth()) / 2
            soft.append((t.GetNetname(), t, ln.buffer(w) if ln.length else Point(TOMM(st.x), TOMM(st.y)).buffer(w)))
    return {k: unary_union(v) for k, v in hard.items()}, unary_union(holes), soft


def board_outline(board):
    ps = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(ps)
    return polyset_to_shapely(ps)


def unconnected(path):
    rpt = path + ".fix.json"
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-error", "-o", rpt, path],
                   check=True, stdout=subprocess.DEVNULL)
    d = json.load(open(rpt))
    os.remove(rpt)
    return d["unconnected_items"], [v for v in d["violations"]]


def endpoints(board, item):
    """Candidate (x, y, layer-name) points for a DRC item."""
    desc, u = item["description"], item["uuid"]
    pts = []
    for t in board.GetTracks():
        if str(t.m_Uuid.AsString()) == u:
            if t.GetClass() == "PCB_VIA":
                return [(TOMM(t.GetPosition().x), TOMM(t.GetPosition().y), ln) for ln in LAYERS]
            for q in (t.GetStart(), t.GetEnd()):
                pts.append((TOMM(q.x), TOMM(q.y), t.GetLayerName()))
            return pts
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if str(p.m_Uuid.AsString()) == u:
                return [(TOMM(p.GetPosition().x), TOMM(p.GetPosition().y), ln) for ln, l in LAYERS.items() if p.IsOnLayer(l)]
    x, y = item["pos"]["x"], item["pos"]["y"]
    return [(x, y, ln) for ln in LAYERS if ln in desc] or [(x, y, ln) for ln in LAYERS]


HOLE_CLEAR = 0.25 + 0.02
RIP_COST = 60.0  # per grid step through another net's track (it gets ripped up and re-routed)


def route_pair(board, net, starts, goals, cu, outline, width):
    xs = [p[0] for p in starts + goals]
    ys = [p[1] for p in starts + goals]
    x0, x1 = min(xs) - 8, max(xs) + 8
    y0, y1 = min(ys) - 8, max(ys) + 8
    nx, ny = int((x1 - x0) / GRID) + 1, int((y1 - y0) / GRID) + 1
    gx, gy = np.meshgrid(x0 + np.arange(nx) * GRID, y0 + np.arange(ny) * GRID, indexing="ij")
    inside = shapely.contains_xy(outline.buffer(-(EDGE + width / 2)), gx, gy)
    inside_v = shapely.contains_xy(outline.buffer(-(EDGE + VIA_D / 2)), gx, gy)
    free, soft, via_ok, via_soft = {}, {}, inside_v.copy(), np.zeros_like(inside_v)
    win = box(x0, y0, x1, y1)
    for ln in LAYERS:
        hard, holes, tracks = cu[ln]
        others = unary_union([g for n, g in hard.items() if n != net])
        blocked = shapely.contains_xy(others.buffer(CLEAR + width / 2), gx, gy) | \
            shapely.contains_xy(holes.buffer(HOLE_CLEAR + width / 2), gx, gy)
        vblocked = shapely.contains_xy(others.buffer(CLEAR + VIA_D / 2), gx, gy) | \
            shapely.contains_xy(holes.buffer(HOLE_CLEAR + VIA_D / 2), gx, gy)
        trk = unary_union([g for n, _, g in tracks if n != net and g.intersects(win)])
        tmask = shapely.contains_xy(trk.buffer(CLEAR + width / 2), gx, gy)
        free[ln] = inside & ~blocked
        soft[ln] = tmask
        via_ok &= ~vblocked
        via_soft |= shapely.contains_xy(trk.buffer(CLEAR + VIA_D / 2), gx, gy)

    def cell(x, y):
        return int(round((x - x0) / GRID)), int(round((y - y0) / GRID))

    goal_cells = {(*cell(x, y), ln) for x, y, ln in goals}
    for i, j, ln in goal_cells:  # the goal pad/track itself counts as free
        free[ln][i, j] = True
        soft[ln][i, j] = False
    li = list(LAYERS)
    openq, came, cost = [], {}, {}
    gxs = np.array([c[0] for c in goal_cells])
    gys = np.array([c[1] for c in goal_cells])

    def h(i, j):
        return float(np.min(np.hypot(gxs - i, gys - j)))

    for x, y, ln in starts:
        i, j = cell(x, y)
        free[ln][i, j] = True
        soft[ln][i, j] = False
        s = (i, j, ln)
        cost[s] = 0.0
        heapq.heappush(openq, (h(i, j), s))
    moves = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    found = None
    while openq:
        _, s = heapq.heappop(openq)
        if s in goal_cells:
            found = s
            break
        i, j, ln = s
        c0 = cost[s]
        nbrs = []
        for di, dj, w in moves:
            a, b_ = i + di, j + dj
            if 0 <= a < nx and 0 <= b_ < ny and free[ln][a, b_]:
                nbrs.append(((a, b_, ln), w + (RIP_COST if soft[ln][a, b_] else 0)))
        if via_ok[i, j]:
            other = li[1 - li.index(ln)]
            if free[other][i, j]:
                nbrs.append(((i, j, other), 25.0 + (RIP_COST if via_soft[i, j] else 0)))
        for n, w in nbrs:
            nc = c0 + w
            if nc < cost.get(n, 1e18):
                cost[n] = nc
                came[n] = s
                heapq.heappush(openq, (nc + h(n[0], n[1]), n))
    if not found:
        return None
    path = [found]
    while path[-1] in came:
        path.append(came[path[-1]])
    path.reverse()
    return [(x0 + i * GRID, y0 + j * GRID, ln) for i, j, ln in path]


def rip_crossed(board, net, path, cu, width):
    """Remove other nets' tracks that the new path runs through; returns how many."""
    victims = set()
    for ln in LAYERS:
        pts = [(x, y) for x, y, l2 in path if l2 == ln]
        vias = [Point(path[k][0], path[k][1]) for k in range(len(path) - 1) if path[k][2] != path[k + 1][2]]
        geoms = [Point(p).buffer(width / 2 + CLEAR) for p in pts] + [v.buffer(VIA_D / 2 + CLEAR) for v in vias]
        if not geoms:
            continue
        g = unary_union(geoms)
        for n, t, tg in cu[ln][2]:
            if n != net and tg.intersects(g):
                victims.add(t)
    for t in victims:
        board.Remove(t)
    return len(victims)


def add_path(board, net, path, width):
    ni = board.FindNet(net)
    # merge collinear runs
    simp = [path[0]]
    for k in range(1, len(path) - 1):
        a, b_, c = simp[-1], path[k], path[k + 1]
        if a[2] == b_[2] == c[2]:
            d1 = (b_[0] - a[0], b_[1] - a[1])
            d2 = (c[0] - b_[0], c[1] - b_[1])
            if abs(d1[0] * d2[1] - d1[1] * d2[0]) < 1e-9:
                continue
        simp.append(b_)
    simp.append(path[-1])
    n_t = n_v = 0
    for a, b_ in zip(simp, simp[1:]):
        if a[2] != b_[2]:
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetWidth(MM(VIA_D))
            v.SetDrill(MM(VIA_DRILL))
            v.SetNet(ni)
            board.Add(v)
            n_v += 1
            continue
        if (a[0], a[1]) == (b_[0], b_[1]):
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
        t.SetEnd(pcbnew.VECTOR2I(MM(b_[0]), MM(b_[1])))
        t.SetWidth(MM(width))
        t.SetLayer(LAYERS[a[2]])
        t.SetNet(ni)
        board.Add(t)
        n_t += 1
    return n_t, n_v


def main(path, rounds=8):
    path = os.path.abspath(path)
    last = None
    for rnd in range(int(rounds)):
        items, viol = unconnected(path)
        items = [it for it in items if "[GND]" not in it["items"][0]["description"]]
        if not items:
            break
        if last is not None and len(items) >= last[0] and rnd > 3:
            break
        last = (len(items),)
        b = pcbnew.LoadBoard(path)
        outline = board_outline(b)
        done = ripped = 0
        for it in items:
            cu = {ln: copper(b, l) for ln, l in LAYERS.items()}
            a, c = it["items"][0], it["items"][1]
            net = a["description"].split("[", 1)[1].split("]", 1)[0]
            width = 0.4 if net == "VCC" else 0.2
            path_ = route_pair(b, net, endpoints(b, a), endpoints(b, c), cu, outline, width)
            if not path_:
                print(f"  no path for {net}")
                continue
            ripped += rip_crossed(b, net, path_, cu, width)
            add_path(b, net, path_, width)
            done += 1
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        b.Save(path)
        print(f"round {rnd + 1}: routed {done}/{len(items)}, ripped {ripped} tracks", flush=True)
    items, viol = unconnected(path)
    print(f"final: {len(viol)} violations, {len(items)} unconnected")


if __name__ == "__main__":
    main(sys.argv[1])
