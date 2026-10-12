# Keyball61 Choc — tooling to iterate on the PCB

Everything here is scripted, so the boards can be regenerated from Yowkees' original Keyball61 KiCad
files after any tweak to the conversion parameters.

## What you need

| Tool | Version used | Why |
|---|---|---|
| KiCad | **9.0.x** (9.0.9 used) | `pcbnew` Python module, `kicad-cli pcb drc / export`. KiCad 7's CLI has no DRC, and its Python Specctra export misbehaves. |
| Python | **3.12**, i.e. the interpreter KiCad's `pcbnew` module is built for | runs `tools/*.py` |
| shapely | ≥ 2.0 | outline / clearance geometry in `convert.py` |
| Java | 17+ | runs Freerouting |
| Freerouting | **1.9.0** jar | autorouter (Specctra DSN → SES) |
| xvfb (Linux, headless only) | any | Freerouting 1.9 opens a hidden window even in batch mode. `route.py` wraps it in `xvfb-run` when `$DISPLAY` is unset. |
| numpy, ezdxf | any | grid router (`fixup.py`), plate DXFs (`plates.py`) |
| cairosvg (optional) | any | turns `kicad-cli` SVG exports into PNG previews |

### Ubuntu 24.04 (what the cloud sessions use)

```sh
# KiCad 9 from the official PPA. add-apt-repository can't reach Launchpad's API from some
# sandboxes, so the key and source are added by hand:
curl -sS "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x245D5502FAD7A805" \
  | gpg --dearmor > /usr/share/keyrings/kicad-ppa.gpg
echo "deb [signed-by=/usr/share/keyrings/kicad-ppa.gpg] https://ppa.launchpadcontent.net/kicad/kicad-9.0-releases/ubuntu noble main" \
  > /etc/apt/sources.list.d/kicad9.list
apt-get update
apt-get install -y --no-install-recommends kicad xvfb xauth default-jre-headless

python3.12 -m pip install --break-system-packages shapely numpy ezdxf cairosvg

mkdir -p ~/tools
curl -L -o ~/tools/freerouting.jar \
  https://github.com/freerouting/freerouting/releases/download/v1.9.0/freerouting-1.9.0.jar
```

Check the install with `python3.12 -c "import pcbnew; print(pcbnew.Version())"`. It should print 9.0.x.
If `python3` is newer than the Python KiCad was built for (3.13 on this image), call `python3.12`
explicitly. The scripts' shebangs already do.

### macOS

Install KiCad 9 from kicad.org and use its bundled Python, which has `pcbnew`:
`/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`.
`pip install shapely` into that interpreter, install a JDK (`brew install openjdk`), and download the
Freerouting jar. No xvfb is needed because a display exists.

## Pipeline

```sh
# 0. unpack the originals (they live in keyball61/design_data)
unzip keyball61/design_data/keyball61_Right_KiCad.zip -d /tmp/kb61
unzip keyball61/design_data/keyball61_Left_KiCad.zip  -d /tmp/kb61

# 1. convert MX 19.05 mm -> Choc 18x17 mm (positions, footprints, outline, holes)
python3.12 keyball61-choc/tools/convert.py right /tmp/kb61/keyball61_Right_KiCad/keyball61_right.kicad_pcb /tmp/kb61/right.kicad_pcb
python3.12 keyball61-choc/tools/convert.py left  /tmp/kb61/keyball61_Left_KiCad/keyball61_Left.kicad_pcb  /tmp/kb61/left.kicad_pcb

# 2. route: Freerouting, DRC-driven rip-up/re-route rounds, then tools/fixup.py (grid A* router with
#    rip-up) for the last few nets, then GND pours. Takes ~30–60 min per half.
python3.12 keyball61-choc/tools/route.py /tmp/kb61/right.kicad_pcb keyball61-choc/pcb/right/keyball61_choc_right.kicad_pcb ~/tools/freerouting.jar 30
python3.12 keyball61-choc/tools/route.py /tmp/kb61/left.kicad_pcb  keyball61-choc/pcb/left/keyball61_choc_left.kicad_pcb  ~/tools/freerouting.jar 30

# 3. DRC
kicad-cli pcb drc --severity-error -o right-drc.rpt keyball61-choc/pcb/right/keyball61_choc_right.kicad_pcb

# 4. fab outputs (gerbers, drill, JLC BOM/CPL) and acrylic bottom plates
python3.12 keyball61-choc/tools/fab.py
python3.12 keyball61-choc/tools/plates.py

# fixup.py also runs standalone on any board after hand edits:
python3.12 keyball61-choc/tools/fixup.py keyball61-choc/pcb/right/keyball61_choc_right.kicad_pcb
```

The KiCad project files can be opened in the KiCad 9 GUI for hand touch-ups. The footprint library is
`keyball61-choc/pcb/keyball61_choc.pretty` (Choc v1 hotswap and M2 hole).

## Gotchas found along the way (so you don't rediscover them)

- **The left PCB is mounted upside down.** Keyball's halves are one reversible design: on the left board,
  switches enter from the file's B side and parts are soldered on F.Cu. `convert.py` flips the Choc
  footprints and keeps the F-side pads of the "BOTH" diode and LED footprints on the left.
- **Specctra export** fails on references with spaces or duplicates ("BACK SIDE ONLY" ×2), on the
  Keyball logo footprints, and on custom-shape solder-jumper pads. `convert.py` renames references to
  unique names (`BACK_SIDE_ONLY_2`, `LED_CUT`, …). `route.py` routes a sanitized copy without logos
  and with rect jumper pads.
- **SES import:** KiCad rejects Freerouting 1.9's duplicated via padstacks, so `route.py` has its own small
  SES importer.
- **Freerouting can stall** once nothing is left that it can route. Each run has a 30-minute timeout, and the
  best earlier pass is kept.
- **Keyball's cut jumpers** overlap their pads by design (normally closed). The routing copy drops the bridge pad
  and approximates the arrow pads with non-overlapping boxes. Their 0.1905 mm per-pad clearance override is
  stripped so the 0.15 mm board rule applies.
- **LED cut-outs** are drawn as four thin Edge.Cuts lines. Treat them as filled boxes in any geometry check,
  or parts get placed and tracks routed into the hole.
- **BOARD.Remove() still corrupts SWIG proxies on KiCad 9** when another board is loaded later in the same
  process. The scripts delete tracks by uuid in the saved file instead.
- **KiCad 7 SWIG quirks:** removing items through the Python API corrupts proxies. The scripts mark
  items and strip them from the saved file text instead. That approach also works on KiCad 9.
