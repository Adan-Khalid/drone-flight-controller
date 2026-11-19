# Learning notes

What every calculation in `scripts/design_calcs.py` does, why the design looks the way it does, what was rejected, and questions an interviewer could ask. Numbers quoted here come from `reports/design_calcs.md`; datasheet values are sourced in `configs/design_inputs.yaml` and `RESEARCH_LOG.md`.

## 1. Battery input range (`fcboard/battery.py`)

**Maths.** A LiPo pack of N cells in series has N times the cell voltage. The board must run from the emptiest pack it supports to the fullest: 2 x 3.0 V = 6.0 V up to 6 x 4.2 V = 25.2 V, and survive 6 x 4.45 V = 26.7 V for high-voltage cells.

**Design choice.** 2S to 6S covers small quads (2S to 4S) and larger frames (6S) with one board. Everything downstream (regulator rating, surge clamp, divider ratio) is sized from 26.7 V, not from the nominal 22.2 V.

**Rejected.** 3S to 6S only (common on hobby boards) would make the 5 V regulator's low-voltage limit easier but excludes small 2S test quads.

**Interview questions.**
1. *Why design for 26.7 V when a 6S pack is "22.2 V"?* 22.2 V is nominal (3.7 V per cell); a fully charged high-voltage cell sits at 4.45 V, so the board must withstand 26.7 V continuously.
2. *What happens at 6.0 V?* The 5 V regulator is close to dropout; it still regulates but skips switching cycles (see section 2).
3. *What protects against more than 26.7 V?* A 30 V stand-off TVS diode clamps surges to 48.4 V at 12.4 A, below the regulator's 65 V absolute maximum.

## 2. The 5 V buck regulator (`fcboard/buck.py`, LT8641)

**What a buck does.** A switch connects the input to an inductor for a fraction D of each period, then a second switch lets the inductor current freewheel. The average of the switched node is D x VIN, so VOUT ≈ D x VIN; the inductor and output capacitor filter the square wave into DC.

**Maths, step by step (LT8641 datasheet Rev B equation numbers):**
- Feedback (eq. 1): VOUT = VFB (1 + R1/R2) with VFB = 0.81 V. ADI's 1 MΩ / 191 kΩ gives 5.051 V. With the reference spread over temperature (0.79 to 0.822 V) and 1 % resistors the worst-case range is 4.844 to 5.213 V.
- Frequency (eq. 3 and Table 1): RT = 46.5/fSW - 5.2. The equation is within 4 % of the table (a test checks every row), so the final value is read from the table: 18.2 kΩ for 2 MHz, giving 1.987 MHz.
- Minimum on-time limit (eq. 4): at high input the duty cycle is small, so the on-time per cycle is short. fSW(MAX) = (VOUT + VSW(BOT)) / (tON(MIN) (VIN - VSW(TOP) + VSW(BOT))). With the maximum 50 ns on-time at 26.7 V this allows 3.92 MHz, so 2 MHz is safe.
- Minimum off-time limit (eq. 5): at low input the duty cycle approaches 100 %, and the switch needs at least 110 ns off each cycle. Below 6.81 V the regulator skips cycles to reach a higher effective duty cycle; it keeps regulating, only the frequency drops. This only happens with a nearly empty 2S pack.
- Inductor (eq. 6, 9, 7): first guess L = (VOUT + VSW(BOT))/fSW = 2.62 µH; ADI's own 2 MHz design uses 2.2 µH. Ripple ΔI = VOUT/(L fSW) (1 - VOUT/VIN(MAX)) is largest at the highest input: 0.937 A. Peak current = load + ΔI/2 = 2.47 A at 2 A and 3.97 A at 3.5 A, so the inductor's saturation current must exceed about 4 A.
- Current limit (eq. 8): available output = ILIM - ΔI/2 = 5.73 A with the minimum 6.2 A limit, comfortably above 3.5 A.
- Subharmonic oscillation (eq. 10): peak-current-mode control becomes unstable above 50 % duty unless the inductor is large enough. At 6.0 V in (duty 0.84) the minimum is 0.83 µH; 2.2 µH is fine.
- Output ripple: a triangle current of ΔI into a capacitor C at frequency f gives ΔV = ΔI/(8 f C) = 1.25 mV for 47 µF (2.5 mV if DC bias halves the capacitance). Real ripple is larger because of ESL and layout, which is why the oscilloscope measurement on the real board has the last word.
- Soft-start: the TR/SS pin sources 1.9 µA into 10 nF; the output follows the pin up to 0.81 V, so start-up takes C V / I = 4.26 ms (3.12 to 6.75 ms over the current spread).
- Heat: switch conduction loss I² (R_top D + R_bot (1 - D)) at 2 A is 0.26 to 0.39 W, a 10 to 16 °C rise at 40 °C/W. Switching loss is not included, so the real rise is higher and is measured on the bench.

