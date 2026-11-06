#!/usr/bin/env python3
"""Build/check the A5 firmware without network access; save exact release evidence."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm-prefix", default="arm-none-eabi-")
    parser.add_argument("--no-leak-check", action="store_true",
                        help="Disable only LeakSanitizer where /proc/ptrace restrictions prevent it.")
    args = parser.parse_args()
    release = ROOT / "dist"
    logs = release / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    if args.no_leak_check:
        environment["ASAN_OPTIONS"] = environment.get("ASAN_OPTIONS", "") + ":detect_leaks=0"

    def run(command: list[str], log_name: str | None = None, env=None) -> str:
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if log_name:
            (logs / log_name).write_text(result.stdout, encoding="utf-8")
        if result.returncode:
            print(result.stdout)
            raise SystemExit(f"FAILED ({result.returncode}): {' '.join(command)}")
        return result.stdout

    run(["make", "clean"], "clean.txt")
    host_output = run(["make", "test"], "host_tests.txt")
    sanitizer_output = run(["make", "test-sanitize"], "asan_ubsan.txt", environment)
    arm_output = run(["make", "arm", f"ARM_PREFIX={args.arm_prefix}", "-j4"], "arm_build.txt")
    run(["make", "build/timing_report"], "timing_compile.txt")
    timing = run(["./build/timing_report"])
    compiled_constants = json.loads(run(["./build/timing_report", "--json"]))
    (release / "timing.md").write_text(timing, encoding="utf-8")

    gcc_version = run([args.arm_prefix + "gcc", "--version"]).splitlines()[0]
    size_output = run([args.arm_prefix + "size", "-A", "build/light_block_A5.elf"], "elf_sections.txt")
    elf_header = run([args.arm_prefix + "readelf", "-h", "-A", "build/light_block_A5.elf"], "elf_attributes.txt")
    if run([args.arm_prefix + "nm", "-u", "build/light_block_A5.elf"], "undefined_symbols.txt").strip():
        raise SystemExit("Unexpected undefined ELF symbols")
    nm_output = run([args.arm_prefix + "nm", "--defined-only", "build/light_block_A5.elf"], "symbols.txt")
    symbols = {}
    types = {}
    for line in nm_output.splitlines():
        parts = line.split()
        if len(parts) == 3:
            try:
                symbols[parts[2]] = int(parts[0], 16)
                types[parts[2]] = parts[1]
            except ValueError:
                pass

    binary = (ROOT / "build/light_block_A5.bin").read_bytes()
    stack, reset = struct.unpack_from("<II", binary)
    if stack != 0x20002000 or not (0x08000000 <= (reset & ~1) < 0x08010000) or not (reset & 1):
        raise SystemExit("Unexpected startup vector/range")
    header = (ROOT / "vendor/STM32CubeG0/Drivers/CMSIS/Device/ST/STM32G0xx/Include/stm32g031xx.h").read_text()
    vectors = {"NMI_Handler": 2, "HardFault_Handler": 3, "SysTick_Handler": 15}
    for irq, handler in [("EXTI4_15_IRQn", "EXTI4_15_IRQHandler"),
                         ("DMA1_Channel1_IRQn", "DMA1_Channel1_IRQHandler")]:
        match = re.search(r"\b" + irq + r"\s*=\s*(\d+)", header)
        if not match:
            raise SystemExit(f"Missing device IRQ {irq}")
        vectors[handler] = 16 + int(match.group(1))
    vector_report = {}
    for handler, index in vectors.items():
        actual = struct.unpack_from("<I", binary, index * 4)[0]
        expected = symbols[handler] | 1
        if actual != expected or types[handler] != "T":
            raise SystemExit(f"Incorrect/weak interrupt vector {handler}")
        vector_report[handler] = {"vector_index": index, "address": f"0x{actual:08x}", "strong_definition": True}
    if "ARM" not in elf_header or "Cortex-M0+" not in elf_header:
        # GNU readelf may use the architecture name rather than the part family.
        if "v6S-M" not in elf_header:
            raise SystemExit("Unexpected ELF architecture")

    artifacts = []
    for extension in ["elf", "hex", "bin", "map"]:
        src = ROOT / "build" / f"light_block_A5.{extension}"
        dst = release / src.name
        shutil.copyfile(src, dst)
        artifacts.append({"file": dst.name, "bytes": dst.stat().st_size, "sha256": sha(dst)})

    licenses_dir = release / "licenses"
    licenses_dir.mkdir(exist_ok=True)
    license_paths = {
        "STM32CubeG0-component-licenses.md": "vendor/STM32CubeG0/LICENSE.md",
        "CMSIS-Core-Apache-2.0.txt": "vendor/STM32CubeG0/Drivers/CMSIS/LICENSE.txt",
        "CMSIS-Device-Apache-2.0.txt": "vendor/STM32CubeG0/Drivers/CMSIS/Device/ST/STM32G0xx/LICENSE.md",
        "STM32-HAL-BSD-3-Clause.txt": "vendor/STM32CubeG0/Drivers/STM32G0xx_HAL_Driver/LICENSE.md",
        "ARM-GCC-package-copyright.txt": "vendor/licenses/ARM-GCC-package-copyright.txt",
        "GCC-GPL-3.0.txt": "vendor/licenses/GCC-GPL-3.0.txt",
        "GCC-Runtime-Library-Exception-3.1.txt": "vendor/licenses/GCC-Runtime-Library-Exception-3.1.txt",
        "GCC-license-provenance.md": "vendor/licenses/README.md"
    }
    license_report = []
    for name, relative in license_paths.items():
        source = ROOT / relative
        if not source.exists():
            raise SystemExit(f"Missing license source: {relative}")
        target = licenses_dir / name
        shutil.copyfile(source, target)
        license_report.append({"file": f"licenses/{name}", "sha256": sha(target)})

    # Tree digest excludes derived files and repository metadata. The per-file
    # manifest permits verification after unpacking without requiring git.
    input_files = []
    for folder in ["include", "src", "platform", "tests", "tools", "vendor"]:
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and not any(part.startswith(".") for part in path.relative_to(ROOT).parts):
                input_files.append(path)
    input_files += [ROOT / "Makefile", ROOT / "sources.json"]
    lines = [f"{sha(path)}  {path.relative_to(ROOT).as_posix()}" for path in sorted(set(input_files))]
    manifest = "\n".join(lines) + "\n"
    (release / "source_files.sha256").write_text(manifest, encoding="utf-8")

    assertions = int(re.search(r"PASS total assertions: (\d+)", host_output).group(1))
    if f"PASS total assertions: {assertions}" not in sanitizer_output:
        raise SystemExit("Host and sanitizer test suites differ")
    static_ram = symbols["_end"] - 0x20000000
    evidence = {
        "revision": "A5",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "ARM build and host verification passed; no flashing or hardware validation",
        "mcu": "STM32G031G8U6TR / UFQFPN28 / Cortex-M0+ / 64KiB flash / 8KiB SRAM",
        "board_adc_revision": "A5 U7 follower, R24=330ohm, R25=1kohm; incompatible with A4.1 ADC",
        "compiler": gcc_version,
        "sdk": json.loads((ROOT / "vendor/pins.json").read_text()),
        "tests": {
            "host": "PASS", "assertions": assertions, "suites": 7,
            "address_sanitizer": "PASS", "undefined_behavior_sanitizer": "PASS",
            "leak_sanitizer": "NOT RUN: explicit container/process-inspection limitation" if args.no_leak_check else "enabled",
            "timing_sweep_ppm": [-30000,30000], "timing_sweep_points":60001,
            "random_sequences_start_active":250,
            "arm_compile_link": "PASS", "undefined_symbols":0,
            "interrupt_vectors":vector_report,
            "hardware_tested":False, "flashed":False
        },
        "memory": {
            "flash_payload_bytes": len(binary), "flash_limit_bytes":65536,
            "static_ram_and_alignment_bytes":static_ram,
            "reserved_stack_bytes":2048,
            "static_plus_stack_bytes":static_ram+2048,
            "ram_limit_bytes":8192,
            "initial_stack_pointer":f"0x{stack:08x}", "reset_vector":f"0x{reset:08x}",
            "note":"Linker reservation only; runtime stack high-water not measured."
        },
        "io": {
            "mode_A":"PA2", "mode_B":"PA3", "switch_bits":{"01":"ON","11":"PROGRAM","10":"CV","00":"invalid/black"},
            "cv_adc":"PA0/ADC_IN0", "fault":"PA4 active-low, EXTI4_15 priority0",
            "enable":"PA5 HIGH enables NPN/active-low TPS2552-1 EN",
            "left":"PA6/AF1/TIM3_CH1", "right":"PA7/AF1/TIM3_CH2",
            "dma":"DMA1_Channel1, TIM3_UP,2-halfword burst CCR1/CCR2",
            "pixel_order":"GRB, MSB first,4 pixels per independent chain",
            "max_channel_code":compiled_constants["channel_cap"]
        },
        "timing": {
            **compiled_constants,
            "actual_report":"timing.md", "measured_on_hardware":False
        },
        "adc": {
            "transfer":"VADC=(100/133)*(VDD/2+CV/8)", "inverse":"CV=10.64*VADC-4*VDD",
            "factory_vref_cal_vdda_mv":3000, "sample_clock_hz_nominal":compiled_constants["timer_hz"]//4,
            "acquisition_cycles":160.5, "pairs_per_second_target":1000,
            "zero_gain_calibration":"nominal only; measured values not yet supplied"
        },
        "reset_policy": {
            "ordinary_startup":"selected mode after stabilization, only reset backup pair plus nonconflicting power-reset cause",
            "retained_armed_fault_or_partial_record":"inhibits all automatic enable",
            "warm_or_retained_domain_brownout":"stays off",
            "deep_supply_collapse":"backup loss can authorize a new attempt; indistinguishable from unplugging",
            "manual_switch_gesture":False, "automatic_retry_timer":False,
            "option_bytes_modified":False, "service_clear_command":False
        },
        "artistic_defaults":"provisional; not user-approved colors, animation, CV curve or deadband",
        "source_manifest":{"file":"source_files.sha256","files":len(lines),"sha256":sha(release/"source_files.sha256")},
        "artifacts":artifacts,
        "licenses":license_report,
        "sources_file":"../sources.json",
        "remaining_hardware_gates":["Pin/switch polarity and SWD reset", "Both LED chain waveforms and incoming lot", "Fault/BOR/full-collapse recovery", "A5 CV transfer/calibration/off-state cases", "Power-up current/temperature and stack/watchdog"]
    }
    (release / "verification.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    release_readme = f"""# A5 firmware build — prototype only

