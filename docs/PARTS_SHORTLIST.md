# Parts shortlist

First choice and alternatives for every main part, 15 Nov 2026. Specs come from the datasheets and product pages listed in `RESEARCH_LOG.md`. Prices are USD for one piece, read from LCSC or the JLCPCB parts library on 15 Nov 2026; stock and prices change daily and are re-checked in the BOM step before ordering. "Ext" means a JLCPCB Extended part (an extra loading fee per part type at assembly); every IC below is Extended.

Nothing is ordered. The final choice is made after the pin plan and the schematic review.

## Chosen parts

| Role | Part | Why this one | Key specs (datasheet) | LCSC / JLCPCB | Price, stock |
| --- | --- | --- | --- | --- | --- |
| Processor | ST STM32H743VIT6 (tape-and-reel `TR` order code) | 2 MB flash keeps ArduPilot's full feature set (scripting, FFT notch, DroneCAN); used on Pixhawk 6C and MatekH743, so reference pin maps exist; LQFP100 can be inspected and reworked by hand | Cortex-M7 480 MHz, 1 MB RAM, 2x SDMMC, 2x USB OTG, 1.62 to 3.6 V, LQFP100 14 x 14 mm | C5271084, Ext | $12.0959 (JLCPCB), 980 in stock |
| Crystal | 8 MHz (part to be chosen in the BOM step) | ArduPilot crystals are "normally 8Mhz or 24Mhz"; 8 MHz matches the MatekH743 board file. A 2026 student board had to replace a 26 MHz crystal | to be checked | to be checked | to be priced |
| Motion sensor 1 | TDK ICM-45686 | Newest InvenSense part with an ArduPilot driver (Invensensev3); low noise; in stock. Used three times on Pixhawk 6X Rev 8 | Gyro noise 3.8 mdps/√Hz, accel 70 µg/√Hz; up to ±4000 dps and ±32 g; 0.42 mA; LGA-14 2.5 x 3.0 x 0.81 mm; SPI 24 MHz | C22459454, Ext | $10.3136, 1,072 in stock |
| Motion sensor 2 | Bosch BMI088 | Different maker and MEMS design from sensor 1; Bosch markets it for "vibration robustness" in drones; ±24 g range; ArduPilot driver; flown on Pixhawk 6X and Crazyflie | Gyro 0.014 °/s/√Hz; accel 160 (X, Y) / 190 (Z) µg/√Hz at ±3 g; accel ODR up to 1600 Hz, gyro 2000 Hz; LGA-16 3.0 x 4.5 x 0.95 mm; SPI 10 MHz | C194919, Ext | $6.3937, 1,301 in stock |
| Barometer | Infineon DPS368 | In stock; ArduPilot's DPS310 driver covers it; sealed (IPx8) package | ±6 Pa (±0.5 m) relative accuracy; 0.2 Pa RMS at 64x oversampling; VLGA-8 2.0 x 2.5 x 1.1 mm; SPI or I2C | C3232508, Ext | $4.4253, 10,858 in stock |
| Compass | External, on the GPS mast (no compass on the board) | ArduPilot advises mounting the compass away from high-current wiring; boards with an onboard compass usually disable it | n/a | n/a | n/a |
| Flight logs | microSD socket on 4-bit SDMMC | Same approach as Pixhawk 6X, 6C and MatekH743; no size limit; ArduPilot's flash (dataflash) logs are "typically 16MB" and an open issue reports broken logs on W25N01 chips | Socket part to be chosen in the BOM step | to be checked | to be priced |
| 5 V regulator | ADI LT8641 | Coolest and smallest of the three 60 V-class options compared at 2 A (`reports/design_calcs.md`, section 6), most current margin, and an ADI-tested 2 MHz 5 V typical application; 65 V rating gives margin over the input surge clamp; plenty of stock | 3 to 65 V in, 3.5 A continuous (5 A peak), 200 kHz to 3 MHz, 2.5 µA quiescent, QFN 3 x 4 mm, θJA 40 °C/W; datasheet Rev B | C462660, Ext | $11.14 (JLCPCB), 3,016 in stock |
| 5 V regulator passives | from ADI's 2 MHz 5 V typical application: RT 18.2 kΩ, 2.2 µH (Vishay IHLP2525CZ-01 or equivalent with saturation above 4 A), 47 µF 1210 X5R/X7R output, 1 MΩ / 191 kΩ feedback with 4.7 pF, 10 nF soft-start, 2 x 1 µF + 4.7 µF input rated 50 V | Checked by `scripts/design_calcs.py` for 6.0 to 26.7 V input | see `reports/design_calcs.md` | to be chosen in the BOM step | to be priced |
| 3.3 V for the processor and SD card | TI TLV62569DBVR buck | An LDO would overheat at the processor's current (see `reports/design_calcs.md`, section 3); this buck loses 10 to 27 mW in its switches | 2.5 to 5.5 V in, 2 A, 1.5 MHz, 0.6 V reference, 100 / 60 mΩ switches, 3 A limit, SOT-23-5 (θJA 188.2 °C/W) | C141836, Ext | $0.0681 (LCSC, 5+), 633,930 in stock |
| 3.3 V for the motion sensors and barometer | TI TPS7A2033 | Very low noise and high ripple rejection, so switching noise from the 5 V regulator does not reach the sensors | 300 mA, 7 µVRMS (10 Hz to 100 kHz), 95 dB PSRR at 1 kHz | C2862740, Ext | $0.2042, 161,605 in stock |
| USB / battery power path | TI TPS2116 | Automatic priority switch: the battery-fed 5 V supply takes over from USB without back-feeding the computer | 1.6 to 5.5 V, 2.5 A, 40 mΩ | C3235557, Ext | $0.38, 64,159 in stock |
| Reverse-battery protection | TI LM74700-Q1 ideal-diode controller with an N-channel MOSFET | Near-zero loss compared with a diode; MOSFET chosen in the BOM step | 3.2 to 65 V, withstands -65 V | C2941042, Ext | $2.73, 13,821 in stock |
| Input surge clamp | Littelfuse SMBJ30A | Stand-off above a full 6S pack, clamp below the LT8641's 65 V | 30 V stand-off, 33.3 V breakdown, 48.4 V clamp at 12.4 A, 600 W | C83851, Ext | $0.1267, 16,310 in stock |
| USB-C connector and ESD | TYPE-C-31-M-12 receptacle; ST USBLC6-2SC6 | Common at JLCPCB; ESD array rated to IEC 61000-4-2 level 4 | USB-C 16-pin; USBLC6 3.5 pF max | C165948; C7519, Ext | $0.1869; $0.157 |
| CAN transceiver (removed 18 Nov 2026, DECISIONS D31) | TI TCAN1044V (SOIC-8) | 5 V supply with 3.3 V logic pins; ±58 V bus fault protection; DroneCAN at ArduPilot's 1 Mbit default | 4.5 to 5.5 V VCC, 1.7 to 5.5 V VIO, up to 8 Mbps | C1852061, Ext | $0.46, 1,522 in stock |
| Connectors to GPS, telemetry, CAN, I2C | JST GH (1.25 mm), e.g. SM04B-GHS-TB for 4-pin | Pinouts follow the Pixhawk DS-009 connector standard, so standard cables fit | 1 A per contact, 50 V | C189895 (4-pin), Ext | $0.4413, 30,369 in stock |
| Connector to the 4-in-1 ESC, debug | JST SH (1.0 mm), e.g. SM04B-SRSS-TB | Hobby ESC cables use JST SH; Pixhawk uses SH for debug | 1 A per contact, 50 V | C160404 (4-pin), Ext | $0.2147, 70,563 in stock |

