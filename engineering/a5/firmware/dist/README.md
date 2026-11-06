# A5 firmware build — prototype only

Built for STM32G031G8U6TR and the A5 U7-buffered,330 Ω /1 kΩ divided CV input. Do not use this binary with the A4.1 CV circuit.

Actual ARM compilation and host verification passed. **No device was flashed and no hardware test was performed.** Colors, animation and CV response are configurable prototype defaults.

Compiler: arm-none-eabi-gcc (15:13.2.rel1-2) 13.2.1 20231009

Host tests: 987,189 assertions across seven suites; ASan and UBSan passed. LeakSanitizer status: NOT RUN: explicit container/process-inspection limitation.

Flash: 10,712 bytes. Static RAM including alignment: 1,800 bytes, plus2,048 bytes stack reservation.

Files: ELF for debugging, Intel HEX or BIN for a suitable programming tool, map for layout, verification.json for hashes/provenance, timing.md for calculations, logs/ for exact checks, licenses/ for third-party terms. BIN load address:0x08000000.

The retained backup marker blocks warm resets and retained-domain brownouts. Complete supply collapse can erase the marker and permit a new attempt. There is no fault retry timer or hidden switch arming gesture. Read ../README.md and ../docs/reset_policy.md before first powered testing.

Copy all license files with any binary distribution.