Built for STM32G031G8U6TR and the A5 U7-buffered,330 Ω /1 kΩ divided CV input. Do not use this binary with the A4.1 CV circuit.

Actual ARM compilation and host verification passed. **No device was flashed and no hardware test was performed.** Colors, animation and CV response are configurable prototype defaults.

Compiler: {gcc_version}

Host tests: {assertions:,} assertions across seven suites; ASan and UBSan passed. LeakSanitizer status: {evidence['tests']['leak_sanitizer']}.

Flash: {len(binary):,} bytes. Static RAM including alignment: {static_ram:,} bytes, plus2,048 bytes stack reservation.

Files: ELF for debugging, Intel HEX or BIN for a suitable programming tool, map for layout, verification.json for hashes/provenance, timing.md for calculations, logs/ for exact checks, licenses/ for third-party terms. BIN load address:0x08000000.

The retained backup marker blocks warm resets and retained-domain brownouts. Complete supply collapse can erase the marker and permit a new attempt. There is no fault retry timer or hidden switch arming gesture. Read ../README.md and ../docs/reset_policy.md before first powered testing.

Copy all license files with any binary distribution.
"""
    (release / "README.md").write_text(release_readme, encoding="utf-8")
    print(json.dumps({"status":"PASS", "assertions":assertions, "flash_bytes":len(binary),
                      "static_ram_plus_stack_bytes":static_ram+2048,
                      "hardware_tested":False,"dist":str(release)}, indent=2))

if __name__ == "__main__":
    main()