**Design choice.** 2 MHz with ADI's published 5 V component values, so the design starts from a circuit ADI has built and tested. Compared with two cheaper TI parts at a 2 A load (report section 6) it runs coolest and has the most current margin. The LT8641's 65 V rating leaves 16.6 V of margin above the surge clamp.

**Rejected.**
- 1 MHz: no skipped cycles down to 6.0 V, but a larger inductor; the skipping region (6.0 to 6.8 V) is harmless.
- TPS54360 ($0.68): needs a Schottky catch diode that burns 0.76 to 1.14 W at 2 A, plus an 8.2 µH inductor; more heat and area next to the motion sensors.
- LMR36520 ($1.22): synchronous, but its switches are about twice as resistive (0.72 to 0.81 W at 2 A, up to 1.5 W at maximum resistance) and it is rated for only 2 A.
- LT8609S: 42 V rating sits below the 48.4 V surge clamp.

**Interview questions.**
1. *Why does the inductor ripple peak at the highest input voltage?* ΔI = VOUT/(L f) (1 - D): a smaller duty cycle at high input means a longer off-time during which the inductor current ramps down.
2. *What limits the switching frequency at high input?* The minimum on-time: at 26.7 V in, 5 V out, the duty cycle is about 19 %, so at very high frequency the on-time would be shorter than the 50 ns the switch can do.
3. *Why a feed-forward capacitor across the top feedback resistor?* With megaohm feedback resistors, the FB node is slow; 4.7 pF adds a zero that improves loop phase margin and transient response (the datasheet recommends 4.7 to 22 pF).

## 3. Power budget (`scripts/design_calcs.py`, section 3)

**Maths.** Sum the currents on each rail. The processor rail uses the STM32H743's datasheet current at 480 MHz with all peripherals on: 220 mA typical, 436 mA maximum at 85 °C junction (DS12110 Rev 7, Table 130). The SD card and LEDs get allowances (100 mA and 20 mA) until measured. The 5 V rail adds the CAN transceiver (70 mA maximum when driving the bus), one DroneCAN device (500 mA maximum by the DroneCAN hardware recommendations), and allowances for GPS, telemetry radio and receiver. Total: 1.47 A typical, 1.68 A worst case, under the 2 A design target and the LT8641's 3.5 A rating.

**Why counting 3.3 V current at full value on the 5 V rail is safe.** A buck's input current is IOUT VOUT / (VIN η). It is smaller than IOUT whenever the efficiency η is above VOUT/VIN = 66 %, which any working buck at this load exceeds.

**Interview questions.**
1. *Why use the 85 °C maximum, not the typical current?* Worst-case design: a hot board in summer, every peripheral clocked; typical values are for battery-life estimates, maximum values for sizing parts.
2. *Which numbers are not from datasheets yet?* The SD card, LED, GPS, radio and receiver allowances; they are replaced by measured or datasheet values when those parts are chosen.
3. *What happens on USB power alone?* A computer USB port cannot supply the full 5 V budget, so bench tests on USB run without peripherals.

## 4. Why the processor rail uses a buck, not an LDO (`fcboard/linear.py`)

