# Native gate infrastructure fixtures

Test infrastructure for `scripts/native_gate/`. **Not an A7 board, not an A5 revision, not a manufacturing file.**

- `led_leaf_zoned/` — the immutable A5 LED leaf's routing plus one filled GND zone on F.Cu, built by
  `scripts/native_gate/make_fixture.py` inside the pinned KiCad 10.0.8 image into an empty directory, then committed.
  `provenance.json` records the A5 source hashes and outputs. Regeneration is not byte-identical (KiCad assigns new
  UUIDs), so the committed board is the fixture authority and `profile.lock.json` pins it.
- `led_leaf_zoned/placement.json` — derived by `authority.py export-placement` from fresh native facts; the gate
  re-checks it as its regeneration-preservation step.
- `profile.json` / `profile.lock.json` — the infrastructure gate profile and its generated input lock.
- `a5_identity_delta.json` — identity record: a fresh export of the A5 controller schematic must equal the
  historical A5 netlist with no delta.
