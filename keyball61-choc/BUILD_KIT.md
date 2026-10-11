# Keyball61 Choc — build kit, PCB and priced BOM

A Keyball61 converted to **Kailh Choc v1 at Choc spacing (18 × 17 mm)**, with **quiet, standard-weight
low-profile linears**, keeping everything that makes a Keyball a Keyball:
- the 34 mm PMW3360 thumb trackball (same ball case, same notch, same sensor board);
- OLEDs, 71 SK6812MINI-E LEDs (per-key + underglow);
- wired TRRS split, Pro Micro-footprint RP2040 controllers;
- **the unchanged Keyball61 switch matrix and pinout**, so the stock Keyball61 QMK firmware runs as-is.

Prices checked 2026-10-11 in USD. **(est.)** marks figures that could not be quoted live.

> **Status: v0.1, unbuilt prototype.** The PCBs are generated, routed and DRC-checked, but nobody has
> fabricated one yet. Read §7 before ordering.

---

## 1. Why a new PCB: no Choc-spacing Keyball exists

| Candidate | Spacing | Verdict |
|---|---|---|
| Keyball39 / 44 / 61 / 61+ / Keyball+ (Yowkees, holykeebs) | 19 mm (measured from the KiCad files) | Choc sockets are offered, but only at MX pitch. |
| ~200 GitHub repos named "keyball" | — | Firmware, keymaps and cases only. None is a Choc-pitch PCB. |
| torabo-tsuki LP **L** (64 keys) | **19 mm** (measured: sockets step 28→47→66 mm) | Only its 42–52-key MS/XS sizes are 17 mm. It also uses a 25 mm ball, ZMK and AA cells. |
| Crosses V2 | Choc v1, pitch unconfirmed | 54 keys max, dual ball, sold out. |
| holykeebs Lily58 / Corne Choc | 18 × 17 ✔ | No thumb trackball (only the small Pimoroni module, sold out). |
| Klorball35 | 18 × 17 ✔ | 35 keys, 25 mm ball. |

So this folder forks Yowkees' GPL-3.0 KiCad source (`keyball61/design_data/*_KiCad.zip`) into a Choc
version. The conversion is fully scripted; see [TOOLING.md](TOOLING.md).

## 2. What changed vs. Keyball61

- **Key grid:** 19.05 mm → **18 mm × 17 mm**.
  - Column 5 and row 3 are the anchors. The **trackball notch, ball-PCB contact (J2) and thumb cluster keep their exact original geometry**, so the stock Keyball trackball case fits unchanged.
  - The finger columns pull in toward the ball: up to 4.2 mm sideways and 6 mm vertically.
- **Switch footprint:** MX hotswap → **Kailh Choc v1 hotswap (CPG135001S30)** on all 61 keys.
  - Per-key LEDs sit under the Choc LED window, 4.7 mm south of key centre.
- **Single-sided parts placement.** Sockets, diodes, LEDs and pull-ups are all on the solder side, so JLC can assemble each half as a one-sided job.
  - Keyball's left PCB is mounted upside down, so its "solder side" is the file's F.Cu.
- **Case:** M4 spacer holes → **M2** holes, re-placed into the Choc key gaps.
  - They keep ≥1.9 mm from switch housings for screw heads and ≥2 mm from sockets for standoffs.
  - New outlines and 2 mm acrylic bottom plates are included. The right plate fills the notch and carries the original ball-case screw holes.
- **Board size:** the outline is regenerated from the Choc key cells and is about 10 % smaller.
- **Routing:** fully re-routed (Freerouting), with GND pours on both layers, 0.25 mm signals, 0.5 mm power and 0.3 mm copper-to-edge.
- **Unchanged:**
  - every net: matrix, LED chain order, OLED/I²C, TRRS, the left/right jumpers and the ball connector;
  - firmware;
  - the trackball sensor board.

## 3. Files

| Path | What |
|---|---|
| `pcb/left/`, `pcb/right/` | KiCad 9 projects (`keyball61_choc_{left,right}.kicad_pcb`), with DRC rules |
| `pcb/keyball61_choc.pretty/` | Choc v1 hotswap and M2 hole footprints |
| `fab/{left,right}/` | **Order files:** gerber zip, JLC BOM, JLC CPL |
| `case/` | 2 mm acrylic bottom plates (DXF) |
| `tools/` | `convert.py` → `route.py` → `fab.py` / `plates.py` |
| `renders/` | PNG previews |

