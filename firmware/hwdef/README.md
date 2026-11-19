# ArduPilot board definition

`DroneFC-H743/` holds the files ArduPilot needs to build firmware for this board:

| File | What it does |
| --- | --- |
| `hwdef.dat` | Every pin, bus, sensor and default for the flight firmware |
| `hwdef-bl.dat` | The smaller pin set for the bootloader (USB, TELEM1, SD card, LED) |
| `defaults.parm` | Parameter defaults: RC input on SERIAL7, ESC telemetry on SERIAL5 |

The pin map is explained in `docs/PIN_PLAN.md`. It is derived from ArduPilot's MatekH743 board files, and these files are GPL-3.0-or-later like ArduPilot.

## Building (WSL2 Ubuntu on Windows)

ArduPilot's recommendation for Windows is WSL2, with the source kept inside the WSL file system.

1. Clone ArduPilot (or your fork) inside WSL and install the build tools with `Tools/environment_install/install-prereqs-ubuntu.sh -y`, as in ArduPilot's "Building the code" guide. Build the existing `MatekH743` target once first, to prove the toolchain works before building this board.
2. Copy `DroneFC-H743/` into `libraries/AP_HAL_ChibiOS/hwdef/`.
3. Board ID: ArduPilot allocates IDs from 1000 up only through a pull request to `Tools/AP_Bootloader/board_types.txt`. For a first local compile test, add a line `AP_HW_DRONEFC_H743 <a number not used in that file>` to your local copy; before any firmware is shared, reserve a real ID through a pull request and use that number.
4. Build:
   ```
   ./waf configure --board DroneFC-H743
   ./waf copter
   Tools/scripts/build_bootloaders.py DroneFC-H743
   ```
5. Check the DMA allocation: ArduPilot's `dma_resolver.py` does not stop the build when streams run out; it writes a line "The following peripherals can't be resolved for DMA" into the generated `hwdef.h` in the build folder. That line must be absent, or list only peripherals marked `NODMA` on purpose. Save the generated `hwdef.h`, `features.txt` and the build log in `reports/firmware/`.

## First flash (after the board exists)

Hold BOOT0 high while powering the board to enter ST's USB DFU bootloader, flash the bootloader with `dfu-util -a 0 --dfuse-address 0x08000000 -D DroneFC-H743_bl.bin`, power-cycle, then load the firmware with Mission Planner or `./waf copter --upload`.
