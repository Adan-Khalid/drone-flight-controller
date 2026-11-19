# Research log

Background research for a drone flight controller board that runs ArduPilot, compiled on 15 Nov 2026. Every link was accessed that day.

**How to read the check notes.** "Opened" means the page or PDF was read for this log. "Snippet" means the detail comes from a search result and must not be relied on until the source is opened. "Computed" means the number was worked out from opened values. "Quote" means a price or stock figure read from a live distributor or fab page on 15 Nov 2026; these change daily and are re-checked before ordering.

## 1. Problem and users

- **What a flight controller does.** It reads gyroscopes and accelerometers at kilohertz rates, a barometer for height and usually a GPS and compass, runs an estimator (ArduPilot uses an extended Kalman filter) and a control loop, and sends a speed command to each motor's ESC. Everything else on a drone plugs into it: radio receiver, telemetry radio, GPS, battery monitor, companion computer.
- **Why the board design matters.** ArduPilot's own guidance is that accelerometer readings are combined with barometer and GPS data, and that "with excessive vibrations, the estimate can be thrown off". Vibration levels "below 30m/s/s are normally acceptable", above 30 "may have problems" and above 60 "nearly always have problems with position or altitude hold" [A1]. Sensor placement, supply noise and mounting are board-level decisions that decide where a design lands on that scale.
- **Users of this work.** Engineers and recruiters judging hardware design skill, and my later drone projects that need real hardware (trajectory tracking, sensor fusion, drone audition).

## 2. Tools

| Tool | Version and facts | Source | Check |
| --- | --- | --- | --- |
| KiCad | 10.0.8 is the current version (release post 30 Oct 2026). Windows installer `kicad-10.0.8-x86_64.exe`, 969.1 MB; no smaller installer without libraries for 10.x. Code GPL v3 or later; libraries CC-BY-SA 4.0 with an exception for designs and generated files. Windows 10 or 11, up to 10 GB disk. Includes ngspice | [T1], [T2], [T3], [T4] | Opened |
| `kicad-cli` (10.0) | `sch erc`, `pcb drc` (JSON report), `pcb export gerbers`, `drill`, `pos`, `step`, `pdf`, `sch export bom`, `sch export pdf`, `pcb render` (raytraced PNG), `jobset run` | [T5] | Opened |
| LTspice (installed, not used: simulation is done in KiCad) | 26.1.1 for Windows 10/11 x64; "Fast, Free, Unlimited". Installer size not shown on the page. Command line: `-b` batch mode with `-run` or `-netlist`, `-ascii` for text output | [T6], [T7] | Opened |
| Altium Designer | 26.11.1 (14 Oct 2026). Web installer 29.2 MB (download behind sign-in). Windows 11 64-bit only; minimum i5, 4 GB RAM, 10 GB disk | [T8], [T9], [T10] | Opened |
| Altium Student Lab | "Free access to Altium Designer". Licence "valid for 1 year and can be renewed yearly as long as you remain a student"; needs a school email | [T11], [T12] | Opened |
| EasyEDA Pro | Free; Windows installer version 3.2.209; imports KiCad and Altium, exports Altium. Not used as the design tool here | [T13] | Opened |
| STM32CubeMX | 6.18.1; ST licence SLA0048; download needs a light ST registration. Size not shown | [T14] | Opened |
| STM32CubeProgrammer | 2.23.0; size not shown | [T15] | Opened |
| Mission Planner | 1.3.83, Windows `.msi` of 119,841,133 bytes | [T16] | Opened |
| QGroundControl | 5.1.5, Windows installer 135,445,404 bytes | [T17] | Opened |
| ArduPilot build on Windows | "New developers should use WSL"; keep the source inside the WSL file system; install with `install-prereqs-ubuntu.sh -y`; uploading from WSL2 needs Python on the Windows side; usbipd does not work for the bootloader | [F2], [F3] | Opened |
| JLCPCB helpers for KiCad | JLCPCB's own KiCad guide uses KiCad's built-in plot dialogs and names no plug-in or rules file. Community tools: Fabrication Toolkit (Apache-2.0) and kicad-jlcpcb-tools (MIT, KiCad 7 to 10), which assigns LCSC part numbers and writes BOM and placement files | [J4], [J5], [J6] | Opened |

## 3. Processor and firmware

### 3.1 ArduPilot's requirements for a new board

| Fact | Source | Check |
| --- | --- | --- |
| New boards are added with `hwdef.dat` (firmware) and `hwdef-bl.dat` (bootloader) in `libraries/AP_HAL_ChibiOS/hwdef/<Board>`; board name 13 characters or less | [F1] | Opened |
| MCUs already supported include STM32F405, F427, F745, F765, F777, H743 and H757; the MCU needs at least 1 MB of flash; crystals are "normally 8Mhz or 24Mhz" | [F1] | Opened |
| A board ID is reserved through `Tools/AP_Bootloader/board_types.txt` | [F1], [F9] | Opened |
| First flash: hold BOOT0 high at power-on, then `dfu-util -a 0 --dfuse-address 0x08000000 -D <board>_bl.bin`; later uploads with `./waf copter --upload` | [F4], [F1] | Opened |
| The official build may reject "Hobby, personal, student, or educational projects", so this board definition stays in this repo (and a personal fork) | [F1] | Opened |
| On 1 MB boards (for example MatekF405) the Copter build drops scripting, in-flight FFT, DroneCAN drivers, optical flow, mount and IMU temperature calibration; MatekH743 (2 MB) keeps them | [F5], [F6] | Opened |
| DShot needs one `TIMn_UP` DMA stream per output timer unless a pin is marked `NODMA`; bidirectional DShot (`BIDIR`) also needs a `TIMn_CHx` DMA for input capture and does not work on complementary (CHxN) channels; all outputs on one timer share one protocol | [F7], [F8], [F9] | Opened (from `chibios_hwdef.py` and the MatekH743 files) |
| Harmonic notch filtering: "virtually all vibrations originate from the motor's rotational frequency"; ESC RPM telemetry is "generally the best source"; the FFT mode needs an F7 or H7 class board | [F10] | Opened |
| Bidirectional DShot needs ESC firmware BLHeli32 32.7+, BLHeli_S 16.73+ (Bluejay or JESC) or AM32; DShot300 or 600 preferred; DShot600 "recommended for most vehicles" | [F8], [F11] | Opened |
| Autopilot outputs are "usually only at 3.3V levels"; the docs suggest buffers where 5 V signalling is needed and keeping signal wires away from power wires | [F11], [F12] | Opened |
| Mount the board "close to the center of gravity" | [A2] | Opened |

