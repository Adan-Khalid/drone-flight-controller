"""The flight controller circuit: every part, its value, footprint, LCSC number and pin nets.

Sources: docs/PIN_PLAN.md (processor pins), docs/DECISIONS.md and reports/design_calcs.md
(values), the datasheet pin tables listed in hardware/gen/symbols.py and docs/RESEARCH_LOG.md.
Pins are referenced by number. Every visible pin must be connected or listed as not connected.
"""

from __future__ import annotations

from dataclasses import dataclass, field

FP_R = {"0402": "Resistor_SMD:R_0402_1005Metric", "0603": "Resistor_SMD:R_0603_1608Metric"}
FP_C = {"0402": "Capacitor_SMD:C_0402_1005Metric", "0603": "Capacitor_SMD:C_0603_1608Metric",
        "0805": "Capacitor_SMD:C_0805_2012Metric", "1206": "Capacitor_SMD:C_1206_3216Metric",
        "1210": "Capacitor_SMD:C_1210_3225Metric"}
JST_GH = "Connector_JST:JST_GH_SM0{n}B-GHS-TB_1x0{n}-1MP_P1.25mm_Horizontal"
JST_SH = "Connector_JST:JST_SH_SM0{n}B-SRSS-TB_1x0{n}-1MP_P1.00mm_Horizontal"
PAD = "TestPoint:TestPoint_Pad_1.0x1.0mm"

# LCSC numbers (read from LCSC / JLCPCB pages, 15 and 16 Nov 2026)
LCSC_R = {"10": "C22859", "120": "C25079", "220": "C25091", "1k": "C11702", "1.5k": "C25867",
          "4.7k": "C25900", "5.1k": "C25905", "10k": "C25744", "18.2k": "C25859", "28.7k": "C26972",
          "100k": "C25741", "150k": "C25755", "191k": "C270632", "453k": "C27009", "1M": "C26083"}
LCSC_C = {("4.7p", "0402"): "C1569", ("6.8p", "0402"): "C1576", ("15p", "0402"): "C1548",
          ("10n", "0402"): "C15195", ("100n", "0402"): "C1525", ("1u", "0402"): "C52923",
          ("1u", "0603"): "C15849", ("2.2u", "0603"): "C23630", ("10u", "0805"): "C15850",
          ("4.7u", "1206"): "C29823", ("47u", "1210"): "C77101"}


@dataclass
class Part:
    ref: str
    lib: str
    value: str
    fp: str
    sheet: str
    conn: dict = field(default_factory=dict)   # pin number -> net
    nc: tuple = ()                              # pin numbers deliberately not connected
    lcsc: str = ""
    mpn: str = ""
    dnp: bool = False


PARTS: list[Part] = []
_counters: dict[str, int] = {}


def add(ref, lib, value, fp, sheet, conn, nc=(), lcsc="", mpn="", dnp=False):
    PARTS.append(Part(ref, lib, value, fp, sheet, dict(conn), tuple(nc), lcsc, mpn, dnp))


def R(ref, value, a, b, sheet, size="0402"):
    add(ref, "Device:R_Small", value, FP_R[size], sheet, {"1": a, "2": b}, lcsc=LCSC_R[value])


def C(ref, value, a, b, sheet, size="0402", lcsc=None):
    add(ref, "Device:C_Small", value + "F", FP_C[size], sheet, {"1": a, "2": b},
        lcsc=lcsc or LCSC_C[(value, size)])


def TP(ref, net, sheet, label):
    add(ref, "Connector:TestPoint", label, PAD, sheet, {"1": net})


# ============================================================================ power sheet
S = "power"
add("J1", "Connector_Generic_MountingPin:Conn_01x08_MountingPin", "ESC", JST_SH.format(n=8), S,
    {"1": "VBAT_IN", "2": "GND", "3": "ESC_CUR", "4": "ESC_TLM",
     "5": "M1_OUT", "6": "M2_OUT", "7": "M3_OUT", "8": "M4_OUT"}, nc=("MP",),
    lcsc="C160407", mpn="SM08B-SRSS-TB")