**Maths.** A linear regulator burns (VIN - VOUT) x I. From 5.05 V to 3.3 V at 0.34 A that is 0.60 W; at 0.556 A it is 0.97 W. Junction temperature = ambient + P θJA. The AP2112K in SOT-23-5 has θJA = 184 °C/W, so at a 45 °C ambient it would reach 155 °C (typical load) and 224 °C (worst case), above its 150 °C limit. The TLV62569 buck's switch conduction loss at the same loads is 10 to 27 mW (θJA 188.2 °C/W gives 47 to 50 °C, switching losses excluded).

**Design choice.** TLV62569 (2 A, 1.5 MHz, SOT-23-5, $0.07) for the processor and SD card. Feedback 453 kΩ over 100 kΩ gives 3.318 V. The sensitive sensors keep their own low-noise LDO, which only carries 6.6 mA and burns 11.5 mW.

**Rejected.** AP2112K in a bigger package (SOT89-5, 120 °C/W) still rises about 70 °C at typical load; a second LT8641 for 3.3 V is expensive overkill.

**Interview questions.**
1. *Why is an LDO fine for the sensors but not for the processor?* Dissipation scales with current: 6.6 mA through 1.75 V is 11.5 mW, but 340 mA is 0.6 W.
2. *Why not run the sensors from the buck too?* Supply noise. The low-noise LDO rejects slow disturbances very well (95 dB at 1 kHz by the datasheet), but an LDO's rejection falls at high frequency, so the regulators' MHz switching ripple is removed by a ferrite bead and capacitors in front of the LDO. That filter is simulated in KiCad's simulator.
3. *Where did this problem show up?* In the power-budget calculation before any schematic existed, which is the point of doing the numbers first.

## 5. Battery voltage sensing (`fcboard/sensing.py`)

**Maths.**
- Ratio = (Rtop + Rbot)/Rbot. The processor's analog pins accept no positive injection current (DS12110 Table 59), so the pin must stay at or below 3.3 V even when the surge clamp holds the input at 48.4 V: ratio ≥ 48.4/3.3 = 14.7. 150 kΩ / 10 kΩ gives 16.0, so 26.7 V reads 1.67 V and 48.4 V reads 3.03 V.
- The ADC sees the Thevenin resistance 150k ∥ 10k = 9.38 kΩ, under its 50 kΩ maximum.
- A 100 nF capacitor at the pin forms a 170 Hz low-pass filter and acts as a charge reservoir: when the 4 pF sample capacitor connects, the worst-case error is 4 pF / 100 nF = 40 ppm, below one 12-bit step (244 ppm).
- Resolution: 3.3 V / 4096 x 16 = 12.9 mV of battery voltage per step.
- In ArduPilot the ratio goes into `BATT_VOLT_MULT` (pin voltage times multiplier).

**Rejected.** 10 kΩ / 1 kΩ (ratio 11): the pin would reach 4.4 V at the surge clamp, and the divider would drain 2.4 mA from the battery.

**Interview questions.**
1. *Why is the capacitor at the ADC pin important?* It supplies the charge for the sample capacitor, so the high source resistance does not cause a sampling error, and it filters noise.
2. *Why not a much larger ratio?* Resolution: every doubling of the ratio halves the voltage per ADC step.
3. *What does the divider cost in battery life?* 167 µA at 26.7 V, negligible next to a flight current of tens of amps.

## 6. Trace widths (`fcboard/traces.py`)

**Maths.** IPC-2221 (as used by KiCad's PCB calculator): I = k ΔT^0.44 A^0.725, A in square mils, k = 0.048 for outer and 0.024 for inner layers. Solving for width at a 10 °C rise: 2 A needs 0.78 mm on a 35 µm outer layer but 4.68 mm on a 15.2 µm inner layer (JLCPCB's default 4-layer stack-up).

**Design choice.** Power is routed on the outer layers or as copper pours; the inner layers carry the ground plane and low-current signals.

