"""Rebuild the A5 selection ledger from the frozen, dated observations.

No network access. Stock is not reserved and prices are not quotations.
This is a design-selection BOM, not an assembler BOM/CPL release.

Run `python build_procurement_rows.py --check` to verify without writing.
To revise the selection, edit the frozen input deliberately, then regenerate.
Historical A4 builders and prices are not current inputs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "procurement_inputs_A5.json"
DEFAULT_OUTPUT = ROOT / "procurement_rows.json"


def unit_price(row: dict, quantity: int) -> Decimal:
    if quantity < 1:
        raise ValueError("A price comparison requires a positive fitted quantity")
    for tier in reversed(row["tiers"]):
        if quantity >= tier["min_qty"]:
            maximum = tier.get("max_qty")
            if maximum is not None and quantity > maximum:
                raise ValueError(f"Unpriced quantity {quantity} for {row['id']}")
            return Decimal(str(tier["unit_price_usd"]))
    raise ValueError(f"No price for {row['id']} at {quantity}")


def validate_row(row: dict, root: Path) -> None:
    qty = row["qty_per_module"]
    if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
        raise ValueError(f"Invalid fitted quantity: {row['id']}")
    tiers = row.get("tiers", [])
    previous_max = 0
    for index, tier in enumerate(tiers):
        minimum, maximum = tier["min_qty"], tier.get("max_qty")
        if previous_max is None or minimum != previous_max + 1:
            raise ValueError(f"Missing or overlapping price tier: {row['id']}")
        if maximum is not None and maximum < minimum:
            raise ValueError(f"Invalid price-tier range: {row['id']}")
        if Decimal(str(tier["unit_price_usd"])) <= 0:
            raise ValueError(f"Invalid unit price: {row['id']}")
        if index == len(tiers) - 1 and maximum is not None:
            raise ValueError(f"Last price tier is bounded: {row['id']}")
        previous_max = maximum
    if row.get("c_code") and not tiers:
        raise ValueError(f"Missing primary component price: {row['id']}")
    for key in ("stock", "prepurchase_qty"):
        value = row.get(key)
        if value is not None and (not isinstance(value, int) or value < 0):
            raise ValueError(f"Invalid {key}: {row['id']}")
    snapshot = row.get("snapshot")
    if snapshot:
        path = (root / snapshot).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f"Missing or external evidence file: {snapshot}")
        expected = row.get("snapshot_sha256")
        if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Evidence hash mismatch: {snapshot}")


def build(input_path: Path = DEFAULT_INPUT) -> dict:
    data = copy.deepcopy(json.loads(input_path.read_text(encoding="utf-8")))
    rows = data["components"]
    codes = [r["c_code"] for r in rows]
    if len(set(codes)) != len(codes):
        raise ValueError("Duplicate primary C code")
    for row in rows + data["external_items"] + data.get("alternative_components", []):
        validate_row(row, input_path.parent)
    external = {r["id"]: r for r in data["external_items"]}
    costs = {}
    for count in (1, 10, 100):
        categories: dict[str, Decimal] = {}
        for row in rows:
            cost = unit_price(row, count * row["qty_per_module"]) * row["qty_per_module"]
            categories[row["category"]] = categories.get(row["category"], Decimal(0)) + cost
        led = external["EXT-01"]
        power = external["EXT-02"]
        costs[str(count)] = {
            "fitted_component_cost_per_module_usd": float(sum(categories.values())),
            "categories_per_module_usd": {k: float(v) for k, v in categories.items()},
            "LED_external_cables_per_module_usd": float(
                unit_price(led, count * led["qty_per_module"]) * led["qty_per_module"]
            ),
            "power_external_cable_per_module_usd": float(
                unit_price(power, count * power["qty_per_module"]) * power["qty_per_module"]
            ) if power["tiers"] else None,
            "excludes": "Attrition, pre-purchase minimums, board-job splitting, PCBs, assembly, fixtures, X-ray, programming, other cables, mechanical parts, shipping and taxes.",
        }
    data["cost_checks"] = costs
    data["summary"] = {
        "unique_jlc_mpn_count": len(rows),
        "fitted_parts_per_module": sum(r["qty_per_module"] for r in rows),
        "all_stock_cover_100_fitted_modules": all(r["stock"] >= 100 * r["qty_per_module"] for r in rows),
        "all_prepurchase_cover_100_fitted_modules": all(r["prepurchase_qty"] >= 100 * r["qty_per_module"] for r in rows),
        "least_stock_coverage_code": min(rows, key=lambda r: r["stock"] / r["qty_per_module"])["c_code"],
        "all_quantities_before_attrition": True,
        "release_status": data["summary"]["release_status"],
    }
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = build(args.input.resolve())
    if args.check:
        actual = json.loads(args.output.read_text(encoding="utf-8"))
        if data != actual:
            raise SystemExit("FAIL: procurement_rows.json differs from regenerated inputs")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "revision": data["revision"],
                      "mode": "check" if args.check else "write",
                      "summary": data["summary"], "cost_checks": data["cost_checks"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
