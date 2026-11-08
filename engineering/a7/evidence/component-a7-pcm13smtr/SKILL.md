---
name: component-a7-pcm13smtr
description: Resolve exact C&K PCM13SMTR (C221842, SMD) evidence for the Zudo LED Block A7 PCB-side ON / PGM / CV mode setting switch. Use whenever PCM13SMTR, C221842, its switch positions, pins, footprint, actuator, sourcing, substitution or bring-up are relevant.
---

# C&K PCM13SMTR (C221842) — A7 staging bundle

Route here only for the exact identity C&K PCM13SMTR / C221842. Not for the A5 front toggle (Dailywell
1MS3T1B1M2QES-5) or the Nidec CSS-1310TB alternate.

Selected because the manufacturer prints a per-position terminal table (POS.1 1-3, POS.2 2-3, POS.3 3-4), so
leaving terminal 2 open gives the ON-OFF-ON behaviour the MODE_A/MODE_B encoding needs. Open: JLC stock was 0 on
2026-11-08. Staged under `engineering/a7/evidence/` until the #9 catalog migration lands.
