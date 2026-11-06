# Light Block A5 firmware

**Editable, host-tested prototype firmware for STM32G031G8U6TR.** The package includes a real ARM build, two independent four-pixel outputs, the A5 CV conversion, and reset/fault protection. It has **not been flashed or tested on hardware**. Compilation and simulated tests do not replace the bench gates below.

日本語要点: A5のバッファ付きCV入力専用です。ON / PROGRAM / CV、左右独立4 LED、初期20%上限を実装しました。通常の電源投入では選択モードで起動します。故障またはMCUリセット後、バックアップ領域の記録が残っている間は消灯を維持します。電源が完全に落ちると記録も消えるため、深い電圧低下と意図的な電源再投入は区別できません。色・アニメーションは未承認の試作初期値で、実機検証は未実施です。

## Board compatibility

This build is for the **A5 input network with U7 voltage follower, R24=330 Ω, R25=1 kΩ**, followed by PA0. Its nominal transfer is:

\[
V_{ADC}=\frac{100}{133}\left(\frac{V_{DD}}2+\frac{CV}{8}\right),\qquad
CV=10.64V_{ADC}-4V_{DD}.
\]

At 3.3 V, nominal −5 / 0 / +5 V CV gives approximately 0.77068 / 1.24060 / 1.71053 V at the ADC. **Do not flash this binary onto the unbuffered A4.1 input circuit.** The compile-time board revision is a configuration check, not automatic physical-board detection. Nominal resistor values and calibration remain distinct; no measured calibration is invented.

| MCU physical pin | Signal | Configuration |
|---:|---|---|
| 6 | PA0 | ADC channel0, A5 divided CV |
| 8 | PA2 | MODE_A, external10 kΩ pull-up |
| 9 | PA3 | MODE_B, external10 kΩ pull-up |
| 10 | PA4 | Active-low TPS2552-1 FAULT, falling-edge EXTI |
| 11 | PA5 | HIGH enables LEDs through the NPN and active-low /EN |
| 12 | PA6 | AF1, TIM3_CH1, left four LEDs |
| 13 | PA7 | AF1, TIM3_CH2, right four LEDs |
| 20 / 21 / 5 | PA13 / PA14 / PF2-NRST | SWDIO / SWCLK / reset, retained for service |

The switch common is grounded. Ordered bits are **(PA2/MODE_A, PA3/MODE_B)**: `01` ON, `11` PROGRAM, `10` CV, `00` invalid. Confirm the physical throw orientation in the assembled panel. Valid changes need20 ms stable contact state. An observed `00` blanks the next frame immediately without cycling LED power.

## User behavior and provisional defaults

After a new backup-domain power-up, the firmware waits at least100 ms with LED power disabled, requires a valid switch position and a valid fresh ADC/reference sample, enables VLED, waits5 ms, transmits an all-black frame including its reset interval, then enters the selected mode. There is no additional startup gesture.

| Mode | Prototype default |
|---|---|
| ON | All eight pixels neutral RGB white, each channel at code51 |
| PROGRAM |8-second triangular brightness cycle; warm left/cool right, half-cycle phase offset |
| CV | Absolute CV controls brightness; positive warm, negative cool; ±50 mV deadband; full level at ±5 V; larger magnitudes saturate |

These colors, period, curve, deadband and left/right behavior are configurable prototype choices, **not approved artistic behavior**. Both renderer and wire encoder enforce code≤51 per color channel (20% of255). This is a commanded PWM cap; it is not a measured lumen, supply-current, temperature or power-up-transient limit.

The ADC takes a PA0/VREFINT pair approximately once per millisecond. It uses the chip's factory VREFINT calibration at3.0 V, ADC self-calibration, and a160.5-cycle acquisition interval at15 MHz nominal. The CV estimate uses an integer1/8 IIR filter. `lb_calibration_t` supplies measured zero/gain corrections when available. Until then, `lb_calibration_default()` uses the nominal divider and affine network. Invalid reference data, implausible3.0–3.6 V VDDA, or an ADC sample older than20 ms during operation latches the output off.

## Fault and reset policy

The TPS2552-1 latch can clear when its enable is disabled. Therefore **a high FAULT input after shutdown is not permission to re-enable**. The firmware never uses a retry timer or a switch change to clear a fault. It preserves a nonzero record in two backup registers before PA5 can go high. Fault handling immediately lowers PA5, stops TIM3/DMA, forces both data pins low, and records a fault.

Normal automatic startup requires both backup words to be zero and a power-reset cause, with no software, watchdog, option-byte or low-power-reset cause. A retained boot/armed/fault marker, a torn/corrupt marker, or a warm reset inhibits startup. Reset flags are captured before initialization and cleared only after classification. `PINRSTF` accompanies other system resets and is not mistaken for an external-reset-only flag. See [docs/reset_policy.md](docs/reset_policy.md).