**Interview questions.**
1. *Why do inner layers need wider traces?* They are thinner in this stack-up (0.5 oz) and cool worse (surrounded by FR-4), hence the lower k.
2. *Is IPC-2221 exact?* No, it is an empirical fit to measured traces. It is used here for first sizing, and the regulator and trace temperatures are checked on the bench.
3. *What else limits a power trace besides heating?* Voltage drop and inductance in the switching loop, which matter more than heating for the regulator layout.

## 7. DShot600 timing

One bit lasts 1/600 kHz = 1.667 µs and a 16-bit frame 26.67 µs. The motor-signal edges must settle in a small fraction of a bit; this is simulated in KiCad's simulator with the output resistor and the cable to the ESC.

**Interview question.** *Why does DShot need DMA?* Each bit is a precisely timed pulse width; a timer fed by DMA produces the 16 pulses with no CPU jitter, which is why the pin plan must give every motor timer a DMA stream.

## 8. Sensor supply RC filter (`fcboard/rc.py`)

**Maths.** A resistor R feeding a capacitor C is a first-order low-pass filter with corner fc = 1/(2πRC). With 10 Ω and 10 µF, fc = 1592 Hz. Above the corner the gain falls 20 dB per decade: |H| = 1/sqrt(1 + (f/fc)^2), so at 1.987 MHz the gain is -61.9 dB and at 1.5 MHz -59.5 dB. The DC cost is the drop R x I = 10 Ω x 6.6 mA = 66 mV.

**Design choice.** A resistor instead of a ferrite bead: the sensor current is tiny, so the drop is harmless, and a resistor's behaviour is exactly known, while a bead's impedance depends on frequency and current. Checked in KiCad's simulator (AC analysis).

**Interview questions.**
1. *Why not use the same RC filter for the processor?* At 0.34 A a 10 Ω resistor would drop 3.4 V; filters with resistors only work for small currents.
2. *Why will the real attenuation be lower than 60 dB?* The capacitor's series inductance (ESL) makes its impedance rise again at MHz frequencies, and the layout adds inductance; so the capacitor sits right at the LDO pin.
3. *What does the LDO add?* High rejection of low-frequency disturbances (95 dB at 1 kHz by the datasheet), which the RC filter cannot provide well.

## 9. Motor output series resistor

**Maths.** The processor pin may sink at most 20 mA (DS12110). A short from a 3.3 V output to ground through R draws 3.3/R, so R must be at least 165 Ω; 220 Ω gives 15 mA. The resistor and the load capacitance C form an RC edge: the 10 to 90 % rise time is ln(9) RC ≈ 2.2 RC = 48.3 ns for an assumed 100 pF, and the edge settles within 1 % after 4.6 RC = 101 ns. A DShot600 bit lasts 1667 ns, so the edge uses 2.9 % of it.

**Design choice.** 220 Ω protects the pin without hurting the signal. The 100 pF load is a pessimistic assumption that is replaced by a scope measurement with the real ESC.

**Interview questions.**
1. *Why protect the output pin at all?* ESC wires get pinched and shorted in crashes; an unprotected pin can be damaged by a short.
2. *What else does the resistor do?* It damps ringing on the wire, because it adds resistance in series with the wire's inductance and capacitance.
3. *How would you know the resistor is too big?* The edges would take a noticeable fraction of a bit; the KiCad tuning tool shows how far the load can grow before that happens.

## 10. Pin plan and DMA (`docs/PIN_PLAN.md`, `scripts/check_hwdef.py`)

**The problem.** Each peripheral on the STM32H743 can only use certain pins (alternate functions), and fast peripherals need DMA: a hardware unit that moves data between memory and the peripheral without the CPU. DShot needs DMA because every motor command is 16 precisely timed pulses produced by a timer; bidirectional DShot also needs DMA to capture the ESC's reply on the same pin. The H743 has two DMA controllers with 8 streams each, so 16 streams are shared by the IMU buses, motor timers, UARTs and ADC.