# reverse-battery ideal diode: MOSFET source at the battery, drain at the protected rail
add("Q1", "Transistor_FET:CSD18543Q3A", "CSD18543Q3A", "dronefc:TI_VSON-8_3.3x3.3mm_P0.65mm_NexFET_GatePad0.47mm",
    S, {"1": "VBAT_IN", "4": "Q1_GATE", "5": "VBAT"}, lcsc="C840100")
add("U1", "Power_Management:LM74700", "LM74700-Q1", "Package_TO_SOT_SMD:SOT-23-6", S,
    {"1": "U1_VCAP", "2": "GND", "3": "VBAT_IN", "4": "VBAT", "5": "Q1_GATE", "6": "VBAT_IN"},
    lcsc="C2941042", mpn="LM74700QDBVRQ1")
C("C1", "100n", "U1_VCAP", "VBAT_IN", S)
add("D1", "Device:D_TVS", "SMBJ30A", "Diode_SMD:D_SMB", S, {"1": "VBAT", "2": "GND"}, lcsc="C83851")
# 5 V buck, values of ADI's 2 MHz 5 V typical application
C("C2", "4.7u", "VBAT", "GND", S, size="1206")
C("C3", "1u", "VBAT", "GND", S, size="0603")
C("C4", "1u", "VBAT", "GND", S, size="0603")
add("U2", "dronefc:LT8641", "LT8641", "dronefc:ADI_UDC-18_3x4mm_P0.5mm_LT8641", S,
    {"4": "VBAT", "13": "VBAT", "14": "VBAT", "15": "U2_RT", "16": "U2_SS", "3": "U2_BST",
     "8": "SW5", "1": "+5V_REG", "20": "FB5", "2": "U2_INTVCC", "18": "GND"},
    nc=("17", "19"), lcsc="C462660", mpn="LT8641EUDC#TRPBF")
R("R1", "18.2k", "U2_RT", "GND", S)
C("C5", "10n", "U2_SS", "GND", S)
C("C6", "100n", "U2_BST", "SW5", S)
C("C7", "1u", "U2_INTVCC", "GND", S)
add("L1", "Device:L", "2.2uH", "Inductor_SMD:L_Coilcraft_XAL4020-XXX", S,
    {"1": "SW5", "2": "+5V_REG"}, lcsc="C3151182", mpn="XAL4020-222MEC")
R("R2", "1M", "+5V_REG", "FB5", S)
R("R3", "191k", "FB5", "GND", S)
C("C8", "4.7p", "+5V_REG", "FB5", S)
C("C9", "47u", "+5V_REG", "GND", S, size="1210")
# power path: regulator 5 V has priority over USB VBUS (switch-over near 4.5 V)
add("U3", "Power_Management:TPS2116DRL", "TPS2116", "Package_TO_SOT_SMD:SOT-583-8", S,
    {"1": "GND", "2": "+5V", "3": "+5V_REG", "4": "U3_PR1", "5": "+5V_REG", "6": "VBUS"},
    nc=("8",), lcsc="C3235557", mpn="TPS2116DRLR")
R("R4", "100k", "+5V_REG", "U3_PR1", S)
R("R5", "28.7k", "U3_PR1", "GND", S)
C("C10", "1u", "VBUS", "GND", S)
C("C11", "10u", "+5V", "GND", S, size="0805")
# 3.3 V buck for the processor and SD card
add("U4", "Regulator_Switching:TLV62569DBV", "TLV62569DBV", "Package_TO_SOT_SMD:SOT-23-5", S,
    {"1": "+5V", "2": "GND", "3": "SW3", "4": "+5V", "5": "FB3"}, lcsc="C141836",
    mpn="TLV62569DBVR")
C("C12", "4.7u", "+5V", "GND", S, size="1206")
add("L2", "Device:L", "2.2uH", "Inductor_SMD:L_Murata_DFE201610P", S, {"1": "SW3", "2": "+3V3"},
    lcsc="C79317", mpn="DFE201612P-2R2M")