Small passives fixed by the calculations: battery divider 150 kΩ / 10 kΩ with 100 nF; sensor supply filter 10 Ω with 10 µF; 220 Ω in series with each motor output (see `docs/DECISIONS.md`, D8, D12, D13).

Battery monitoring uses the analog voltage and current inputs that ArduPilot reads as `BATT_MONITOR` 4: a resistor divider on the board for battery voltage, and the current-sense output of the ESC or power module. No current shunt sits on the board itself, because motor current never flows through the flight controller.

## Alternatives kept in reserve

| Role | Alternative | When to use it | Facts |
| --- | --- | --- | --- |
| Processor | STM32H743ZIT6 (LQFP144) | if more pins are needed | C114408, $10.7821, 2,589 in stock; 20 x 20 mm body is large for a 36 mm board |
| Motion sensor 1 | TDK ICM-42688-P | the usual partner on Pixhawk 6X, 6C and Matek H743 | 0 in stock at LCSC on 15 Nov 2026 (price shown $21.81, looks wrong) |
| Motion sensor 2 | Bosch BMI270 | cheaper second sensor | C2836813, $2.4348, 7,204 in stock; gyro 0.007 dps/√Hz (performance mode) |
| Barometer | TE MS5611 | the classic Pixhawk barometer | C15639, $6.1944, 4,229 in stock; QFN 5 x 3 mm |
| Optional onboard compass | MEMSIC MMC5983MA or Isentek IST8310 | bench tests without a GPS | C404329 $2.0097, 5,715 in stock; C2683055 $3.1292, 8,103 in stock |
| Extra log memory | Winbond W25N01GV (1 Gbit SPI NAND) | if the SD card causes trouble | C88868, $9.6904, 3,145 in stock; ArduPilot driver AP_Logger_W25NXX |
| 5 V regulator | ADI LT8609S | smaller 2 A part | C580305, $11.04, only 133 in stock; 42 V rating is below the SMBJ30A clamp |
| 5 V regulator, low cost | TI TPS54360 | if cost matters more than heat and size | C44377, $0.6839, 22,047 in stock; 4.5 to 60 V, 3.5 A; non-synchronous: needs a Schottky catch diode (0.76 to 1.14 W at 2 A) and an 8.2 µH inductor |
| 5 V regulator, low cost, synchronous | TI LMR36520 | not recommended: 2 A rating, 1.8 A minimum low-side limit, 0.72 to 0.81 W at 2 A | C2879422, $1.2174, 4,722 in stock; 4.2 to 65 V, 400 kHz, HSOIC-8 |
| Sensor LDO | TI LP5907-3.3 | second source for the low-noise rail | C80670, 6.5 µVRMS, 82 dB at 1 kHz |
| Power path | TI LM66100 ideal diode, or SS34 Schottky (a JLCPCB Basic part) | simpler, with more voltage drop | C2869734 $0.1949; C8678 $0.0351, 550 mV at 3 A |
| Reverse protection, alternative | ADI LTC4359 | second source for the ideal-diode controller | C3234107, $12.64, 132 in stock |
| CAN transceiver, 3.3 V only | TI SN65HVD230 | if no 5 V supply is wanted on the transceiver | C12084, $0.565, 121,218 in stock |

## Rejected, and why

| Part | Reason |
| --- | --- |
| STM32F405RGT6, STM32H723VGT6 | 1 MB flash: ArduPilot drops scripting, FFT notch and DroneCAN on 1 MB boards; H723 out of stock |
| Bosch BMP388, BMP390 | BMP388 missing from Bosch's product overview and listed obsolete by a distributor; BMP390 shown as stopped and out of stock at LCSC |
| Infineon DPS310, Goertek SPL06-001 | listed obsolete or stopped, 0 in stock |
| TDK ICP-20100 | TDK lists it as end of life |
| ST LIS3MDL | ST termination notice for LIS3MDLTR |
| INA228, INA238 digital power monitors | out of stock; and not needed, since current is measured by the ESC or power module |
| Diodes AP2112K-3.3 for the processor rail | dropping 5.05 V to 3.3 V at 0.34 A (typical) burns 0.60 W; with θJA 184 °C/W the junction would reach 155 °C at 45 °C ambient, above its 150 °C limit (224 °C worst case) |