**How ArduPilot handles it.** The board file (`hwdef.dat`) lists pins and functions; ArduPilot's `dma_resolver.py` assigns streams. `DMA_NOSHARE` keeps the IMU buses and motor timers on their own streams; UART transmitters may share. If streams run out, the resolver does not stop the build: it writes "can't be resolved for DMA" into the generated `hwdef.h`, which is why `scripts/check_hwdef.py` searches for that line.

**Design choice.** Start from the Matek H743 board files (same chip and package, flying with ArduPilot) instead of a blank sheet, change only what this board needs, and prove the result with ArduPilot's own processor at a pinned commit. Result: every peripheral has DMA; each motor timer's update and capture requests share one stream that nothing else uses.

**Interview questions.**
1. *Why can't any pin drive any motor?* A motor output must be a timer channel, and the timer needs a free DMA stream for DShot; only certain pins connect to timer channels.
2. *Why put the two IMUs on separate SPI buses?* So that a fault or slow transfer on one bus cannot stall the other sensor, and each bus gets its own DMA streams.
3. *What does CubeMX add if ArduPilot already checks DMA?* It checks the pin and peripheral choices and the clock tree in ST's own tool; ArduPilot's check covers the DMA plan.

## 11. Schematic from a circuit description (`hardware/gen/circuit.py`, `build_schematic.py`, `check_netlist.py`)

**The problem.** A schematic drawn by hand is hard to review in a pull request and easy to get subtly wrong: a label one grid step off a pin looks connected but is not.

**How it works here.** `circuit.py` lists every part with its value, footprint, LCSC number and a map from pin number to net name. `build_schematic.py` turns that into four KiCad sheets (power, processor, sensors, connectors): each connected pin gets a short wire and a net label, a power symbol, or a no-connect flag, and parts are grouped in titled boxes by function. Two checks follow. KiCad's electrical rules check (ERC) catches problems such as two outputs driving one net or an input left floating. Then `check_netlist.py` exports KiCad's own netlist and compares every pin with `circuit.py`, which catches what ERC cannot see: a pin on a valid but wrong net.

**Design choices.** Labels on every pin instead of drawn wires: the layout is generated, so drawn wires would cross and bend unpredictably, while named nets read the same at any size. The BMI088 symbol is KiCad's with SDO1 and SDO2 changed to tri-state, because Bosch's SPI diagram joins them on one MISO line; with the stock "output" type ERC reports a false conflict. The DPS368's SDO pin is "passive" because on this board it only sets the I2C address.

**Alternatives rejected.** Drawing by hand in KiCad (not reproducible, slow to review); a netlist with no schematic (no readable drawing for reviewers or for the Altium redraw).

**Interview questions.**
1. *What does ERC check, and what does it miss?* Pin-type conflicts (output to output, undriven inputs, unconnected pins). It cannot know that a correctly typed pin is on the wrong net, which is why the netlist is also compared pin by pin.
2. *What is a PWR_FLAG for?* It tells ERC that a net is driven by something outside the schematic (a battery connector, a regulator output pin typed as passive), so power inputs on that net are not reported as undriven.
3. *Why tri-state rather than switching the check off?* The pin type then describes the real chip: each SDO lets go of the line while its chip select is high, so a genuine conflict elsewhere would still be caught.

## 12. Placement (`hardware/gen/build_board.py`)

