# Pin plan

Which processor pin does what, for the STM32H743VIT6 (LQFP100). This is the plan the schematic is drawn from and the source of the ArduPilot board file `firmware/hwdef/DroneFC-H743/hwdef.dat`.

## Where it comes from

Choosing pins on an STM32 for ArduPilot is constrained by three things at once: which pins can carry each peripheral (the chip's alternate functions), which timers can drive motors with DMA (needed for DShot), and how many DMA streams exist. Rather than solving this from scratch, the plan starts from ArduPilot's own board files for the **Matek H743** (`MatekH743` and its bidirectional-DShot variant `MatekH743-bdshot`). They use the same chip in the same 100-pin package (only ports A to E), and ArduPilot builds and flies them. I then changed it for this board:

| Changed | From the Matek board | On this board | Why |
| --- | --- | --- | --- |
| IMU 1 | ICM-42688-P on SPI1 | ICM-45686 on SPI1 (same pins) | ICM-42688-P out of stock; ArduPilot's Invensensev3 driver supports the ICM-45686 (ID 0xE9) |
| IMU 2 | ICM-42605 / ICM-20602 on SPI4 | BMI088 on SPI4, two chip selects (accelerometer PE11, gyroscope PC13) | Second maker for the second EKF core; the BMI088 has separate accelerometer and gyroscope chips inside |
| Barometer | DPS310 on I2C2 | DPS368 on I2C2 | DPS368 uses ArduPilot's DPS310 driver (as on the HGLRC H743 board file) |
| OSD | MAX7456 on SPI2 | removed | No analog video on this board |
| Battery divider | scale 11.0 | scale 16.0 | 150 k / 10 k divider keeps the ADC pin below 3.3 V at the 48.4 V surge clamp (D8) |
| Motor outputs | 12 outputs | 4 outputs, the bidirectional-DShot map (8 until D31) | A quadcopter needs 4; RPM telemetry for the harmonic notch |
| Extra analog inputs, PINIO, external SPI | used | left free | Fewer parts; the pins stay free for later |

## Pin table

| Pin | Function | Peripheral | Goes to | Note |
| --- | --- | --- | --- | --- |
| PH0, PH1 | HSE oscillator | RCC | 8 MHz crystal | ArduPilot expects 8 or 24 MHz |
| PA11, PA12 | USB D-, D+ | OTG_FS | USB-C | |
| PA13, PA14 | SWDIO, SWCLK | SWD | debug pads | first bring-up with a debug probe |
| BOOT0 | boot mode | | pull-down plus pad or button | high at power-up enters the ST DFU bootloader |
| PA5, PA6, PD7 | SCK, MISO, MOSI | SPI1 | ICM-45686 | own bus, DMA not shared |
| PC15 | IMU1_CS | GPIO | ICM-45686 CS | |
| PE12, PE13, PE14 | SCK, MISO, MOSI | SPI4 | BMI088 | own bus, DMA not shared |
| PE11 | BMI088_A_CS | GPIO | BMI088 accelerometer CS | |
| PC13 | BMI088_G_CS | GPIO | BMI088 gyroscope CS | |
| PB10, PB11 | SCL, SDA | I2C2 (bus 0) | DPS368 barometer | on board |
| PB6, PB7 | SCL, SDA | I2C1 (bus 1) | GPS connector and I2C connector | external compass |
| PC0 | battery voltage | ADC1 channel 10 | 150 k / 10 k divider with 100 nF | `HAL_BATT_VOLT_SCALE 16.0` |
| PC1 | battery current | ADC1 channel 11 | ESC current sensor | scale set per ESC |
| PE3, PE4 | LED0, LED1 | GPIO | status LEDs | |
| PE7, PE8, PE10, PE9 | RX, TX, CTS, RTS | UART7 = SERIAL1 | TELEM1 connector | flow control for telemetry radios |
| PA10, PA9 | RX, TX | USART1 = SERIAL2 | TELEM2 / companion computer | |
| PD5, PD6 | TX, RX | USART2 = SERIAL3 | GPS1 connector | with I2C1 |
| PD9, PD8 | RX, TX | USART3 = SERIAL4 | GPS2 / spare pads | |
| PE0, PE1 | RX, TX | UART8 = SERIAL5 | ESC connector (telemetry in) | `SERIAL5_PROTOCOL 16` |
| PB8, PB9 | RX, TX | UART4 = SERIAL6 | spare pads | |
| PC7, PC6 | RX, TX | USART6 = SERIAL7 | RC receiver connector | `SERIAL7_PROTOCOL 23` (RC input) |
| PB0, PB1 | motor 1, 2 | TIM3 CH3, CH4 | ESC connector | output 1 bidirectional DShot |
| PA0, PA1 | motor 3, 4 | TIM2 CH1, CH2 | ESC connector | output 3 bidirectional DShot |
| PA8 | serial LED | TIM1 CH1 | pad | WS2812 strip |
| PC8 to PC11, PC12, PD2 | D0 to D3, CK, CMD | SDMMC1 | microSD socket | 4-bit |

Every motor output has a 220 Ω series resistor (D13).

**Free pins kept for later:** SPI2 (PB12 to PB15), SPI3 (PB3 to PB5), PD4, PE2, PD10, PD11, PD14, PD15, PE5, PE6, PA4, PA7, PC4, PC5.

## Connectors

| Connector | Type | Pins | Signals |
| --- | --- | --- | --- |
| ESC | JST SH 1.0 mm, 8-pin | 8 | VBAT, GND, current (PC1), telemetry (PE0), motor 1 to 4 (PB0, PB1, PA0, PA1). Pin order matched to the chosen ESC's cable in the schematic step |
| TELEM1 | JST GH 1.25 mm, 6-pin | 6 | 5 V, TX (PE8), RX (PE7), CTS (PE10), RTS (PE9), GND, in Pixhawk DS-009 order |
| GPS1 | JST GH 6-pin | 6 | 5 V, TX (PD5), RX (PD6), SCL (PB6), SDA (PB7), GND, in Pixhawk DS-009 order |
| RC input | JST GH 4-pin | 4 | 5 V, TX (PC6), RX (PC7), GND |
| TELEM2 | JST GH 4-pin, or pads if space runs out | 4 | 5 V, TX (PA9), RX (PA10), GND |
| USB | USB-C | | 5 V, D+, D-, CC resistors |
| Debug | pads | 5 | 3.3 V, SWDIO, SWCLK, NRST, GND |

## Checking the plan in STM32CubeMX (my step)

CubeMX is ST's own pin and clock planner. Its job here is to prove that every pin really has the function the table gives it and that the clock tree works; the DMA allocation is checked afterwards by the ArduPilot build itself.

1. New project for the part number **STM32H743VITx**.
2. Set each pin in the table to its function (click the pin in the pinout view and choose the function), enable each peripheral in its mode (SPI1 and SPI4 as full-duplex master, I2C1 and I2C2, UART7 with hardware flow control, the other UARTs asynchronous, SDMMC1 in 4-bit mode, USB OTG FS as device, ADC1 channels 10 and 11, the timer channels as PWM outputs, RCC with an external crystal, SYS debug as serial wire).
3. Read every warning CubeMX gives about pins or peripherals that clash, and write each one down with how it was resolved.
4. Clock configuration: 8 MHz crystal into the PLL, the system clock at 480 MHz (needs silicon revision V; revision Y is rated to 400 MHz, D10), and 48 MHz for USB.
5. Save the `.ioc` file as `firmware/cubemx/DroneFC-H743.ioc` and export a picture of the pinout to `reports/figures/cubemx_pinout.png`.

Any pin that has to move is changed in this table, in `hwdef.dat` and in the schematic at the same time.

## Checking the DMA plan with the ArduPilot build

ArduPilot's build reads `hwdef.dat` and assigns DMA streams itself (`dma_resolver.py`). If the motor timers, SPI buses and UARTs ask for more streams than exist, it does not stop: it writes "The following peripherals can't be resolved for DMA" into the generated `hwdef.h`. `scripts/check_hwdef.py` runs ArduPilot's processor at a pinned commit on this board's files and fails on that line; it also checks that the IMU buses and motor timers have their own streams. Result: pass (`reports/firmware/hwdef_check.md`). It runs in CI on every push, and the full firmware build in WSL2 follows.

**Change, 18 Nov 2026 (DECISIONS D31):** the CAN port (PD0, PD1, PD3), motor outputs 5 to 8 (PA2, PA3, PD12, PD13) and the buzzer (PA15) were removed to keep the board on 4 layers at the lowest cost. Those pins are now free; the serial LED output on PA8 became PWM 5. ArduPilot's DMA check still passes (`reports/firmware/hwdef_check.md`).
