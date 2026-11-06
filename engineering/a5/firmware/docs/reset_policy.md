# A5 reset and fault contract

## Required physical behavior

PA5 high drives the NPN, which pulls the active-low TPS2552-1 EN low. Reset leaves the NPN base pulled down and EN pulled up: VLED is off. The firmware preloads PA5 and both data pins low before selecting output mode. A fault ISR has priority0, DMA priority1, SysTick priority3. The external TPS current limiter is independent of this software.

The enable path executes a short interrupt-masked transaction: check software latch plus GPIO/EXTI pending state; write and read back an ARMED backup record; check again; set PA5 high; check again; restore the prior mask. A pending FAULT interrupt at restoration immediately disables power. The transfer-start path uses the same guard so a frame cannot restart DMA after a fault. FAULT handling never waits for HAL polling.

## Retained record

| Register | Meaning |
|---|---|
| TAMP_BKP0R | `0x4c420101` BOOT, `0x4c420102` ARMED, or `0x4c420103` FAULT |
| TAMP_BKP1R | Bitwise inverse of BKP0R |
| TAMP_BKP2R | Diagnostic `lb_fault_t`; not authorization |

The nonzero word is written first. A reset between the two writes leaves a retained or corrupt pair; both block startup. Readback failure also blocks enable. Normal firmware never zeroes these registers, requests BDRST, or initializes an RTC in a way that resets its domain. A zero pair is accepted only with the power-reset cause and no conflicting reset cause.

## STM32G031 reset flags

RM0444 Rev6, RCC_CSR, p212, defines PWRRSTF as the combined BOR/POR/PDR indication. PINRSTF is set by NRST or another system-reset source. IWDGRSTF, WWDGRSTF, SFTRSTF, OBLRSTF and LPWRRSTF identify causes that must inhibit this boot. The flags persist until RMVF removes them; a power reset also resets the flag domain. The code snapshots RCC_CSR before HAL work, reads the retained pair without clearing it, classifies, and then issues RMVF. It uses the SDK's symbolic bit masks.

| Event | Backup pair | Result |
|---|---|---|
| New supply / lost backup domain | both zero, power flag only (PIN may coexist) | Stabilize, verify inputs, start selected mode |
| External reset | retained or zero, no power flag | Stay off |
| Watchdog/software/option/low-power reset | any | Stay off |
| BOR with backup domain retained | nonzero marker or corrupt pair | Stay off |
| Fault input deasserts after shutdown | retained FAULT | Stay off |
| Switch changes after fault | retained FAULT | Stay off |
| Full supply collapse, including a deep fault-induced dip | both zero, power flag | Indistinguishable from power cycling; can restart |

The last row is a known hardware boundary, not a passed no-retry guarantee. DS12992 says the package's missing VBAT pin is internally bonded to VDD/VDDA. RM0444 section5.1.3 describes RTC-domain reset on power-up after both its supplies have been off. BOR and complete loss of backup power must be tested separately on the actual PCB.

There is no hidden switch gesture or automatic retry count. An accepted normal startup is attempted once per newly lost-backup-domain boot. The software latch is never cleared within the boot. A stronger latch that survives arbitrary VDD loss requires a hardware or nonvolatile design change and an explicit service/recovery policy.

## What host testing proves

The host simulator executes the same guard/controller code as the ARM binary and models fault edges at each critical step, including an edge after the final read but before interrupt-mask restoration. It also tests already active DMA and late completion. These tests establish software ordering and latch invariants under the modeled API contract. They do not measure electrical propagation, actual EXTI latency, retained-voltage thresholds, hardware DMA completion timing or a real short circuit.

Primary sources: [RM0444 Rev6](https://www.st.com/resource/en/reference_manual/rm0444-stm32g0x1-advanced-armbased-32bit-mcus-stmicroelectronics.pdf), [DS12992 Rev4](https://www.st.com/resource/en/datasheet/stm32g031g8.pdf), [TI TPS255x datasheet](https://www.ti.com/lit/ds/symlink/tps2552-1.pdf). Exact source provenance is in`../sources.json`.