### 3.2 Microcontroller options

| | STM32H743VIT6 | STM32H723VGT6 | STM32F405RGT6 | Source |
| --- | --- | --- | --- | --- |
| Core, clock | Cortex-M7, 480 MHz | Cortex-M7, 550 MHz | Cortex-M4, 168 MHz | [M1], [M2], [M3] |
| Flash, RAM | 2 MB, 1 MB | 1 MB, 564 KB | 1 MB, 192 KB + 4 KB | same |
| Package | LQFP100, 14 x 14 mm, 82 I/O | LQFP100, 14 x 14 mm | LQFP64, 10 x 10 mm | same |
| SD card interface | 2x SDMMC | 2x SD/SDIO/MMC | 1x SDIO | same |
| USB | 2x OTG (one full-speed, one high/full-speed) | 1x OTG | FS OTG, HS OTG with ULPI | same |
| Supply, temperature | 1.62 to 3.6 V, -40 to 85 °C | 1.62 to 3.6 V, -40 to 85 °C | 1.8 to 3.6 V, -40 to 85 °C | same |
| Typical run current | 110 mA at 480 MHz with peripherals off, 220 mA with all on (DS12110 Rev 7, an older revision on a mirror; ST's own PDF did not open) | not checked | not checked | [M4] |
| Status | Active, 10-year longevity from 1 Jan 2026 | Active | Active (some variants NRND) | same |
| ArduPilot features | full (2 MB) | 1 MB: reduced | 1 MB: reduced | [F5], [F6] |
| Stock and price, 15 Nov 2026 | `H743VIT6TR` C5271084: LCSC 802 at $12.212; JLCPCB 980 at $12.0959 (Extended). Tray part C114409: LCSC 0 | 0 in stock at LCSC and JLCPCB | JLCPCB pre-order, about 11 days | [M5], [M6] (quote) |

ST budgetary prices per 10k: H743VIT6 US$6.6133, H723VGT6 US$4.9283, F405RGT6 US$5.3148 [M1], [M2], [M3].

**Choice:** STM32H743VIT6. It keeps the full ArduPilot feature set, it is the processor in Pixhawk 6C and many existing ArduPilot boards (so reference pin maps exist), it is in stock for assembly, and the LQFP100 package can be inspected and reworked by hand.

### 3.3 Pixhawk open standards

| Document | What it covers | Source |
| --- | --- | --- |
| DS-009 Connector Standard | JST GH connectors (JST SH for debug). TELEM 6-pin: +5V, TX, RX, CTS, RTS, GND. GPS 6-pin: VCC, TX, RX, SCL, SDA, GND. CAN 4-pin: VCC, CAN_H, CAN_L, GND. I2C with 1.5 kΩ pull-ups on the autopilot. Power 6-pin: two VCC, CURRENT, VOLTAGE, two GND; CURRENT 0 to 3.3 V for 0 to 60 A | [P1] |
| DS-012 (FMUv6X) and DS-018 (FMUv6C) | STM32H7 autopilots; v6X uses vibration-isolated IMUs; v6C gives an STM32H743 pin map including a heater pin | [P1] |
| Licence | "Copyright (c) 2020, Pixhawk Special Interests Group (SIG). All rights reserved." Redistribution only unmodified; the Pixhawk name needs an adopter agreement. So this board follows the connector pinouts but is not called a Pixhawk | [P1] |
| Reference schematics | `pixhawk/Hardware`: FMUv1 to v4 under CC BY-SA 3 (derived boards must be open); FMUv5 pinout only; no v6; last updated 2022 | [P2] |

Hobby mounting holes are a de facto size, not a formal standard: Holybro Kakute H7 v2 is a 35 x 35 mm board with "30.5 x 30.5mm/Φ4mm hole with Φ3mm Grommets"; the Mini uses 20 x 20 mm [P3].

## 4. Sensors

Datasheet values below were extracted from the PDFs listed; the headline ICM-45686 and BMI088 figures were re-checked on the makers' product pages. Some TDK datasheets were only reachable as distributor copies of older revisions; the current revisions are re-read before layout. Every part is a JLCPCB Extended part.

### 4.1 Motion sensors (IMUs)

| Part | Gyro / accel noise density | Ranges | Max output rate | Package, bus | ArduPilot driver | Stock, 15 Nov 2026 | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TDK ICM-45686 | 3.8 mdps/√Hz; 70 µg/√Hz | up to ±4000 dps, ±32 g | 6400 Hz (low-noise mode) | LGA-14 2.5 x 3.0 x 0.81 mm; SPI 24 MHz, I2C, I3C | Invensensev3 | C22459454, $10.3136, 1,072 | [S1], [S2] product page re-checked |
| Bosch BMI088 | 0.014 °/s/√Hz; 160 (X, Y) / 190 (Z) µg/√Hz at ±3 g | ±3 to ±24 g, ±125 to ±2000 °/s | accel 1600 Hz, gyro 2000 Hz | LGA-16 3.0 x 4.5 x 0.95 mm; SPI 10 MHz, I2C | BMI088 | C194919, $6.3937, 1,301 | [S3], [S4] ranges re-checked |
| TDK ICM-42688-P | 0.0028 º/s/√Hz; 65 / 70 µg/√Hz | ±16 g, ±2000 º/s | 32 kHz | LGA-14 2.5 x 3 x 0.91 mm | Invensensev3 | 0 in stock at LCSC | [S5], [S6] |
| Bosch BMI270 | 0.007 dps/√Hz (performance mode); 0.16 mg/√Hz | ±16 g, ±2000 dps | gyro 6400 Hz | LGA-14 2.5 x 3 x 0.83 mm | BMI270 | C2836813, $2.4348, 7,204 | [S7] |
| TDK ICM-42670-P | 0.007 º/s/√Hz; 100 µg/√Hz | ±16 g, ±2000 º/s | 1600 Hz | LGA-14 2.5 x 3 x 0.76 mm | Invensensev3 | C3288646, $2.1729, 3,241 | [S8] |

Which boards carry which motion sensors (from ArduPilot board files and PX4 pages): Pixhawk 6X uses ICM-42688 + BMI088 + ICM-42670 (Rev 8: three ICM-45686, vibration-isolated and heated, on separate buses); Pixhawk 6C uses ICM-42688 + BMI055; Matek H743 uses ICM-42688 + ICM-42605 [S9], [S10].

Why two different sensors: ArduPilot runs one EKF core per IMU and uses the core whose data is most consistent [S11]. Using two different makers' designs is common practice on the boards above; the reasoning that two MEMS designs are less likely to share a resonance or failure is my inference, not a sourced fact.

### 4.2 Barometers

| Part | Relative accuracy | Noise | Package | ArduPilot driver | Status and stock | Source |
| --- | --- | --- | --- | --- | --- | --- |
| Infineon DPS368 | ±6 Pa (±0.5 m) | 1.0 / 0.35 / 0.2 Pa RMS at 2x / 16x / 64x oversampling | VLGA-8 2.0 x 2.5 x 1.1 mm, IPx8 | DPS310 driver | C3232508, $4.4253, 10,858 | [S12], [S13] |
| TE MS5611-01BA03 | ±1.5 mbar absolute at 25 °C | no RMS figure; 0.012 mbar resolution at OSR 4096 | QFN 5.0 x 3.0 x 1.0 mm | MS5611 | Active; C15639, $6.1944, 4,229 | [S14] |
| Bosch BMP390 | ±3 Pa (±0.25 m) | 0.9 Pa | LGA-10 2 x 2 mm | BMP388 driver | LCSC "stop_product", 0 in stock | [S15] |
| Bosch BMP388 | ±8 Pa | 1.2 Pa | LGA-10 2 x 2 mm | BMP388 | missing from Bosch overview; distributor says obsolete | [S15] |
| Infineon DPS310, Goertek SPL06-001 | ±6 Pa | down to 0.2 / 0.3 Pa RMS | LGA-8 | DPS310, SPL06 | obsolete or stopped, 0 in stock | [S12], [S16] |
| TDK ICP-20100 | ±1 Pa | 0.5 Pa RMS | LGA-10 2 x 2 mm | ICP201XX | TDK lists end of life | [S17] |

### 4.3 Compass

ArduPilot advises an external compass (usually combined with the GPS on a mast), away from the power distribution board and high-current wires, because those create large magnetic fields; a board's onboard compass is usually disabled in favour of the external one [S18], [S9]. This board therefore has no onboard compass; the GPS connector carries I2C for the external one. Candidates for an optional bench-test footprint: MEMSIC MMC5983MA (±8 G, 0.4 mG RMS, C404329, $2.0097) and Isentek IST8310 (C2683055, $3.1292) [S19].

### 4.4 Flight log storage

| Option | Facts | Source |
| --- | --- | --- |
| microSD on 4-bit SDMMC | File logging with no fixed size limit; used by Pixhawk 6X and 6C (SDMMC2) and MatekH743 (SDMMC1) | [S9], [S20] |
| Winbond W25N01GV, 1 Gbit SPI NAND | 104 MHz SPI, page program 250 µs typical; ArduPilot driver AP_Logger_W25NXX; ArduPilot says flash logs on boards without SD are "typically 16MB" and work as a circular buffer. An open ArduPilot issue (#26900) reports broken logs on W25N01/W25N02 chips | [S21], [S20], [S22] |

Choice: microSD. A 2026 student H743 board reported its SD card "Not functional" [O9], so the SDMMC wiring (pull-ups, card detect, short matched traces) gets its own review item.

## 5. Power and interfaces

| Topic | Facts | Source | Check |
| --- | --- | --- | --- |
| Battery range | LiPo cell 3.7 V nominal, 4.2 V full, 3.0 V safe minimum; high-voltage cells charge to 4.35 or 4.45 V. 2S to 6S therefore spans 6.0 to 25.2 V, or 26.7 V for 6S high-voltage packs | [W1] | Opened; range computed |
| 5 V regulator: LT8641 | 3 to 65 V in, 3.5 A continuous (5 A peak), 200 kHz to 3 MHz, 2.5 µA quiescent, 3 x 4 mm QFN. Official LTspice model and a demo circuit "5.5-65V to 5V @ 3.5A". ADI $6.57 per 1k; JLCPCB C462660 $11.14, 3,016 in stock | [W2], [W3] | Opened; quote |
| 5 V regulator: LT8609S | 3 to 42 V, 2 A (3 A peak), LTspice model and 5 V demo; JLCPCB C580305 $11.04, only 133 in stock | [W4], [W3] | Opened; quote |
| 5 V regulator, low-cost alternative: TPS54360 | 4.5 to 60 V, 3.5 A, 146 µA; PSpice and TINA models only (no LTspice); JLCPCB C44377 $0.68 | [W5], [W3] | Opened; quote |
| 3.3 V for the MCU: AP2112K-3.3 | 2.5 to 6.0 V in, 600 mA, 50 µVRMS (10 Hz to 100 kHz), 250 mV dropout at 600 mA; C51118 $0.1667 | [W6], [W3] | Opened; quote |
| 3.3 V for the motion sensors: TPS7A2033 | 300 mA, 7 µVRMS (10 Hz to 100 kHz), 95 dB PSRR at 1 kHz; C2862740 $0.2042 | [W7], [W3] | Opened; quote |
| USB and battery 5 V power path: TPS2116 | 1.6 to 5.5 V, 2.5 A, 40 mΩ, priority mux; C3235557 $0.38 | [W8], [W3] | Opened; quote |
| Input surge: SMBJ30A | 30 V stand-off, 33.3 V breakdown, 48.4 V clamp at 12.4 A, 600 W; C83851 $0.1267. Clamp is below the LT8641's 65 V rating and above the LT8609S's 42 V (computed) | [W3] | Opened (JLCPCB listing; maker page blocked); computed |
| Reverse battery: LM74700-Q1 ideal-diode controller with an N-MOSFET | 3.2 to 65 V, -65 V reverse; C2941042 $2.73. LTC4359 has an LTspice model but costs $12.64 with 132 in stock | [W9], [W10], [W3] | Opened; quote |
| USB | USBLC6-2SC6 ESD array (IEC 61000-4-2 level 4), C7519 $0.157; USB-C receptacle TYPE-C-31-M-12, C165948 $0.1869 | [W11], [W3] | Opened; quote |
| Battery monitor | ArduPilot `BATT_MONITOR` 4 = analog voltage and current (standard power modules); 21 = INA2XX (INA226, INA228, INA238, INA231, INA260); 8 = DroneCAN. INA226: 0 to 36 V, 16-bit, I2C, C49851 $0.679 in stock; INA228 and INA238 out of stock | [W12], [W13], [W14] | Opened; quote |
| CAN for DroneCAN | ArduPilot: 120 Ω twisted pair, 1 Mbit default. DroneCAN "micro" connector: JST GH 4-pin, pin 1 power 5.0 to 5.5 V, 500 mA per device. TCAN1044V: 4.5 to 5.5 V supply, 1.7 to 5.5 V logic I/O, ±58 V bus fault, C1852061 $0.46. SN65HVD230 runs from 3.3 V only, C12084 $0.565 | [W15], [W16], [W17], [W18] | Opened; quote |
| Connectors | JST GH (1.25 mm): 1 A, 50 V; SM04B-GHS-TB C189895 $0.4413. JST SH (1.0 mm): 1 A, 50 V; SM04B-SRSS-TB C160404 $0.2147 | [W19], [W3] | Opened; quote |

On JLCPCB's parts pages, all the ICs above are "Extended" parts (an extra loading fee each); the SS34 Schottky diode was the only "Basic" part found [W3].

### 5.1 Datasheet values used in the design calculations

These were read from the datasheet PDFs themselves (text extracted from the PDF) for `scripts/design_calcs.py`; the config file `configs/design_inputs.yaml` names the source of each value.

| Part | Values | Source | Check |
| --- | --- | --- | --- |
| LT8641 (datasheet Rev B, 08/18) | Feedback reference 0.81 V (0.804 to 0.816 V at 25 °C; 0.79 to 0.822 V over temperature); RT = 46.5/fSW - 5.2 and Table 1 (18.2 kΩ for 2.0 MHz); minimum on-time 35 ns typical, 50 ns maximum; minimum off-time 80 / 110 ns; top switch 105 mΩ, bottom 55 mΩ; top current limit 6.2 / 8.2 / 9.9 A, falling to 6.4 A at 80 % duty; TR/SS current 1.2 / 1.9 / 2.6 µA; θJA 40 °C/W; BIAS tied to VOUT for 3.3 to 25 V outputs; design equations 1 to 10. Typical application "2MHz 5V, 3.5A Step-Down Converter": 18.2 kΩ, 2.2 µH (IHLP2525CZ-01), 47 µF 1210, 1 MΩ / 191 kΩ with 4.7 pF, 10 nF, 2 x 1 µF + 4.7 µF input | [W22] | Opened (ADI datasheet as hosted by LCSC; analog.com timed out) |
| LT8641 LTspice example | `LT8641.asc` shipped with LTspice 26.1.1: 48 V in, 5 V at 3.5 A, 3.3 µH, 47 µF, RT 41.2 kΩ (1 MHz) | local LTspice install | Opened |
| TI TLV62569 (SLVSDG1C, Oct 2017) | 2.5 to 5.5 V in, 2 A; feedback 0.6 V (0.588 to 0.612 V); 1.5 MHz; switches 100 mΩ / 60 mΩ; current limit 3 A (DBV); θJA 188.2 °C/W (SOT-23-5); example 2.2 µH, 10 µF output, 4.7 µF input; R2 at most 200 kΩ, 6.8 pF feed-forward for 100 kΩ. LCSC C141836: 633,930 in stock, $0.0681 (5+); JLCPCB Extended | [W20], [W3] | Opened; quote |
| Diodes AP2112 (DS39724 Rev 2-2) | θJA 184 °C/W (SOT25, no heatsink); junction limit +150 °C; input 2.5 to 6.0 V | [W6] | Opened |
| TI TCAN1044V (SLLSFG2, Dec 2019) | Supply current dominant 45 mA typical, 70 mA maximum (60 Ω load); recessive 4.5 / 7.5 mA; 130 mA maximum with a bus fault | [W21] | Opened |
| STM32H743 (DS12110 Rev 7, April 2019, older revision) | Run current at 480 MHz, VOS0, all peripherals on: 220 mA typical, 342 mA maximum at 25 °C, 436 mA at 85 °C (Table 130); ADC sample capacitor 4 pF typical, external input impedance 50 kΩ maximum; analog pins PA0, PA1, PC2, PC3, PA4, PA5 and others accept 0 mA positive injection (Table 59); 480 MHz only on silicon revision V | [M4] | Opened; re-check against Rev 11 when ST's PDF opens |
| STM32H743 output pins (DS12110 Rev 7) | Output current sunk by any I/O and control pin: 20 mA maximum; total for all pins 140 mA | [M4] | Opened |
| KiCad 10 simulator | ngspice built in; runs only in the Schematic Editor's simulator window (`kicad-cli` 10.0.8 has no simulation command, checked with `kicad-cli --help`); exports plots as PNG and data as CSV | [T19] | Opened; checked locally |
| IPC-2221 trace current | I = k ΔT^0.44 A^0.725, A in mil², k = 0.048 outer and 0.024 inner (KiCad 10.0 PCB calculator source) | [T18] | Opened |
| JLCPCB 4-layer 1.6 mm stack-up JLC04161H-7628 | Outer copper 0.035 mm, prepreg 7628 0.2104 mm, inner copper 0.0152 mm, core 1.065 mm | [J10] | Opened |

## 6. Fabrication and assembly

| Item | Facts | Source | Check |
| --- | --- | --- | --- |
| JLCPCB 4-layer limits | Trace and space 0.09 / 0.09 mm (2-layer 0.10 / 0.10); via 0.15 mm hole, 0.25 mm diameter; annular ring 0.20 mm recommended, 0.15 mm minimum; drill 0.15 to 6.3 mm; finishes HASL, ENIG, OSP | [J1] | Opened |
| JLCPCB clearances (capabilities page, read 17 Nov 2026) | Via hole to track 0.2 mm; inner-layer via hole to copper 0.2 mm; PTH to track 0.28 mm minimum (0.35 recommended); NPTH to track 0.2 mm; pad to track 0.1 mm (1 oz); SMD pad to pad, different nets, 0.15 mm; via hole-to-hole 0.2 mm; copper to a routed board edge 0.2 mm; 0.2 or 0.25 mm via holes cost extra only with a via diameter under 0.45 mm (preferred minimum hole 0.2 mm) | [J1] | Opened |
| JLCPCB assembly fees (page updated 22 Oct 2026) | Economic: single-sided, 2/4/6 layers, 0.8 to 1.6 mm, 2 to 50 boards; setup $8.18, stencil $1.53, extended-part loading $3.07. Standard: double-sided allowed; setup $25.56 single-sided or $51.12 double-sided; stencil $8.21 or $16.42; $1.53 per part type | [J2], [J3] | Opened |
| JLCPCB instant quote, 5 bare boards, 36 x 36 mm, 4 layers, 1.6 mm, 3 to 4 day build | $8.00 with OSP finish; $24.70 with ENIG (finish +$16.70); "desktop price" in JLCPCB's own app $2.00 and $18.70 | [J7] | Quote, read by me |
| Shipping to Pakistan, 0.15 kg (quote page) | E-POST $11.69 (10 to 21 business days); S.F Express Economy $28.23 (6 to 8); DHL Express $35.46 (3 to 5); UPS $46.33 (5 to 7) | [J7] | Quote, read by me |
| PCBWay | Trace and space 0.1 / 0.1 mm, annular ring 0.15 mm; "From $5/10pcs"; assembly from 5 pieces with free stencil; offers KiCad DRC rule files | [J8], [J9] | Opened |

## 7. Open and comparable designs

| Design | Processor and sensors | Files and licence | What it shows or lacks | Source |
| --- | --- | --- | --- | --- |
| Pixhawk FMUv3 | STM32F427 plus IO processor; L3GD20, MPU6000, LSM303D, MS5611 | Altium files, CC BY-SA 3; last commit 2022 | The classic open reference; large (81.5 x 50 mm), old sensors | [O1], [O2] |
| Pixracer (FMUv4) | STM32F427; ICM-20608, MPU9250, MS5611; microSD | Altium files, no licence stated; last push 2017 | 36 x 36 mm with 30.5 mm holes, the same size class as this board | [O3], [O4] |
| OpenPilot Revolution | STM32F405; MPU6000, MS5611, HMC5883L | DIY zip with schematic, layout, Gerbers, BOM; licence not stated | Runs ArduPilot, but 1 MB flash | [O5] |
| Crazyflie 2.1+ (Bitcraze) | STM32F405 + nRF51822; BMI088, BMP388 | Schematic PDFs only; layout not published | Polished research drone, own firmware; $240 | [O6] |
| OpenFC-Lite (2026) | RP2354B; BMI270 | KiCad, CERN-OHL-S-2.0, OSHWA certified; marked beta | Runs Betaflight, not ArduPilot | [O7] |
| STM32H743 flight controller (Emrecanbl, 2025) | STM32H743VIT; BMI088, BMP280 | KiCad 9; no licence | Custom firmware "in development"; no test results | [O8] |
| University student H743 board (2026) | STM32H743; BMI088 + ICM20602, BMP388 | Altium files and thesis; no licence | Flew 3 tests on ArduPilot, but the SD card was "Not functional", the compass failed, and a 26 MHz crystal had to be replaced by 24 MHz | [O9], [O10] |
| Holybro Kakute H7 v2 (closed) | STM32H743; BMI270, BMP280; 128 MB flash log | Closed | 35 x 35 mm, 3S to 8S, $52.00; supported by ArduPilot | [O11], [O12] |
| Holybro Pixhawk 6C (closed) | STM32H743 + STM32F103 IO; ICM-42688-P plus a Bosch IMU, MS5611 | Closed (standard DS-018 published) | $199.00 | [O13], [O14] |

**What this board does differently.** None of the open designs opened above publishes power-stage design calculations, measured IMU noise or vibration, or a bring-up and test report; none of the KiCad ones shows ERC and DRC running in CI that could be checked. The student H743 board shows what goes wrong without a design review (crystal frequency, SD card, compass). This board's contribution is the engineering record: requirements, a pin plan checked against ArduPilot's DMA rules, calculated and simulated predictions compared with scope measurements, automatic checks, and a test report from bench to hover, all open under an explicit hardware licence.

**Engineering question (not a novelty claim).** On a 36 x 36 mm 4-layer board with two different motion sensors on separate SPI buses and a low-noise sensor supply, how close does the measured gyro noise at rest come to the datasheet values, and does the board meet ArduPilot's 30 m/s² vibration guidance in a hover on a small quad?

## 8. Drone rules in Pakistan

Source: Civil Unmanned Aircraft Rules, 2025 (Ministry of Defence, September 2025, made under section 146 of the Pakistan Civil Aviation Act, 2023; "shall come into force at once"), PDF on the PCAA website [R1]. Opened; text extracted from the PDF (scanned, so the S.R.O. number is not legible).

| Rule | What it says |
| --- | --- |
| 3 | Categories by maximum take-off weight: I up to 250 g; II over 250 g to 5 kg; III over 5 kg to 25 kg; IV over 25 kg to 100 kg |
| 4 | "A person shall not possess, own or operate an unmanned aircraft unless it is registered"; apply within fifteen days of acquisition; category I and II registrations renewed every three years |
| 10 | Prohibited airspace: within 6 km of an aerodrome perimeter or 10 km along the runway axis; within 6 km of the border, working boundary or line of control; within 5 km of a port; defence and law-enforcement areas. Does not apply inside a "sufficiently lit building or covered space" with the owner's permission |
| 11 | Restricted airspace includes "within the precincts of a city or a town" and 6 to 12 km from an aerodrome |
| 18 | No permission needed for categories I to III when flown in permitted airspace, within visual line of sight, no higher than 200 ft, in daylight, one aircraft at a time, not from a moving vehicle |
| 33 | "A person shall not establish, own, relocate or operate a facility for the design, manufacture or repair of an unmanned aircraft without obtaining a certificate for the facility" |
| 41 | "A person shall not import or export an unmanned aircraft or part of an unmanned aircraft unless he is registered with the Director General" |

A newspaper report on an earlier 2024 draft [R2] is superseded by this text. The PCAA "UAV" portal button was disabled when opened [R3].

**What this means for the project:**
- Bench tests (props off) and indoor tests in a lit covered space with the owner's permission come first.
- Register the quadcopter before any outdoor flight; fly only outside city precincts and aerodrome zones, in sight, at or below 200 ft, in daylight.
- Open questions to settle with PCAA or NUST before ordering: whether importing an assembled flight controller board counts as importing a "part of an unmanned aircraft" (rule 41), and whether building one prototype as a student counts as operating a design "facility" (rule 33). This is a question to ask, not legal advice.

## 9. Open questions

1. Rules 33 and 41 (see section 8): ask PCAA or the NUST department before placing the order.
2. Which drone parts I already have (frame, motors, ESC, battery, radio, GPS); this sets the flight-test plan and its cost.
3. What the NUST lab can lend: bench supply with current limit, oscilloscope, debug probe.
4. Whether the board fits the Economic (single-sided) assembly option on 36 x 36 mm, or needs a larger board or double-sided assembly ($51.12 setup instead of $8.18).

## Sources

All accessed 15 Nov 2026.

- [A1] ArduPilot, Measuring Vibration: https://ardupilot.org/copter/docs/common-measuring-vibration.html (opened)
- [A2] ArduPilot, Mounting the Flight Controller: https://ardupilot.org/copter/docs/common-mounting-the-flight-controller.html (opened)
- [T1] KiCad download for Windows: https://www.kicad.org/download/windows/ (opened)
- [T2] KiCad 10.0.8 release: https://www.kicad.org/blog/2026/10/KiCad-10.0.8-Release/ (opened)
- [T3] KiCad licences: https://www.kicad.org/about/licenses/ and https://www.kicad.org/libraries/license/ (opened)
- [T4] KiCad system requirements: https://www.kicad.org/help/system-requirements/ (opened)
- [T5] KiCad 10.0 command-line interface: https://docs.kicad.org/10.0/en/cli/cli.html (opened)
- [T6] LTspice: https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator.html (opened)
- [T7] LTspice shortcuts and command-line options (ADI PDF): https://www.analog.com/media/en/news-marketing-collateral/solutions-bulletins-brochures/ltspice-keyboard-shortcuts-ink-saver.pdf (opened)
- [T8] Altium Designer release notes: https://www.altium.com/documentation/altium-designer/public-release-notes (opened)
- [T9] Altium downloads: https://www.altium.com/products/downloads (opened)
- [T10] Altium Designer system requirements: https://www.altium.com/documentation/altium-designer/system-requirements (opened)
- [T11] Altium Student Lab: https://www.altium.com/education/students (opened)
- [T12] Altium student licences: https://www.altium.com/education/student-licenses and https://www.altium.com/documentation/knowledge-base/altium-designer/apply-renew-student-license (opened)
- [T13] EasyEDA download centre: https://easyeda.com/page/download (opened)
- [T14] STM32CubeMX: https://www.st.com/en/development-tools/stm32cubemx.html (opened)
- [T15] STM32CubeProgrammer: https://www.st.com/en/development-tools/stm32cubeprog.html (opened)
- [T16] Mission Planner downloads: https://firmware.ardupilot.org/Tools/MissionPlanner/ (opened)
- [T17] QGroundControl v5.1.5 release: https://github.com/mavlink/qgroundcontrol/releases/tag/v5.1.5 (opened)
- [F1] ArduPilot, Porting to a new flight controller board: https://ardupilot.org/dev/docs/porting.html (opened)
- [F2] ArduPilot, Building the code: https://ardupilot.org/dev/docs/building-the-code.html (opened)
- [F3] ArduPilot, Setting up the build environment on Windows 11: https://ardupilot.org/dev/docs/building-setup-windows11.html (opened)
- [F4] ArduPilot, Using DFU to load the bootloader: https://ardupilot.org/dev/docs/using-DFU-to-load-bootloader.html (opened)
- [F5] ArduPilot, Firmware limitations on boards with 1 MB flash: https://ardupilot.org/copter/docs/common-limited-firmware.html (opened)
- [F6] ArduPilot feature lists: https://firmware.ardupilot.org/Copter/stable/MatekF405/features.txt and https://firmware.ardupilot.org/Copter/stable/MatekH743/features.txt (opened)
- [F7] ArduPilot source: `libraries/AP_HAL_ChibiOS/hwdef/MatekH743/hwdef.dat`, `MatekH743-bdshot/hwdef.dat`, `hwdef-bl.dat`, `scripts/chibios_hwdef.py`, https://github.com/ArduPilot/ardupilot (opened)
- [F8] ArduPilot, ESC telemetry and bidirectional DShot: https://ardupilot.org/copter/docs/common-esc-telemetry.html (opened)
- [F9] ArduPilot, `Tools/AP_Bootloader/board_types.txt`: https://github.com/ArduPilot/ardupilot (opened)
- [F10] ArduPilot, Harmonic notch filtering: https://ardupilot.org/copter/docs/common-imu-notch-filtering.html (opened)
- [F11] ArduPilot, DShot ESCs: https://ardupilot.org/copter/docs/common-dshot-escs.html (opened)
- [F12] ArduPilot, ESC issues: https://ardupilot.org/copter/docs/common-esc-issues.html (opened)
- [F13] ArduPilot `libraries/AP_SerialManager/AP_SerialManager.h` (SerialProtocol_ESCTelemetry = 16, SerialProtocol_RCIN = 23), `MatekH743-bdshot/defaults.parm`, `Pixhawk6X/hwdef.dat` (ICM-45686 and BMI088 SPI settings), `HGLRC_H743_EVO/hwdef.dat` (DPS368 on the DPS310 driver), `AP_InertialSensor_Invensensev3.cpp` (ICM-45686 ID 0xE9): https://github.com/ArduPilot/ardupilot (opened)
- [F14] ArduPilot `libraries/AP_HAL_ChibiOS/hwdef/scripts/chibios_hwdef.py` and `dma_resolver.py` at commit fe04abb61ecb80e1ac6893f56896690b91041f6f, run locally by `scripts/check_hwdef.py` (opened and run)
- [M1] ST, STM32H743VI: https://www.st.com/en/microcontrollers-microprocessors/stm32h743vi.html (opened; DS12110 Rev 11.0, 21 Jan 2026 listed)
- [M2] ST, STM32H723VG: https://www.st.com/en/microcontrollers-microprocessors/stm32h723vg.html (opened)
- [M3] ST, STM32F405RG: https://www.st.com/en/microcontrollers-microprocessors/stm32f405rg.html (opened)
- [M4] DS12110 Rev 7 (April 2019, older revision, mirror copy): https://xdevs.com/doc/STM/stm32h743bi.pdf (opened)
- [M5] LCSC search, STM32H743VIT6 and alternatives: https://www.lcsc.com/search?q=STM32H743VIT6 (quote)
- [M6] JLCPCB parts library: https://jlcpcb.com/parts/componentSearch?searchTxt=STM32H743VIT6 (quote)
- [P1] Pixhawk standards (DS-009, DS-010, DS-011, DS-012, DS-018, DS-019): https://github.com/pixhawk/Pixhawk-Standards (opened)
- [P2] Pixhawk reference hardware: https://github.com/pixhawk/Hardware (opened)
- [P3] Holybro Kakute H7 v2 and Mini: https://docs.holybro.com/autopilot/kakute-h7-v1-v2-mini/kakute-h7-v2/overview (opened)
- [S1] TDK ICM-45686 product page: https://invensense.tdk.com/products/motion-tracking/6-axis/icm-45686/ (opened, re-checked)
- [S2] ICM-45686 datasheet DS-000577 r1.0 (distributor copy): https://www.hestore.eu/prod_getfile.php?id=20047 (opened)
- [S3] Bosch BMI088 product page: https://www.bosch-sensortec.com/products/motion-sensors/imus/bmi088/ (opened, re-checked)
- [S4] BMI088 datasheet BST-BMI088-DS001 r1.9: https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi088-ds001.pdf (opened)
- [S5] TDK ICM-42688-P product page: https://www.invensense.tdk.com/en-us/products/6-axis/icm-42688-p (opened)
- [S6] ICM-42688-P datasheet DS-000347 r1.6 (third-party copy): https://pcbsync.com/wp-content/uploads/2026/07/ICM-42688-P-Datasheet-TDK.pdf (opened)
- [S7] BMI270 datasheet BST-BMI270-DS000 r1.6: https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi270-ds000.pdf (opened)
- [S8] TDK ICM-42670-P product page: https://invensense.tdk.com/products/motion-tracking/6-axis/icm-42670-p/ (opened)
- [S9] ArduPilot board files `Pixhawk6X`, `Pixhawk6C`, `MatekH743` (hwdef.dat) and `HGLRC_H743_EVO/README.md`: https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_HAL_ChibiOS/hwdef (opened)
- [S10] PX4, Pixhawk 6X: https://docs.px4.io/main/en/flight_controller/pixhawk6x.html (opened)
- [S11] ArduPilot, EKF overview: https://ardupilot.org/copter/docs/common-apm-navigation-extended-kalman-filter-overview.html (opened)
- [S12] Infineon DPS368 datasheet v1.1: https://www.infineon.com/dgdl/Infineon-DPS368-DS-v01_00-EN.pdf (opened)
- [S13] ArduPilot source `libraries/AP_Baro/AP_Baro_DPS280.h`: https://github.com/ArduPilot/ardupilot (opened)
- [S14] TE MS5611-01BA03: https://www.te.com/en/product-MS561101BA03-50.html (opened)
- [S15] Bosch BMP388 and BMP390 datasheets and pressure sensor overview: https://www.bosch-sensortec.com/products/environmental-sensors/pressure-sensors/ (opened)
- [S16] Goertek SPL06-001 datasheet (DigiKey copy) and DigiKey listing: https://www.digikey.com/en/products/detail/goertek-microelectronics-inc/SPL06-001/17005535 (opened)
- [S17] TDK ICP-20100: https://invensense.tdk.com/products/smartpressure/icp-20100/ (opened)
- [S18] ArduPilot, Magnetic interference: https://ardupilot.org/copter/docs/common-magnetic-interference.html (opened)
- [S19] MEMSIC MMC5983MA datasheet Rev A: https://www.memsic.com/Public/Uploads/uploadfile/files/20220119/MMC5983MADatasheetRevA.pdf (opened)
- [S20] ArduPilot, Downloading and analysing logs: https://ardupilot.org/copter/docs/common-downloading-and-analyzing-data-logs-in-mission-planner.html (opened)
- [S21] Winbond W25N01GV datasheet Rev Q: https://www.winbond.com/resource-files/W25N01GV%20Rev%20Q%20051721.pdf (opened)
- [S22] ArduPilot issue #26900: https://github.com/ArduPilot/ardupilot/issues/26900 (opened)
- [W1] Grepow, LiPo battery voltage: https://www.grepow.com/blog/what-is-the-voltage-of-a-lipo-battery.html (opened)
- [W2] ADI LT8641: https://www.analog.com/en/products/lt8641.html (opened, datasheet Rev C)
- [W3] JLCPCB parts library and LCSC search for each part number listed (quote)
- [W4] ADI LT8609S: https://www.analog.com/en/products/lt8609s.html (opened, datasheet Rev D)
- [W5] TI TPS54360: https://www.ti.com/product/TPS54360 (opened)
- [W6] Diodes AP2112 datasheet DS39724 Rev 2-2: https://www.diodes.com/assets/Datasheets/AP2112.pdf (opened)
- [W7] TI TPS7A20 datasheet SBVS338H: https://www.ti.com/lit/ds/symlink/tps7a20.pdf (opened)
- [W8] TI TPS2116: https://www.ti.com/product/TPS2116 (opened)
- [W9] TI LM74700-Q1: https://www.ti.com/product/LM74700-Q1 (opened)
- [W10] ADI LTC4359: https://www.analog.com/en/products/ltc4359.html (opened)
- [W11] ST USBLC6-2: https://www.st.com/en/protections-and-emi-filters/usblc6-2.html (opened)
- [W12] ArduPilot `AP_BattMonitor_Params.cpp` and `AP_BattMonitor_INA2xx.cpp`: https://github.com/ArduPilot/ardupilot (opened)
- [W13] ArduPilot, Power modules: https://ardupilot.org/copter/docs/common-powermodule-landingpage.html (opened)
- [W14] TI INA226, INA228, INA238 product pages: https://www.ti.com/product/INA226 (opened)
- [W15] ArduPilot, CAN bus setup: https://ardupilot.org/copter/docs/common-canbus-setup-advanced.html (opened)
- [W16] DroneCAN hardware design recommendations: https://dronecan.github.io/Specification/8._Hardware_design_recommendations/ (opened)
- [W17] TI TCAN1044V: https://www.ti.com/product/TCAN1044V (opened)
- [W18] TI SN65HVD230: https://www.ti.com/product/SN65HVD230 (opened)
- [W19] JST GH and SH series: https://www.jst-mfg.com/product/index.php?series=105&lang=2 and https://www.jst-mfg.com/product/index.php?series=231&lang=2 (opened)
- [W20] TI TLV62569 datasheet SLVSDG1C: https://www.ti.com/lit/ds/symlink/tlv62569.pdf (opened); JLCPCB part page https://jlcpcb.com/partdetail/TexasInstruments-TLV62569DBVR/C141836 (opened)
- [W21] TI TCAN1044V datasheet SLLSFG2: https://www.ti.com/lit/ds/symlink/tcan1044v.pdf (opened)
- [W22] ADI LT8641 datasheet Rev B, copy hosted by LCSC for part C462660: https://datasheet.lcsc.com/datasheet/pdf/c7125f0998bd1e8b0cc46cc8fb159dc0.pdf?productCode=C462660 (opened)
- [T18] KiCad 10.0 source, PCB calculator track width: https://gitlab.com/kicad/code/kicad/-/raw/10.0/pcb_calculator/calculator_panels/panel_track_width.cpp (opened); KiCad PCB calculator manual: https://docs.kicad.org/10.0/en/pcb_calculator/pcb_calculator.html (opened)
- [T19] KiCad 10.0 Schematic Editor manual, Simulator chapter (Simulation_SPICE symbols, inferred R/L/C models, analysis types, cursors, measurements, tuning, PNG and CSV export): https://docs.kicad.org/10.0/en/eeschema/eeschema.html (opened)
- [J10] JLCPCB impedance calculator and stack-ups: https://jlcpcb.com/impedance (opened)
- [J1] JLCPCB PCB capabilities: https://jlcpcb.com/capabilities/pcb-capabilities (opened)
- [J2] JLCPCB assembly capabilities: https://jlcpcb.com/capabilities/pcb-assembly-capabilities (opened)
- [J3] JLCPCB assembly price: https://jlcpcb.com/help/article/pcb-assembly-price (opened)
- [J4] JLCPCB, Gerber and drill files in KiCad 9: https://jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-9 (opened)
- [J5] Fabrication Toolkit: https://github.com/bennymeg/Fabrication-Toolkit (opened)
- [J6] kicad-jlcpcb-tools: https://github.com/Bouni/kicad-jlcpcb-tools (opened)
- [J7] JLCPCB instant quote: https://cart.jlcpcb.com/quote (quote)
- [J8] PCBWay capabilities: https://www.pcbway.com/capabilities.html (opened)
- [J9] PCBWay assembly: https://www.pcbway.com/pcb-assembly.html (opened)
- [O1] Pixhawk Hardware repo: https://github.com/pixhawk/Hardware (opened)
- [O2] PX4, mRo Pixhawk: https://docs.px4.io/main/en/flight_controller/mro_pixhawk.html (opened)
- [O3] PX4, Pixracer: https://docs.px4.io/main/en/flight_controller/pixracer.html (opened)
- [O4] FMUv4 Pixracer files: https://github.com/AUAV-OpenSource/FMUv4-PixRacer (opened)
- [O5] ArduPilot, OpenPilot Revo Mini: https://ardupilot.org/copter/docs/common-openpilot-revo-mini.html (opened)
- [O6] Bitcraze Crazyflie 2.1+: https://www.bitcraze.io/products/crazyflie-2-1-plus/ (opened)
- [O7] OpenFC-Lite: https://github.com/OpenDrone-hw/OpenFC-Lite (opened)
- [O8] STM32H743 flight controller: https://github.com/Emrecanbl/STM32H743-Flight-Controller (opened)
- [O9] Student H743 board files: https://github.com/AlexBoa45/TFM_Custom_FC_Ardupilot (opened)
- [O10] ArduPilot forum thread on that board: https://discuss.ardupilot.org/t/university-student-project-custom-fc-pcb-board-space-application-study/142718 (opened)
- [O11] Holybro Kakute H7 v2: https://holybro.com/products/kakute-h7-v2 (opened)
- [O12] ArduPilot, Holybro Kakute H7: https://ardupilot.org/copter/docs/common-holybro-kakuteh7.html (opened)
- [O13] PX4, Pixhawk 6C: https://docs.px4.io/main/en/flight_controller/pixhawk6c.html (opened)
- [O14] Holybro Pixhawk 6C: https://holybro.com/products/pixhawk-6c (opened)
- [R1] PCAA, Civil Unmanned Aircraft Rules 2025: https://pcaa.gov.pk/rules-and-legislation/civil-unmanned-aircraft-rules-2025-1/ (PDF opened, text extracted)
- [R2] Dawn, 24 June 2024, on the earlier draft: https://www.dawn.com/news/1841590 (secondary)
- [R3] PCAA portals: https://pcaa.gov.pk/portals (opened)