R("R6", "453k", "+3V3", "FB3", S)
R("R7", "100k", "FB3", "GND", S)
C("C13", "6.8p", "+3V3", "FB3", S)
C("C14", "10u", "+3V3", "GND", S, size="0805")
C("C15", "10u", "+3V3", "GND", S, size="0805")
# low-noise 3.3 V for the sensors, behind a 10 ohm / 10 uF filter
R("R8", "10", "+5V", "+5V_F", S, size="0603")
C("C16", "10u", "+5V_F", "GND", S, size="0805")
add("U5", "Regulator_Linear:TPS7A20xxxDBV", "TPS7A2033", "Package_TO_SOT_SMD:SOT-23-5", S,
    {"1": "+5V_F", "2": "GND", "3": "+5V_F", "5": "+3V3_S"}, lcsc="C2862740",
    mpn="TPS7A2033PDBVR")
C("C17", "1u", "+5V_F", "GND", S)
C("C18", "1u", "+3V3_S", "GND", S)
# battery voltage sense (ratio 16) and ESC current-sense filter
R("R9", "150k", "VBAT", "VBAT_SENSE", S)
R("R10", "10k", "VBAT_SENSE", "GND", S)
C("C19", "100n", "VBAT_SENSE", "GND", S)
R("R11", "1k", "ESC_CUR", "ESC_CUR_SENSE", S)
C("C20", "100n", "ESC_CUR_SENSE", "GND", S)
for i, net in enumerate(("VBAT_IN", "VBAT", "+5V_REG", "VBUS", "+3V3", "+5V_F", "GND"), start=1):
    add(f"#FLG{i:02d}", "power:PWR_FLAG", "PWR_FLAG", "", S, {"1": net})

# ============================================================================ processor sheet
S = "mcu"
mcu = {
    # power and core
    "11": "+3V3", "27": "+3V3", "50": "+3V3", "75": "+3V3", "100": "+3V3", "6": "+3V3",
    "21": "+3V3", "20": "+3V3", "10": "GND", "19": "GND",
    "48": "VCAP1", "73": "VCAP2", "14": "NRST", "94": "BOOT0", "12": "HSE_IN", "13": "HSE_OUT",
}
PINMAP = {  # processor pin name -> net, from docs/PIN_PLAN.md
    "PA0": "M3", "PA1": "M4", "PA5": "IMU1_SCK", "PA6": "IMU1_MISO",
    "PA8": "LED_DATA", "PA9": "TEL2_TX", "PA10": "TEL2_RX", "PA11": "USB_DM", "PA12": "USB_DP",
    "PA13": "SWDIO", "PA14": "SWCLK",
    "PB0": "M1", "PB1": "M2", "PB6": "I2C1_SCL", "PB7": "I2C1_SDA", "PB10": "I2C2_SCL",
    "PB11": "I2C2_SDA",
    "PC0": "VBAT_SENSE", "PC1": "ESC_CUR_SENSE", "PC6": "RC_TX", "PC7": "RC_RX", "PC8": "SD_D0",
    "PC9": "SD_D1", "PC10": "SD_D2", "PC11": "SD_D3", "PC12": "SD_CK", "PC13": "IMU2_GCS",
    "PC15": "IMU1_CS",
    "PD2": "SD_CMD", "PD5": "GPS1_TX",
    "PD6": "GPS1_RX", "PD7": "IMU1_MOSI", "PD8": "GPS2_TX", "PD9": "GPS2_RX",
    "PE0": "ESC_TLM", "PE3": "LED0", "PE4": "LED1", "PE7": "TEL1_RX", "PE8": "TEL1_TX",
    "PE9": "TEL1_RTS", "PE10": "TEL1_CTS", "PE11": "IMU2_ACS", "PE12": "IMU2_SCK",
    "PE13": "IMU2_MISO", "PE14": "IMU2_MOSI",
}
add("U7", "MCU_ST_STM32H7:STM32H743VITx", "STM32H743VIT6", "Package_QFP:LQFP-100_14x14mm_P0.5mm",
    S, mcu, nc=(), lcsc="C5271084", mpn="STM32H743VIT6TR")
