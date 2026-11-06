# Provenance of `engineering/a5/`

`engineering/a5/` is an **immutable, byte-for-byte import** of the Light Block A5 engineering checkpoint. Nothing in that directory was edited by the repository bootstrap. New wrappers, checks, site generators, documentation and CI live outside it.

| File | What it is |
| --- | --- |
| `seed-manifest.json` | Size + SHA-256 of all 786 imported files, their repository paths, and the five explicit omissions |
| `source-recovery-verification.json` | Recovery receipt for the original `light_block_A5_design_package.zip` (ZIP CRC + 790 manifest hashes checked at handoff) |
| `repository-evidence.json` | Repository/reference revisions and package versions inspected when the handoff was prepared (2026-11-07 JST) |
| `plan-review.json` | Independent review of the handoff plan (no implementation claims) |
| `handoff-README.md` | The handoff bundle's README, unchanged |

## Original archive

- Name: `light_block_A5_design_package.zip`
- Size: 67,187,342 bytes
- SHA-256: `94448c56521e868280076c0444c7d60339d75c6b128e6b4fde00e2b36533cf24`
- 791 ZIP entries; 790 entries in its own manifest (`engineering/a5/package_manifest.json`)

## Seed import

- 786 files, 83,093,114 bytes, copied unchanged from the verified archive; only the directory prefix changed to `engineering/a5/`.
- The handoff ZIP itself is **not** committed (see `.gitignore`).

## Five omitted paths

| Original path | Bytes | Why omitted | How to restore |
| --- | ---: | --- | --- |
| `mechanical/exports/2hp/light_block_A5_2hp_assembled.json` | 28,277,450 | Generated tessellation (bulk) | `mechanical/build_mechanical.py` (CadQuery 2.7) before `render_previews.py` |
| `mechanical/exports/2hp/light_block_A5_2hp_exploded.json` | 28,269,761 | Generated tessellation | same |
| `mechanical/exports/3hp/light_block_A5_3hp_assembled.json` | 28,149,402 | Generated tessellation | same |
| `mechanical/exports/3hp/light_block_A5_3hp_exploded.json` | 28,146,094 | Generated tessellation | same |
| `references/light_block_A3_design_package.zip` | 8,169,740 | Historical nested archive | From the original full A5 download (user-access only) |

The original `engineering/a5/package_manifest.json`, `verification_A5.json` and reports still describe the **full** archive and still list those five files. They are historical evidence and were intentionally **not** rewritten. Consequently `engineering/a5/build_package.py` (the full archival rebuild) cannot pass until the omitted files are regenerated/restored; it is not a CI gate.

## Verify

From the repository root (standard library only):

```sh
python3 scripts/verify_seed.py --manifest provenance/seed-manifest.json --repo .
```

This checks file identity only. It is not a hardware, firmware or manufacturing qualification.
