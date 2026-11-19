# Data

This board produces its own data; nothing is downloaded.

| Data | Where it comes from | Where it goes |
| --- | --- | --- |
| ArduPilot flight and bench logs (`.BIN`) | microSD card on the board, or downloaded with Mission Planner | `data/raw/` (not in git); the analysis scripts write summaries and figures to `reports/` |
| Oscilloscope captures (CSV or PNG) | lab oscilloscope during bring-up | `data/raw/scope/` (not in git); selected figures copied to `reports/figures/` |
| Simulation results | KiCad's built-in simulator (ngspice), run on the test circuits in `sim/` | plots exported from KiCad to `reports/figures/` |

Logs can contain GPS positions. Before any log is shared, positions are removed or the log is recorded indoors without GPS.