**The problem.** 130 parts on 36 x 36 mm, inside a 30.5 mm mounting pattern, with five connectors and a microSD socket. The courtyards (each part's keep-clear outline) cover most of both sides, and what is left must carry about 400 connections.

**How it works here.** Large parts are placed by hand in a table: processor in the middle of the top, the 5 V regulator along the west edge next to the battery connector, connectors on the edges with their openings outwards, IMUs and barometer underneath near the centre, microSD underneath on the east edge. Every other part is placed by a greedy search: starting from the pins it connects to (or the pin named for a decoupling capacitor), it spirals outwards in 0.25 mm steps and takes the first spot where its courtyard touches nothing, stays inside the outline and keeps clear of the M3 hardware and of through-hole pegs coming through from the other side.

**Design choices.** Decoupling capacitors first, each aimed at its own supply pin, because their benefit falls with the length of the loop from capacitor to pin and back through ground. IMUs near the board centre, where the board flexes least and rotation adds the least acceleration (a = ω²r grows with distance r from the centre). The switching regulator in a corner, away from the sensors.

**Alternatives rejected.** Placing every part by hand (hours per iteration, and every later change means moving parts again); KiCad's built-in spreading tools (they spread parts apart but do not place them next to the pins they serve).

**Interview questions.**
1. *Why must a decoupling capacitor sit close to its pin?* The fast current a chip draws when it switches comes from the nearest charge store; the loop's inductance, which grows with the loop's length and area, limits how fast the capacitor can supply it.
2. *What is a courtyard?* The area a part needs around its pads for assembly and rework; overlapping courtyards are a DRC error.
3. *Why do the USB connector's pegs matter for the bottom side?* They are through-hole: they come out under the board, so nothing can be placed there.

## 13. Ground fan-out and routing (`hardware/gen/route_board.py`, `finish_board.py`)

**The problem.** Every part needs a ground connection with a short return path, and the remaining nets must be routed on four layers without breaking the clearance rules.

**How it works here.** The stack-up is signal, ground plane, mixed (signals plus a 5 V pour), signal. Before routing, a script gives every surface ground pad a short track and a via down to the solid ground plane on inner layer 1, searching outwards from the pad (inwards, under the body, for the processor's ground pins); 3.3 V pads get the same escape vias. Freerouting then routes everything except ground through KiCad's Specctra export. After import, ground is poured on both outer layers, 5 V on inner layer 2 (it carries up to 2 A to the connectors), and local pours are added on the battery-side power nets.

**Design choices.** A solid ground plane right under the top layer gives each signal a return path directly beneath it, which keeps loops small and emissions low. Ground is left out of the autorouter because the plane already connects it; routing it as tracks would waste the space the signals need. A 0.3 mm keepout ring inside the outline keeps routes clear of the edge, because the router does not know KiCad's edge rule.

**What went wrong first, and what fixed it.** The first full route left about half the connections open. Four causes, each found by looking at the board, not at the router's score: (1) Freerouting's fan-out pre-pass put an escape via 2.5 to 4.5 mm from every surface pin, which filled the board, so it is switched off and only ground and 3.3 V get escape vias, placed by my own script; (2) 0.127 mm rules and 0.5 mm vias were looser than needed, so the rules moved to 0.1 mm and 0.45 / 0.2 mm vias, still inside JLCPCB's published limits and at no extra cost; (3) the inner signal layer was nearly empty while pins could not reach it, because decoupling capacitors stood shoulder to shoulder against the processor's pins: a 1.2 mm escape band now keeps small parts back from the processor, so each pin has room for a short trace and a via; (4) the router's automatic neck-down drew 0.075 mm tracks, under the 0.09 mm limit, so it is off. The router's command-line build also crashed after its first pass (a packaging bug), so the Java build runs instead.

**Alternatives rejected.** Routing everything by hand (the right choice for a production board, too slow for a first full layout); a 6-layer board (more routing room, but a new quote and more cost for a first prototype).

**Interview questions.**
1. *Where does the return current of a fast signal flow?* In the plane directly under the trace, because that path has the lowest inductance; a gap in the plane forces a detour and a bigger loop.
2. *Why one via per ground pad instead of shared vias?* Each shared via adds inductance to every pad that uses it; separate vias keep each part's ground path short.
3. *What does DRC prove, and what not?* Clearances, widths, connectivity and that the board matches the schematic. It says nothing about signal quality, heat or whether the design works; that needs simulation and the bench.
4. *The autorouter left connections open, but the inner layer was empty. Why?* Escape, not capacity: the pins had no room for a trace and via before the next part. Move parts back or add escape vias, then route again.
