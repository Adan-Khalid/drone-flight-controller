# Simulation guide (KiCad simulator)

Three small circuits from the board are simulated in KiCad's built-in simulator (ngspice) before the board is ordered. Each one checks a calculation in `reports/design_calcs.md` (section 7) with an independent tool. I build and run them in KiCad myself; each run produces a plot (PNG), the data (CSV) and a saved simulator workbook.

| Circuit | Question it answers | Analysis |
| --- | --- | --- |
| A. Battery voltage divider | Does the processor's ADC pin settle to the right voltage, fast enough, and is noise above 170 Hz filtered? | Transient and AC |
| B. Sensor supply filter | How much of the regulators' switching ripple (1.5 to 2 MHz) reaches the sensor LDO? | AC |
| C. Motor output edge | Is a DShot600 edge through the 220 Ω protection resistor still sharp compared with the 1.67 µs bit? | Transient, plus the tuning tool |

The menu names below are from the KiCad 10 manual (Schematic Editor, "Simulator" chapter). KiCad also ships example projects in its `demos/simulation` folder, which are a good first look.

## Before you start

- KiCad 10.0.8 is installed.
- Open `reports/design_calcs.md`, section 7: those are the numbers each simulation should reproduce.
- Make a folder per circuit: `sim/battery_divider/`, `sim/sensor_filter/`, `sim/motor_edge/`. Plots and data go to `reports/figures/` and `reports/sim/`.

## How every simulation is built (same steps each time)

1. **New project.** In the main KiCad window, create a new project (File menu) saved inside the circuit's folder in `sim/` (for example `sim/battery_divider/battery_divider.kicad_pro`). Open its schematic.
2. **Resistors and capacitors.** Press `A` (or the add-symbol button) to open the Choose Symbols dialog; take `R` and `C` from the `Device` library. Type the value only (`150k`, `10k`, `100n`). KiCad gives two-pin parts whose reference starts with R, L or C an ideal simulation model automatically, so nothing else is needed.
3. **Sources and ground.** From the `Simulation_SPICE` library: `VPULSE` (a pulse or step), `VSIN` or `VDC` (for AC analysis), and `0` (the simulation ground, node 0). Every circuit needs the `0` symbol.
4. **Source settings.** Double-click the source → Simulation Model… → Parameters tab. Fill in the values given for each circuit below. For an AC analysis the source needs an AC magnitude (the `ac` parameter): set it to 1, so the plot shows the circuit's gain directly.
5. **Name the nets.** Put a net label (label tool on the right-hand toolbar) on the important wires (`VBAT`, `ADC`, and so on). The signal list in the simulator then shows `V(ADC)` instead of an anonymous node number.
6. **Run.** Inspect → Simulator. In the simulator window: Simulation → New Analysis Tab… (Ctrl+N), choose TRAN or AC, fill the options, then Simulation → Run Simulation (R).
7. **Plot.** Tick the plot box next to a signal, or use Simulation → Probe Schematic… (P) and click a wire.
8. **Measure.** Tick Cursor 1 and Cursor 2 next to a signal and drag them; the cursor table shows both values and their difference. Right-click a signal for ready-made measurements (Measure Max, Measure Min, Measure Peak-to-peak).
9. **Keep the evidence.** File → Export Current Plot as PNG… into `reports/figures/`, File → Export Current Plot as CSV… into `reports/sim/`, and File → Save Workbook into the circuit's `sim/` folder. Use the file names given below.
10. **Write down the numbers** in the results table at the end of this guide.

## A. Battery voltage divider

**Why.** The battery voltage reaches the processor through a 150 kΩ / 10 kΩ divider with a 100 nF capacitor at the ADC pin. The divider scales 26.7 V down to 1.67 V. The capacitor filters noise and feeds the ADC's sample capacitor.

**Schematic.**
```
VBAT ── R1 150k ──┬── ADC
                  │
                R2 10k   C1 100n
                  │        │
                  0        0
```
- `V1` (`VPULSE`) between `VBAT` and `0`.
- `R1` 150k from `VBAT` to `ADC`; `R2` 10k from `ADC` to `0`; `C1` 100n from `ADC` to `0`.

**Run 1: step response (TRAN).**
- V1 pulse settings: initial value 0 V, pulsed value 26.7 V, delay 1 ms, rise time 1 µs, fall time 1 µs, pulse width 20 ms, period 40 ms.
- Analysis TRAN: time step `10u`, final time `10m`.
- Plot `V(ADC)` and `V(VBAT)`.

Check against section 7 A:

| Check | How to read it | Expected |
| --- | --- | --- |
| Settled pin voltage | Measure Max on `V(ADC)` | 1.669 V |
| Value one time constant after the step | Cursor at 1.938 ms (1 ms delay + 0.938 ms) | 1.055 V |
| Settled within 1 % | Cursor where `V(ADC)` reaches 1.652 V, minus the 1 ms delay | 4.32 ms |

Export as `reports/figures/sim_a_divider_step.png` and `reports/sim/sim_a_divider_step.csv`.

**Run 2: frequency response (AC).**
- Replace V1 by a `VSIN` (or give a `VDC` source an `ac` value of 1). AC magnitude 1.
- Analysis AC: 20 points per decade, start `1`, stop `100k`.
- Plot the magnitude of `V(ADC)`.

