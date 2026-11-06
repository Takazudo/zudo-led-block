# A5 timing derived from the compiled lb_config.h constants

Timer: 60000000 Hz nominal, period 78 ticks; +/-3% envelope 58200000..61800000 Hz.

| Signal | Ticks | Nominal ns | Minimum ns (+3% clock) | Maximum ns (-3% clock) | Manufacturer ns |
|---|---:|---:|---:|---:|---:|
| T0H | 21 | 350.000 | 339.806 | 360.825 | 220..380 |
| T0L | 57 | 950.000 | 922.330 | 979.381 | 580..1000 |
| T1H | 57 | 950.000 | 922.330 | 979.381 | 580..1000 |
| T1L | 21 | 350.000 | 339.806 | 360.825 | 220..420 |
| Bit cell | 78 | 1300.000 | 1262.136 | 1340.206 | >=1250 |

Two independent 4-pixel chains, GRB MSB first; 96 data cells per chain.
DMA: 708 interleaved 16-bit values, 1416 bytes, 2 lead + 96 data + 256 zero-tail slots.
Tail complete before immediate DMA-stop callback, conservatively excluding two pipeline cells: 254 cells; nominal 330.200 us, minimum 320.583 us. Requirement: >=280 us.

This calculation covers oscillator frequency tolerance; it does not measure pad/translator/LED waveform, DMA timing under real bus contention or PLL jitter. Scope verification on both chains and the exact LED lot remains required.
