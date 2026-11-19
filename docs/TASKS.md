# Tasks

Small ordered tasks. Each ends with something that can be looked at and checked. I stop after each group, review the output, and only then move on.

## Set-up

- [ ] Ask PCAA or the NUST department about rules 33 and 41 (design facility, importing drone parts) before any order
- [ ] Install KiCad 10.0.8 and STM32CubeMX 6.18.1; record versions in `reports/env/tool_versions.txt`
- [ ] WSL2 Ubuntu with the ArduPilot build tools; build the existing `MatekH743` target once to prove the toolchain
- [ ] Mission Planner 1.3.83; run ArduPilot SITL once to learn the ground station before hardware exists
- [ ] Python environment (uv) for calculations and log analysis; CI with ruff, pytest and `kicad-cli` ERC/DRC

## Design on paper

- [ ] `docs/REQUIREMENTS.md` from the plan, with a block diagram figure
- [ ] Check the pin plan in STM32CubeMX (steps in `docs/PIN_PLAN.md`); save the `.ioc` and a pinout picture
- [x] Pin plan drafted from ArduPilot's MatekH743 board files: `docs/PIN_PLAN.md`
- [x] Board files drafted (`firmware/hwdef/DroneFC-H743/`) and checked with ArduPilot's own processor: `reports/firmware/hwdef_check.md` (pass)
- [ ] Compile ArduPilot for the new board in WSL2; save `features.txt`
- [x] Regulator, power budget, battery divider and trace calculations: `reports/design_calcs.md`
- [ ] Crystal load capacitors (once the crystal is chosen) and USB pair impedance (JLCPCB impedance calculator)
- [x] Step-by-step guide for the simulations: `docs/SIMULATION_GUIDE.md` (expected values in `reports/design_calcs.md`, section 7)
- [ ] KiCad simulator test circuits in `sim/`: sensor supply filter (AC), battery divider with the ADC sample capacitor (transient), DShot600 edge into a cable (transient); plots exported to `reports/figures/`
- [ ] Final BOM with LCSC numbers and stock check; price every part

## Schematic and layout (KiCad)

- [ ] Schematic sheet 1: power (input protection, buck, power path, LDOs)
- [ ] Schematic sheet 2: processor (power pins, VCAP, crystal, BOOT0, reset, SWD, USB)
- [ ] Schematic sheet 3: sensors and SD card
- [ ] Schematic sheet 4: connectors, outputs, LEDs
- [ ] ERC clean; schematic review against the checklist
- [ ] Board outline 36 x 36 mm, 30.5 mm holes, 4-layer stack-up from JLCPCB, design rules from JLCPCB's limits
- [ ] Placement: sensors at the centre, regulator at the edge, connectors at the edges
- [ ] Routing: power, USB pair, SDMMC, SPI, outputs; ground pours and stitching vias
- [ ] DRC clean; layout review; 3D render
- [ ] Fabrication outputs by script: Gerbers, drill, BOM, placement file, schematic PDF, STEP

## Order and redraw

- [ ] Upload to JLCPCB, check the real price and the DFM report, order (I pay)
- [ ] Altium Student Lab licence; redraw schematic and layout in Altium while the boards ship; side-by-side figure

## Bring-up and tests

- [ ] Visual check, rail resistance, first power with current limit, rail voltages
- [ ] Ripple and load step on the scope next to the calculated values
- [ ] DFU, bootloader, ArduPilot, Mission Planner
- [ ] Sensor checks and rest-noise analysis
- [ ] Battery voltage accuracy; port tests; logging test
- [ ] Props-off motor test with DShot and RPM telemetry
- [ ] Register the test drone; hover test in legal airspace; vibration and notch analysis

## Release

- [ ] README, test report, figures, social preview
- [ ] LinkedIn carousel and text
- [ ] Release v1.0.0 after review