for i in range(5):
    C(f"C{21 + i}", "100n", "+3V3", "GND", S)
C("C26", "10u", "+3V3", "GND", S, size="0805")
C("C27", "1u", "+3V3", "GND", S)          # VDDA / VREF+
C("C28", "100n", "+3V3", "GND", S)        # VBAT pin
C("C29", "2.2u", "VCAP1", "GND", S, size="0603")
C("C30", "2.2u", "VCAP2", "GND", S, size="0603")
C("C31", "100n", "NRST", "GND", S)
R("R12", "10k", "BOOT0", "GND", S)
add("Y1", "Device:Crystal_GND24", "8MHz", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", S,
    {"1": "HSE_IN", "2": "GND", "3": "HSE_OUT"}, lcsc="C403948", mpn="TAXM8M4RFDCET2T")
C("C32", "15p", "HSE_IN", "GND", S)
C("C33", "15p", "HSE_OUT", "GND", S)
R("R13", "1k", "LED0", "LED0_K", S)
R("R14", "1k", "LED1", "LED1_K", S)
add("D2", "Device:LED_Small", "red", "LED_SMD:LED_0603_1608Metric", S,
    {"1": "LED0_K", "2": "+3V3"}, lcsc="C2286", mpn="KT-0603R")
add("D3", "Device:LED_Small", "white", "LED_SMD:LED_0603_1608Metric", S,
    {"1": "LED1_K", "2": "+3V3"}, lcsc="C2290", mpn="KT-0603W")
TP("TP1", "SWDIO", S, "SWDIO")
TP("TP2", "SWCLK", S, "SWCLK")
TP("TP3", "NRST", S, "NRST")
TP("TP4", "BOOT0", S, "BOOT0")
TP("TP5", "+3V3", S, "3V3")
TP("TP6", "GND", S, "GND")

# ============================================================================ sensors sheet
S = "sensors"
add("U8", "dronefc:ICM-45686", "ICM-45686", "dronefc:TDK_LGA-14_3x2.5mm_P0.5mm_ICM-45686", S,
    {"12": "IMU1_CS", "13": "IMU1_SCK", "14": "IMU1_MOSI", "1": "IMU1_MISO",
     "8": "+3V3_S", "5": "+3V3_S", "6": "GND"},
    nc=("4", "9", "2", "3", "7", "10", "11"), lcsc="C22459454")
C("C34", "100n", "+3V3_S", "GND", S)
C("C35", "100n", "+3V3_S", "GND", S)
add("U9", "dronefc:BMI088", "BMI088",
    "Package_LGA:Bosch_LGA-16_4.5x3mm_P0.5mm_LayoutBorder7x1y_ClockwisePinNumbering", S,
    {"3": "+3V3_S", "11": "+3V3_S", "4": "GND", "6": "GND", "7": "GND", "8": "IMU2_SCK",
     "9": "IMU2_MOSI", "10": "IMU2_MISO", "15": "IMU2_MISO", "14": "IMU2_ACS", "5": "IMU2_GCS"},
    nc=("1", "12", "13", "16"), lcsc="C194919")
C("C36", "100n", "+3V3_S", "GND", S)
C("C37", "100n", "+3V3_S", "GND", S)
add("U10", "dronefc:DPS368", "DPS368", "dronefc:Infineon_PG-VLGA-8_2x2.5mm_P0.65mm_DPS368", S,
    {"2": "+3V3_S", "3": "I2C2_SDA", "4": "I2C2_SCL", "5": "GND", "8": "+3V3_S", "6": "+3V3_S",
     "1": "GND", "7": "GND"}, lcsc="C3232508", mpn="DPS368XTSA1")
C("C38", "100n", "+3V3_S", "GND", S)
C("C39", "100n", "+3V3_S", "GND", S)
R("R15", "10k", "I2C2_SDA", "+3V3", S)
R("R16", "10k", "I2C2_SCL", "+3V3", S)
add("J2", "Connector:Micro_SD_Card_Det_Hirose_DM3AT", "microSD",
    "Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5", S,
    {"1": "SD_D2", "2": "SD_D3", "3": "SD_CMD", "4": "+3V3", "5": "SD_CK", "6": "GND",
     "7": "SD_D0", "8": "SD_D1", "SH": "GND"}, nc=("9", "10"), lcsc="C114218",
    mpn="DM3AT-SF-PEJM5")
