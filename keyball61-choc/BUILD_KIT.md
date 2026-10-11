# Keyball61 Choc — build kit & priced BOM

Goal: a Keyball61 with **Kailh Choc spacing (18 × 17 mm)**, **low-profile, quiet, standard-weight linear switches**,
the same 34 mm thumb trackball (PMW3360), OLEDs, per-key RGB, wired TRRS split — as close to the
holykeebs Keyball61 (order #2353, Nov 2024) as possible.

Prices checked 2026-10-11, USD. Items marked **(est.)** could not be quoted live and need a final check at checkout.

---

## 1. Does a choc-spacing Keyball already exist?

**No.** Findings:

| Candidate | Spacing | Why it isn't the answer |
|---|---|---|
| Keyball39 / 44 / 61 / 61+ / Keyball+ (Yowkees, holykeebs) | 19 mm (measured on `keyball61_Right_KiCad`: columns 99→118→137→156…) | Choc sockets are offered, but only at MX pitch. holykeebs' own board finder lists Keyball as "standard 19 × 19". |
| ~200 GitHub repos matching "keyball" | — | Firmware/keymaps/cases only. No choc-pitch PCB fork. |
| torabo-tsuki LP **L** (64 keys, "like Keyball61") | **19 mm** (measured from its KiCad: sockets step 28→47→66 mm) | Not choc spacing. Only the 42–52-key MS/XS sizes are 17 mm. It also uses Choc v2, a 25 mm ball, ZMK, and AA batteries. |
| Crosses V2 (Ergo Keyboards) | Choc v1, pitch unconfirmed | 54 keys max, dual ball, wireless only, sold out. Main-key PCB not published. |
| holykeebs Lily58 Choc / Corne Choc | 18 × 17 ✔ | Pointing is the small Pimoroni module (sold out), not a 34 mm thumb ball. |
| Klorball35 | 18 × 17 ✔ | Keyball-derived with PMW3360, but only 35 keys and a 25 mm ball. Gerbers only. |
| cocot46-lp, Rollow, roBa, Drift, Ergohaven K:04, Charybdis | — | Mini ball, no ball, MX pitch, or no choc version. |

**Conclusion:** to get a real Keyball61 at choc pitch, we convert Yowkees' published KiCad source
(`keyball61/design_data/keyball61_{Left,Right}_KiCad.zip`, GPL-3.0, so a fork is allowed) into a
**Keyball61 Choc** PCB and fab it at JLCPCB. Everything else on the bill is off-the-shelf.

### PCB conversion scope (the one piece of real work)
- Swap `CherryMX_MidHeight_Hotswap` for a Choc v1 hotswap (PG1350 / CPG135001S30) footprint, and re-grid the 61 keys to 18 × 17 mm.
- Keep the Pro Micro footprint (`ProMicro_v2_for61`), OLED header, TRRS, reset switch, SK6812 MINI-E chain and matrix wiring **unchanged**. That way the stock Keyball61 QMK keyboard (`qmk_firmware/keyboards/keyball/keyball61`) runs with no matrix changes; only the LED positions in `info.json` move.
- Keep the 34 mm ball cut-out and sensor-board mount from the original. The ball doesn't shrink, so the keys around it can't simply move inward; they need hand placement.
- Regenerate the FR4 top/mid plates and acrylic middle/bottom DXFs to the smaller outline. The board gets about 6–10 % narrower per half.
- Re-route the traces. This is most of the effort.
- Fab-ready output: gerbers, BOM and CPL for JLCPCB, with SMT assembly of diodes + sockets optional.

---

## 2. Reuse from order #2353

| Part | Reuse? | Notes |
|---|---|---|
| Ambients Silent Choc **Nocturnal 20g** × 10 | ✅ Yes | Choc v1. Use them on the 5 thumb keys of each half (very light thumbs are a common preference), or keep as spares. |
| MBK low-profile keycaps, white 1U × 10 | ✅ Yes | Choc v1 stem, true choc size. Use on the thumbs, or as spares/homing. |
| TRRS cable 80 cm | ✅ Yes, if you'll swap boards | Otherwise buy a second one ($5). |
| Tenting feet | ✅ Yes, if swapping | Currently **sold out** at holykeebs. |
| Sea Picro × 2, OLED × 2, PMW3360 sensor, 34 mm ball, ball case | ⚠️ Only by cannibalizing your daily driver | Keyball61 builds are usually soldered/socketed. The BOM below buys new ones so the old board stays usable. Reusing the controllers + OLEDs saves about $26. |
| Outemu Silent Peach v3 (MX), Tai-Hao MX caps, acrylic plates, LEDs (soldered) | ❌ No | MX parts, or board-specific. |

---

## 3. Switches — recommendation

Wanted: quiet + low throw + linear + standard weight, Choc v1 so the MBK caps fit.

| Pick | Switch | Force | Price | Notes |
|---|---|---|---|---|
| **⭐ Primary** | **Kailh Choc v1 Silent "Plum Blossom"** (MoErgo, ships from USA) | 45 gf linear | $18 / 20-pack | Silenced Choc v1, made for Glove80. US stock, no tariff. Cheapest per switch. https://www.moergo.com/products/ships-from-usa-kailh-choc-v1-silent-key-switches-golden-kiwi-cherry-blossom-plum-blossom-20-pack |
| Runner-up | **Ambients Silent Choc "Bokeh"** (lowprokb, Canada) | 50 g linear | $9 / 10 | Same family as your Nocturnals, so the sound matches. Damped on press and release. 3.0 mm travel. https://lowprokb.ca/products/ambients-silent-choc-switches |
| Lighter alt. | Ambients **Twilight** (holykeebs US or lowprokb) | 35 g linear | $9 / 10 | Closest to the light feel of the Silent Peach. |

Avoid for this build:
- **Choc v2** silent switches (Kailh Deep Sea Islet, Purple Iris): MX-cross stem, so no MBK caps and no FK MBK.
- **Gateron KS-33** and **Lofree LP**: different footprint, won't fit Choc sockets.

Count: 61 keys. With the 10 Nocturnals on the thumbs, you need 51 new switches plus spares.
- **Primary:** 3 × 20-pack Plum Blossom gives 60 (63 with bonus spares). **$54**
- If you'd rather not use the Nocturnals on the thumbs: 4 × 20-pack, **$72**.

---

## 4. Keycaps (re-order from FK Keycaps)

FK's custom builder (https://custom.fkcaps.com/custom) offers **MBK** in three "CHOC ONLY" variants: ABS PU shine-through, PBT, and PBT PU.
- **Size:** MBK is 17.5 × 16.5 mm on a Choc v1 stem, so it fits the 18 × 17 pitch exactly.
- **Profiles to avoid:** don't pick LPF/KLP. They're MX-stem and MX-sized.
- **Price:** FK only shows it at checkout. The last public data point is about $1.05/key including shipping (54 keys → $63). Shipping is a $9 flat rate; delivery is 6–14 days.
- **What to order:** recreate your legends on **MBK PBT**, 51 × 1U (all Keyball61 keys are 1U). The thumbs reuse your 10 white MBK caps. Order 61 if you want the thumbs legended too.

Budget fallback: blank MBK/LDSA $3.50 per 10 from holykeebs/typeractive, about $21 for 60.

---

## 5. Full BOM — "Keyball61 Choc", wired, both halves

**Assumptions:**
- Reuse 10 Nocturnals + 10 MBK caps on the thumbs.
- Buy fresh controllers, OLEDs and trackball parts; your current board stays intact.
- PCBs hand-soldered. JLC SMT assembly is optional, in the note under the table.

| # | Part | Qty | Vendor | Unit | Line |
|---|---|---|---|---|---|
| 1 | Keyball61 Choc main PCB L+R (JLCPCB, 2-layer 1.6 mm, min qty 5 per design) | 5 ea. | jlcpcb.com | — | **~$45 (est.)** |
| 2 | FR4 top/mid plates L+R (JLCPCB) | 5 ea. | jlcpcb.com | — | **~$30 (est.)** |
| 3 | JLC shipping (DHL/FedEx, combined) | 1 | jlcpcb.com | — | **~$25 (est.)** |
| 4 | Acrylic middle + bottom plates (laser cut, from regenerated DXFs) | 1 set | JLCPCB CNC/laser, or Ponoko | — | **~$40 (est.)** |
| 5 | Kailh Choc v1 hotswap sockets (PG1350) | 70 (7 × 10) | typeractive.xyz | $1.50/10 | $10.50 |
| 6 | 1N4148W SOD-123 diodes | 70 (7 × 10) | typeractive.xyz | $0.75/10 | $5.25 |
| 7 | RP2040 Pro Micro (USB-C) — Sea Picro is discontinued | 2 | holykeebs.com | $8 | $16.00 |
| 8 | Machine-pin headers/sockets for controllers | 2 sets | holykeebs.com | $3 | $6.00 |
| 9 | OLED 128×32 | 2 | holykeebs.com | $5 | $10.00 |
| 10 | Reset buttons | 2 | typeractive.xyz | $1.50/2 | $1.50 |
| 11 | TRRS jacks PJ-320A (+ a few spares) | 4 | LCSC / AliExpress | ~$0.30 | **~$2 (est.)** |
| 12 | SK6812 MINI-E LEDs (optional, 71) | 80 (8 × 10) | holykeebs.com | $2.80/10 | $22.40 |
| 13 | 34 mm trackball (Perixx, black) | 1 | holykeebs.com | $15 | $15.00 |
| 14 | Keyball trackball case (resin, 3 ceramic bearings) | 1 | holykeebs.com | $15 | $15.00 |
| 15 | PMW3360 sensor board (see note) | 1 | AliExpress / Kivipallur breakout via JLC | — | **~$25 (est.)** |
| 16 | **Switches**: Kailh Choc v1 Silent Plum Blossom 45 gf | 3 × 20-pack | moergo.com | $18 | $54.00 |
| 17 | **Keycaps**: FK custom MBK PBT, 51 × 1U | 51 | custom.fkcaps.com | ~$1.05 | **~$54 + $9 ship (est.)** |
| 18 | M2 spacers/screws, rubber feet | 1 set | Amazon / AliExpress | — | **~$10 (est.)** |
| 19 | TRRS cable 80 cm (skip if reusing) | 1 | holykeebs.com | $5 | $5.00 |
| | **Vendor shipping** (holykeebs, typeractive, MoErgo) | | | | **~$25 (est.)** |
| | **Total** | | | | **≈ $430** |

Ways to cut cost:
- Reuse the Sea Picros and OLEDs from the old board: −$26.
- Skip the RGB: −$22.
- Use blank MBK caps instead of FK custom: −$42.
- Lean build (all three of the above): **≈ $340**.

Note on JLC SMT assembly: having JLC place the diodes and hotswap sockets adds roughly $30–60 in setup and parts. It removes the most tedious soldering.

Note on the **PMW3360**: holykeebs no longer sells the sensor on its own, only inside Keyball kits. There are two routes:
- Order the Kivipallur / Klorball35 sensor breakout, which has a JLC BOM/CPL (https://github.com/dr3san/Kivipallur).
- Buy a PMW3360 module on AliExpress that matches the Keyball sensor-board pinout.

Either way, confirm the pinout before ordering. If neither works out, the fallback is to email holykeebs. They sell the sensor as part of the Keyball kits, so they may sell one on its own.

### Where to order (grouped)
| Vendor | Items |
|---|---|
| **holykeebs.com** | 2× RP2040 Pro Micro, 2× headers, 2× OLED, 8× SK6812 MINI-E 10-pack, 34 mm ball (black), Keyball trackball case, (TRRS cable) |
| **typeractive.xyz** | 7× Choc hotswap sockets 10-pack, 7× 1N4148W 10-pack, 1× reset switch 2-pack |
| **moergo.com** | 3× Kailh Choc v1 Silent Plum Blossom 20-pack (US ship) |
| **custom.fkcaps.com** | 51× MBK PBT custom-legend 1U |
| **jlcpcb.com** | PCBs + FR4 plates + acrylic (+ optional SMT assembly). Gerbers come from the conversion. |
| **LCSC / AliExpress** | PJ-320A TRRS jacks, PMW3360 module, M2 hardware |

---

## 6. Alternatives if you'd rather not fab a PCB

1. **holykeebs Keyball61+ with Choc v2 sockets ($200, soldered).**
   - Gets you low-profile switches today with full Keyball features and the 34 mm ball.
   - Still 19 mm spacing.
   - Needs Choc v2 silent switches (e.g. Kailh Deep Sea Islet 43 g, $6.50/10) and MX-stem low-profile caps.
2. **holykeebs Lily58 Choc ($27 PCB kit + parts).**
   - True 18 × 17, 58 keys.
   - Gives up the thumb ball; the only pointing option is the Pimoroni module (sold out).
3. **torabo-tsuki LP MS size.**
   - 17 mm pitch, 25 mm ball, ZMK wireless.
   - The MS size is marked untested by its designer, has fewer keys, and must be bought from Japan via BOOTH.
