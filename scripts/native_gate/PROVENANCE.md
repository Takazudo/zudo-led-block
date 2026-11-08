# Native gate provenance

Ported selectively from draft PR #14 (A6, branch `claude/project-thread-391rx3`, head
`7e96380be4fbea2bfcc4a5bd1d5721272a5a141f`). PR #14 and its branch are left intact; its A6
scaffold (board, manifest, A6 generator, routing records) is **not** imported.

| New file | Source at 7e96380 | SHA-256 of source | Kept | Changed |
|---|---|---|---|---|
| `evaluate.py` | `scripts/a6_native_eval.py` | `3e7ec0b1…f4b96` | all fail-closed evaluation (exit codes, timeouts, truncated logs, stage hashes, ERC/DRC keys/version/severities/ignored set, residual matching, parity classes and counts, independent pad parity, pcbnew connectivity, refill topology, expected-failure control, tool versions) | docstrings only |
| `inner.py` | `scripts/a6_native_inner.py` | `61ac23b8…eb56` | ERC/netlist/DRC runs with per-op deadlines and log caps, board facts and geometry digest, canonical zone-fill fingerprint, refill on a copy | `wrong_connection` pad/target come from the profile (was hardcoded `R14.2`→`DATA_R`); `route_break` and `fill_shift` raise when there is no routed copper / no filled zone instead of silently doing nothing; `route_break` uses `Delete`; each mutation control runs in its own interpreter (the in-process sequence crashed pcbnew with exit 139 here) |
| `runner.py` | `scripts/a6_native_verify.py` | `f762696e…42f3` | receipt-first, A5 integrity before/after, staging of hash-pinned regular files only, owned container with resource limits and no network, label-scoped cleanup with receipts and `FakeDocker`, synthetic controls, evidence allowlist/cap, current-head identity | A6 paths → a JSON profile + generated lock; A5 netlist identity (`netlist_unchanged`) → behavioral assertions (`interface.py`) + authorized delta (`delta.py`); a mutation control counts only if the unmutated design passed (an unrouted board can no longer make a route-break control look meaningful); `infrastructure` profiles can only reach `INFRASTRUCTURE_PASS`; a `revision` profile without a candidate stops with `NO_CANDIDATE` |
| `../tests/test_native_eval.py`, `../tests/test_native_cleanup.py` | `scripts/tests/test_a6_native_eval.py`, `test_a6_native_cleanup.py` | — | all cases | imports |

New in this port: `interface.py`, `delta.py`, `authority.py`, `make_fixture.py`, `../tests/test_native_behavior.py`,
the fixture under `scripts/tests/fixtures/native/`, and the A7 profile/records under `engineering/a7/verification/`.

Not ported: `scripts/a6_controller.py` (A6 board/schematic derivation), `scripts/a6_site.py`, the A6 expectations' H1/J3
courtyard residual and the A6 `.claude/settings.json` Freerouting allowance.
