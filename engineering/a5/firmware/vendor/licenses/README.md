# GCC runtime license provenance

The ARM firmware links integer-arithmetic routines from the GNU GCC13.2.1 `libgcc` supplied by the workspace's `gcc-arm-none-eabi` package. It uses no newlib functions and distributes no compiler executable.

GCC runtime code is covered by GPL version3 (or later) with the GCC Runtime Library Exception version3.1. The complete GPL3 and exception texts are included. The texts were retrieved on2026-11-06 from the GCC source mirror's GCC13.2.0 release, where these license versions are unchanged:

- [COPYING3](https://github.com/gcc-mirror/gcc/blob/releases/gcc-13.2.0/COPYING3)
- [COPYING.RUNTIME](https://github.com/gcc-mirror/gcc/blob/releases/gcc-13.2.0/COPYING.RUNTIME)

The exception describes the conditions for distributing target code containing eligible runtime-library code together with independent modules. Keep the complete terms with binary distributions.

`ARM-GCC-package-copyright.txt` is the Debian packaging copyright copied from the exact installed package. Its own text explicitly says it does not cover the compiler itself; it is included as packaging provenance, not substituted for the runtime license.

ST HAL is separately BSD-3-Clause; Arm CMSIS Core and ST CMSIS Device are Apache-2.0. Their full unmodified licenses are present in the SDK and copied into the release folder.