**Bounded limitation:** the STM32 power flag combines BOR and POR/PDR. The selected package ties the backup supply to VDD. A sufficiently deep or long supply collapse can erase the backup words exactly as unplugging does. The next boot can therefore retry even if the physical fault remains. This implements retained-domain lockout and ordinary power-cycle recovery; it does not claim a nonvolatile or independent hardware fault interlock. Fault/brownout testing remains a release gate. A stricter requirement needs an independently retained latch or a revised explicitly approved recovery mechanism.

No option bytes, readout protection, boot selection or flash calibration storage are changed automatically. The default build has no software service-clear command. After diagnosis, remove the module's supply and allow both rails to discharge before restarting. An SWD reset/reflash with power retained intentionally remains locked out. The debug variables expose captured reset flags, marker words, decision, ADC readings and last fault reason.

## Build and test

The required, unmodified SDK source is included with licenses. It is pinned to CubeG0 **v1.6.3** and exact device/HAL commits in [vendor/pins.json](vendor/pins.json). A normal build performs no network download. GNU Make, a host C11 compiler, and `arm-none-eabi-gcc` are sufficient. The ARM build is freestanding and links `libgcc`; it does not need newlib, an RTOS or a heap.

```sh
make test
make test-sanitize
make arm
make timing
```

For a toolchain outside PATH:

```sh
make arm ARM_PREFIX=/path/to/toolchain/bin/arm-none-eabi-
```

The supplied managed environment cannot run LeakSanitizer's process inspection. AddressSanitizer and UndefinedBehaviorSanitizer were run using `ASAN_OPTIONS=detect_leaks=0 make test-sanitize`; no project code allocates memory. The leak-check limitation is recorded rather than described as a successful leak test.

For a complete clean release/check with captured logs and hashes:

```sh
python3 tools/make_release.py --arm-prefix arm-none-eabi-
# In the supplied managed environment only:
python3 tools/make_release.py --arm-prefix /path/to/arm-none-eabi- --no-leak-check
```

`dist/` holds the ELF (debug symbols), HEX, BIN, map, reports and license copies. The BIN starts at`0x08000000`; use the HEX or ELF with an appropriate STM32 programming tool. No programming command was executed here. The linker reserves2 KiB of stack within the8 KiB RAM and rejects overflow. See `dist/verification.json` for exact final sizes, compiler identity, vectors and SHA-256 digests.

## What was verified

Host tests exercise mode debounce, wraparound time, the independent A5 voltage oracle across3.0/3.3/3.6 V, calibration, render caps, GRB order, distinct left/right data, DMA buffer boundaries, a timer-preload model, all frequency points in the ±3% envelope, reset classes and corrupt marker words. Fault injection covers before enable, during the marker write, at the EN rising write, immediately after the final input check, at interrupt-mask restoration, during DMA start and during active transmission. It verifies that deasserting FAULT or changing modes cannot restart an inhibited boot. Random sequences begin from an active output and exercise subsequent fault/switch events.

The ARM target really configures TIM3 update DMA bursts to CCR1/CCR2, rather than implementing a host-only waveform model. The encoded buffer has708 halfwords. At least254 complete zero cells have elapsed before the immediate completion-stop path, giving≥320.583 µs at the fast end of the tested frequency envelope. Exact timings are generated from compiled constants in [dist/timing.md](dist/timing.md).

## Remaining bench gates

1. Check PA5 reset/off polarity, SWD reset, software reset and watchdog reset with a current-limited supply; confirm no retained-domain auto-enable.
2. Scope PA6/PA7 and each level-shifted first DIN with independent test colors. Confirm GRB order, timing, reset low and idle-low behavior on the actual LED lot. The manufacturer document's footer is V1.4 despite the URL ending`1.0.pdf`; use the recorded hash and the page4 timing table.
3. Exercise an output short/hot fault, fault assertion during a frame/enable, fault release while disabled, retained-domain brownout, and complete supply collapse. Confirm the documented distinction and characterize any restart under deep supply loss.
4. Verify the A5 ADC network with calibrated −5 /0 /+5 V input, power-off cases, noise and resistor tolerances; then apply measured zero/gain values. Check the passive IN→THRU path separately from firmware.
5. Measure full-white code51 supply current and enclosed temperature, startup transients, watchdog timing, stack high-water use and clock/translator behavior over the intended operating range. Adjust the cap only after thermal/optical validation.

## Source map

- `include/lb_config.h`: board revision, cap, timing and prototype constants.
- `src/light_block.c`: portable mode, ADC, rendering, encoder, reset policy and race-checked guard.
- `platform/stm32g031/`: actual GPIO, ADC, clock, timer/DMA, IRQ, watchdog and linker integration.
- `tests/`: runnable host tests and a timing report compiled from the same constants.
- `vendor/STM32CubeG0/`: pinned licensed ST/Arm sources; no vendor source was modified.
- `sources.json`: primary documents, exact hashes, sections and SDK provenance.

The manufacturer timing calculation incorporates the datasheet's HSI factory/temperature/supply spread using a conservative ±3% frequency envelope. It is not a measurement of PLL jitter, pad rise/fall times, translator delay or DMA bus contention. Primary references and corresponding limitations are listed in [sources.json](sources.json).