---

## 4. Ordering — what to buy, where

### 4a. JLCPCB: PCBs + assembly (one order)

Upload `fab/left/keyball61_choc_left_gerbers.zip` and `fab/right/…_gerbers.zip` as two designs. Settings:
- 2 layers, 1.6 mm FR-4, HASL lead-free or ENIG;
- any colour (black or white looks like the original);
- qty 5;
- **remove the order number** (or place it with "specify position").

**PCB Assembly:** enable it with qty 2, using the BOM/CPL in each `fab/<side>/` folder.

| Side to assemble | Left board: **Top** (the file's F.Cu is the solder side) · Right board: **Bottom** |
|---|---|

What JLC places:

| Part | LCSC | Per kb | Note |
|---|---|---|---|
| Kailh Choc v1 hotswap socket CPG135001S30 | C5333465 | 61 | Extended part. **JLC stock is 0 today:** pre-order it through JLC "Parts Manager → Order Parts" before placing the PCBA order, or consign typeractive/holykeebs sockets. |
| 1N4148W SOD-123 | C81598 | 71 | Basic part |
| SK6812MINI-E | C5149201 | 71 | Extended part, 190k in stock. Reverse-mount into the PCB cut-outs: confirm orientation in JLC's DFM preview. |
| 4.7 kΩ 0603 (I²C pull-ups) | C23162 | 4 | Basic part |
| *Optional THT:* PJ-320A TRRS jack | C2884926 | 2 | JLC can do through-hole; you can also hand-solder it |
| *Optional THT:* 2-pin reset tact switch | C139766 | 2 | |

**Estimated cost** (JLC needs a live quote; 2 assembled + 3 bare boards per half):

| | |
|---|---|
| PCBs, 2 designs × 5 | ~$35–50 |
| PCBA: setup, stencil, extended-part fees, joints | ~$50–80 |
| Placed parts (2 kb worth) | ~$20 |
| Shipping + US tariff/handling | ~$25–40 |
| **Total** | **≈ $130–190** (est.) |

You get **two complete sets** of assembled boards, i.e. a spare keyboard's worth.

### 4b. Bottom plates

Have the two `case/*_bottom_2mm.dxf` files laser-cut in 2 mm acrylic, for example at JLCPCB CNC/laser,
SendCutSend or Ponoko. **≈ $25–40** (est.).

Hardware:
- M2 × 4 mm F-F hex standoffs: 17;
- M2 × 4 mm low-profile screws: 34;
- rubber bumpers: ~8.

An Amazon M2 assortment is **≈ $10**.

### 4c. DigiKey cart (things JLC doesn't place)

| Qty | Part | DigiKey PN | Unit | Line |
|---|---|---|---|---|
| 1 | Mill-Max 0.1" low-profile socket strip, 64-pin. Snap it into 4 × 12 for the controllers. | (mfr 315-43-164-41-003000) | $12.29 | $12.29 |
| 2 | 4-pin female header for the OLEDs | S7002-ND | $0.42 | $0.84 |
| 2 | Adafruit KB2040 (RP2040, Pro Micro footprint) | 5302 listing | $8.95 | $17.90 |
| 2 | 6 × 3.5 mm 2-pin tact switch, reset (if not JLC). The footprint pitch is 6.5 mm: check the datasheet. | e.g. CKN12303-ND | $0.17 | $0.34 |
| — | **Subtotal** | | | **$31.37** |

DigiKey doesn't carry the following, so they go in §4d:
- PMW3360 / LM19-LSI, SK6812MINI-E and the Kailh sockets (JLC places them anyway);
- the 34 mm ball;
- generic 0.91" OLEDs. DigiKey's Adafruit 4440 has a different pinout, so skip it.

### 4d. Other vendors

| Qty | Part | Vendor | Line |
|---|---|---|---|
| 1 | **Pre-soldered Keyball trackball sensor board** (PMW3360 + LM19-LSI lens, tested) | Shirogane Lab (JP), ¥4,800: https://shiroganelab.com/products/keyball-pre-soldered-trackball-sensor-lens-set. Stock is unclear, so check before ordering. | ~$32 + JP shipping |
| 1 | L-shaped 7-pin Conthrough spring header (joins the ball board to J2) | Shirogane Lab (¥240, sometimes sold out), or ask holykeebs | ~$2 |
| 1 | Keyball trackball case (resin, 3 ceramic bearings) | holykeebs.com | $15 |
| 1 | 34 mm trackball (Perixx), black | holykeebs.com | $15 |
| 2 | OLED 128×32 0.91" | holykeebs.com | $10 |
| 3 | **Kailh Choc v1 Silent "Plum Blossom" 45 gf linear**, 20-pack | moergo.com (ships from US) | $54 |
| 51 | **FK Keycaps custom MBK PBT**, 1U, your legends | custom.fkcaps.com | ~$54 + $9 ship (est.) |
| — | holykeebs and MoErgo shipping | | ~$15 (est.) |

Sensor board, DIY alternative:
- Fab Yowkees' `keyball46/ball_design_data/Trackball_PCB_gerber.zip` at JLC (~$5).
- Parts from DigiKey: TPS73601DBVR (296-18255-1-ND, **backordered to Nov 16**), 2 × TXS0102DCUR (296-21912-1-ND) and passives (10 µF ×3, 0.1 µF ×4, 37.4k, 63.4k, 3 × 10k, 39 Ω, 4 × 0 Ω), about $8.
- PMW3360DM-T2QU + LM19-LSI from AliExpress, ~$15.
- The VSSOP-8 level shifters are fiddly to hand-solder, so the pre-assembled board is the recommended route.

### 4e. Reused from your holykeebs order #2353

| Item | Use |
|---|---|
| 10 × Ambients Silent Choc **Nocturnal 20 g** | The 5 thumb keys (3 left + 2 right) plus the 2 inner keys, plus 3 spares. A light thumb is a common preference. |
| 10 × white MBK 1U | Keycaps for those same 7 keys, plus spares |
| TRRS cable 80 cm, tenting feet | Move them between boards, or buy a second cable ($5) |

## 5. Totals

| Block | Cost |
|---|---|
| JLCPCB PCB + assembly + shipping | ≈ $130–190 (est.) |
| Bottom plates + M2 hardware | ≈ $35–50 (est.) |
| DigiKey cart | $31 |
| Sensor board + connector + case + ball | ≈ $65 + JP shipping |
| OLEDs | $10 |
| Switches | $54 |
| Keycaps | ≈ $63 (est.) |
| Misc shipping | ≈ $15 |
| **Total** | **≈ $400–480**, for a spare set of assembled PCBs as well |

## 6. Build steps (what's left for you to solder)

1. **Controllers:**
   - Solder the Mill-Max socket strips on the switch side.
   - Fit the KB2040s with their pins.
   - Same Pro Micro footprint as Keyball61.
2. **OLED headers:** solder the 4-pin female header, then plug in the OLEDs. Add TRRS and reset too if you didn't have JLC do them.
3. **Left/right jumpers:** bridge the `BACK_SIDE_ONLY` / `LEFT` solder jumpers exactly as in the Keyball61 build guide, steps 5 and 8. Their positions are unchanged relative to the controller.
4. **Ball contact:** solder the L-shaped 7-pin Conthrough to J2 on the right half, then push the sensor board on and fit the ball case.
5. **Case:** add standoffs and the bottom plate, then switches and caps.

**Firmware:** the stock Keyball61 QMK keyboard (`qmk_firmware/keyboards/keyball/keyball61`). For RP2040 controllers, use holykeebs' QMK fork or a QMK converter build (`CONVERT_TO=kb2040`). The matrix, LED order and pins are unchanged.

## 7. Before you order: check these

- **Open both boards in KiCad 9 and look them over.** They are machine-generated. DRC is clean on errors (see `pcb/*/drc.rpt`), but nobody has reviewed them by eye yet.
- **Optionally print the PCB at 1:1** and set a few Choc switches, MBK caps, the ball case and your hand on it.
- **Ball case fit.** The notch and J2 are unchanged, but the bottom-row keys around the notch moved slightly. The ball case's outer shell isn't in Yowkees' repo, so check it physically or against the holykeebs case dimensions.
- **Sockets at JLC.** Order C5333465 into your JLC parts library first.
- **Thumb keys.** They keep Keyball's original positions and angles. The finger columns moved, so on the right half the thumbs end up ≈4 mm further inboard relative to the index column than on your MX board.
- **TRRS jack.** The footprint is Keyball's MJ-4PP-9 / PJ-320A pattern. If JLC places C2884926, check its pin mapping in the DFM preview.