| Check | Expected |
| --- | --- |
| Gain at low frequency | -24.08 dB (that is 1/16) |
| Frequency where the gain is 3 dB lower (-27.09 dB) | 170 Hz |

Export as `sim_a_divider_ac.png` / `.csv`.

**What to notice.** The step takes about 4 ms to settle: that is fine for a battery voltage read a few times a second, and it means a motor-current spike lasting microseconds barely moves the reading.

## B. Sensor supply filter

**Why.** The two switching regulators run at 1.987 MHz (LT8641) and 1.5 MHz (TLV62569). The motion sensors get their own low-noise LDO; a 10 Ω resistor and 10 µF capacitor in front of it keep the MHz ripple out, because an LDO's own ripple rejection falls at high frequency.

**Schematic.**
```
5V ── R1 10 ──┬── LDO_IN
              │
            C1 10u
              │
              0
```
- `V1` (`VSIN` or `VDC` with AC magnitude 1) between `5V` and `0`.
- `R1` 10 from `5V` to `LDO_IN`; `C1` 10u from `LDO_IN` to `0`.

**Run (AC).** 10 points per decade, start `10`, stop `10M`. In KiCad's dialogs `M` means mega and `m` means milli; only in raw SPICE text (directives typed on the schematic) is mega written `Meg`. If in doubt, type `10000000`.

| Check | Expected |
| --- | --- |
| Corner (-3 dB) | 1592 Hz |
| Gain at 1.987 MHz (LT8641) | -61.9 dB |
| Gain at 1.5 MHz (TLV62569) | -59.5 dB |

Export as `sim_b_sensor_filter_ac.png` / `.csv`.

**Optional, to learn something real.** A real capacitor has a small series inductance (ESL) that stops it filtering at high frequency. Once the actual capacitor is chosen, add an inductor equal to its datasheet ESL in series with C1 and run again: the attenuation at MHz gets worse. This is why the capacitor goes right next to the LDO pin in the layout.

## C. Motor output edge (DShot600)

**Why.** Each motor output has a 220 Ω series resistor so that a shorted ESC wire cannot pull more than 15 mA from the processor pin (its limit is 20 mA). The resistor and the capacitance of the cable and ESC input slow the edges down. DShot600 sends one bit every 1.667 µs, so the edges must stay much faster than that.

**Schematic.**
```
OUT ── R1 220 ──┬── ESC_IN
                │
             C1 100p
                │
                0
```
- `V1` (`VPULSE`) between `OUT` and `0`: initial 0 V, pulsed 3.3 V, delay 0, rise time 1 ns, fall time 1 ns, pulse width 0.8 µs, period 1.667 µs. The rise time is set very short on purpose, so that the resistor and the load decide the edge.
- `R1` 220 from `OUT` to `ESC_IN`; `C1` 100p from `ESC_IN` to `0`. The 100 pF is an assumption for the cable plus the ESC input, chosen on the pessimistic side; the real value is measured with the scope after the board arrives.

**Run (TRAN).** Time step `1n`, final time `5u`. Plot `V(OUT)` and `V(ESC_IN)`.

| Check | How to read it | Expected |
| --- | --- | --- |
| 10 % to 90 % rise time | Cursor 1 where `V(ESC_IN)` crosses 0.33 V, cursor 2 where it crosses 2.97 V, read the time difference | 48.3 ns (2.9 % of a bit) |
| Settled within 1 % | Cursor where `V(ESC_IN)` reaches 3.267 V, from the start of the edge | 101 ns |

**Then use the tuning tool.** In the simulator choose Simulation → Add Tuned Value… (T), click C1 in the schematic, and slide it from about 20 pF to 500 pF while watching the edge. This shows how much margin the 220 Ω resistor leaves before edges start to eat into the bit.

Export as `sim_c_motor_edge.png` / `.csv`.

## Results table (fill in after each run)

| Circuit | Check | Expected | Simulated | Difference | Pass (within 2 %) |
| --- | --- | --- | --- | --- | --- |
| A | Settled pin voltage | 1.669 V | | | |
| A | Value at 1.938 ms | 1.055 V | | | |
| A | 1 % settling time | 4.32 ms | | | |
| A | Low-frequency gain | -24.08 dB | | | |
| A | -3 dB frequency | 170 Hz | | | |
| B | Corner frequency | 1592 Hz | | | |
| B | Gain at 1.987 MHz | -61.9 dB | | | |
| B | Gain at 1.5 MHz | -59.5 dB | | | |
| C | 10 to 90 % rise time | 48.3 ns | | | |
| C | 1 % settling time | 101 ns | | | |

When the CSV files are in `reports/sim/`, a script will read them and fill this comparison automatically, so the README numbers come from files rather than from hand-copied values.

## What these simulations do not cover

- The 5 V and 3.3 V regulators themselves: they are checked by the datasheet calculations (`reports/design_calcs.md`, sections 2 and 3) and then measured on the scope.
- Real parasitics (capacitor ESL, trace inductance, ESC input circuits): the simulations use ideal parts, and the bench measurements are the final check.