for i, net in enumerate(("SD_CMD", "SD_D0", "SD_D1", "SD_D2", "SD_D3")):
    R(f"R{17 + i}", "10k", net, "+3V3", S)
C("C40", "10u", "+3V3", "GND", S, size="0805")
C("C41", "100n", "+3V3", "GND", S)

# ============================================================================ connectors sheet
S = "io"
add("J3", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C",
    "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", S,
    {"A4": "VBUS", "A1": "GND", "A5": "USB_CC1", "B5": "USB_CC2", "A6": "USB_DP", "B6": "USB_DP",
     "A7": "USB_DM", "B7": "USB_DM", "SH": "GND"}, nc=("A8", "B8"), lcsc="C165948",
    mpn="TYPE-C-31-M-12")
R("R22", "5.1k", "USB_CC1", "GND", S)
R("R23", "5.1k", "USB_CC2", "GND", S)
add("U6", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", S,
    {"1": "USB_DP", "6": "USB_DP", "3": "USB_DM", "4": "USB_DM", "5": "VBUS", "2": "GND"},
    lcsc="C7519")
# The CAN port, motor outputs 5 to 8 and the buzzer driver were removed to keep the board on
# 4 layers at the lowest cost (docs/DECISIONS.md, D31). Their reference numbers are not reused.
add("J5", "Connector_Generic_MountingPin:Conn_01x06_MountingPin", "TELEM1", JST_GH.format(n=6), S,
    {"1": "+5V", "2": "TEL1_TX", "3": "TEL1_RX", "4": "TEL1_CTS", "5": "TEL1_RTS", "6": "GND"},
    nc=("MP",), lcsc="C133065", mpn="SM06B-GHS-TB")
add("J6", "Connector_Generic_MountingPin:Conn_01x06_MountingPin", "GPS1", JST_GH.format(n=6), S,
    {"1": "+5V", "2": "GPS1_TX", "3": "GPS1_RX", "4": "I2C1_SCL", "5": "I2C1_SDA", "6": "GND"},
    nc=("MP",), lcsc="C133065", mpn="SM06B-GHS-TB")
R("R25", "1.5k", "I2C1_SCL", "+3V3", S)
R("R26", "1.5k", "I2C1_SDA", "+3V3", S)
# receiver (SERIAL7) and TELEM2 (SERIAL2) on solder pads: two JST GH 4-pin connectors did not
# fit on the 36 x 36 mm board next to the other five connectors and the microSD socket
for i, (net, label) in enumerate((("RC_TX", "TX7"), ("RC_RX", "RX7"), ("TEL2_TX", "TX2"),
                                  ("TEL2_RX", "RX2"), ("+5V", "5V"), ("GND", "GND")), start=18):
    TP(f"TP{i}", net, S, label)
# motor outputs 1 to 4 (to the ESC connector): 220 ohm protection resistors
for i in range(1, 5):
    R(f"R{26 + i}", "220", f"M{i}", f"M{i}_OUT", S)
# solder pads: spare 5 V and ground, GPS2 (SERIAL4) and the serial LED output
for ref, net, label in (("TP11", "+5V", "5V"), ("TP12", "GND", "GND"), ("TP13", "GPS2_TX", "TX4"),
                        ("TP14", "GPS2_RX", "RX4"), ("TP15", "LED_OUT", "LED")):
    TP(ref, net, S, label)
R("R35", "220", "LED_DATA", "LED_OUT", S)

SHEETS = [("power", "Power"), ("mcu", "Processor"), ("sensors", "Sensors and storage"),
          ("io", "Connectors and interfaces")]
POWER_SYMBOLS = {"GND": "power:GND", "+5V": "power:+5V", "+3V3": "power:+3V3"}
