#!/usr/bin/env python3
"""Package final CAD exports as unsliced H2D 0.6 PLA fit-check projects.

Python 3.10+, standard library only. Never modifies CAD/STL/STEP inputs or the
saved template. Near-identical STL vertices may share an index within 1e-5 mm;
no triangles are deleted, reoriented, or otherwise repaired by this script.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
MECHANICAL = HERE.parent
PROJECT = MECHANICAL.parent
TEMPLATE = HERE / "assets" / "h2d-empty.3mf"
HELPER = HERE / "helpers" / "bambu_3mf.py"
TOLERANCE_MM = 1e-5
EXPECTED_SETTINGS_SHA256 = "99b34023dcf3d8142abb119f426ca54d499a4d07026c7e406e2b062147c7a356"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def module_from_file(path):
    spec = importlib.util.spec_from_file_location("bambu_project_helper", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_stl_points(path):
    raw = path.read_bytes()
    if len(raw) >= 84 and len(raw) == 84 + 50 * struct.unpack_from("<I", raw, 80)[0]:
        points = []
        for i in range(struct.unpack_from("<I", raw, 80)[0]):
            record = struct.unpack_from("<12fH", raw, 84 + i * 50)
            points.extend(tuple(record[j:j + 3]) for j in (3, 6, 9))
    else:
        text = raw.decode("ascii")
        points = [tuple(float(v) for v in m.groups()) for m in
                  re.finditer(r"\bvertex\s+(\S+)\s+(\S+)\s+(\S+)", text)]
    if not points or len(points) % 3 or not all(math.isfinite(v) for p in points for v in p):
        raise ValueError(f"Invalid finite triangle vertices in {path}")
    return points


def weld_vertices(points):
    """Deterministic distance-limited weld, retaining original coordinates."""
    cells = defaultdict(list)
    exact = {}
    vertices, indices = [], []
    movement = 0.0
    for point in points:
        if point in exact:
            indices.append(exact[point])
            continue
        cell = tuple(math.floor(v / TOLERANCE_MM) for v in point)
        choices = []
        for delta in itertools.product((-1, 0, 1), repeat=3):
            adjacent = tuple(cell[i] + delta[i] for i in range(3))
            for index in cells.get(adjacent, ()):
                distance2 = sum((point[i] - vertices[index][i]) ** 2 for i in range(3))
                if distance2 <= TOLERANCE_MM ** 2:
                    choices.append((distance2, index))
        if choices:
            distance2, index = min(choices)
            movement = max(movement, math.sqrt(distance2))
        else:
            index = len(vertices)
            vertices.append(point)
            cells[cell].append(index)
        exact[point] = index
        indices.append(index)
    triangles = [indices[i:i + 3] for i in range(0, len(indices), 3)]
    return vertices, triangles, {
        "tolerance_mm": TOLERANCE_MM,
        "method": "Nearest existing vertex within Euclidean tolerance; retains original representative coordinates",
        "input_triangle_vertices": len(points),
        "input_exact_unique_vertices": len(exact),
        "output_vertices": len(vertices),
        "merged_unique_vertices": len(exact) - len(vertices),
        "maximum_vertex_displacement_mm": movement,
        "triangles_removed": 0,
        "triangles_reversed": 0,
    }


def check_vertex_links(vertices, triangles):
    """Each closed two-manifold vertex must have a single cycle as its link."""
    links = [defaultdict(set) for _ in vertices]
    for a, b, c in triangles:
        for center, u, v in ((a, b, c), (b, c, a), (c, a, b)):
            links[center][u].add(v)
            links[center][v].add(u)
    for index, link in enumerate(links):
        if not link or any(len(neighbors) != 2 for neighbors in link.values()):
            raise ValueError(f"Vertex {index} has a non-cycle link; repair the CAD export")
        unseen = set(link)
        todo = [next(iter(unseen))]
        while todo:
            item = todo.pop()
            if item not in unseen:
                continue
            unseen.remove(item)
            todo.extend(link[item] & unseen)
        if unseen:
            raise ValueError(f"Vertex {index} has disconnected surface fans; repair the CAD export")
    return {"closed_vertex_links_checked": len(links), "point_only_nonmanifold_vertices": 0}


def package_variant(variant, revision, helper, template_data, studio):
    source_dir = MECHANICAL / "exports" / variant / "printable"
    source_manifest = source_dir / "print_manifest.json"
    parts = json.loads(source_manifest.read_text())
    if len(parts) != 7 or len({p["name"] for p in parts}) != 7:
        raise ValueError("The final print manifest must contain seven distinct parts")
    output_dir = MECHANICAL / "exports" / variant
    stem = f"light_block_A5_{variant}_PLA_fit_check_{revision}"
    target = output_dir / (stem + ".3mf")
    validation_file = output_dir / (stem + ".validation.json")
    if target.exists() or validation_file.exists():
        raise FileExistsError(f"Use a new revision; output already exists: {target}")
    work = HERE / variant / revision
    work.mkdir(parents=True, exist_ok=True)
    source_hashes = {str(source_manifest.relative_to(PROJECT)): digest(source_manifest),
                     "mechanical/build_mechanical.py": digest(MECHANICAL / "build_mechanical.py")}
    objects, mesh_reports = [], []
    for part in parts:
        if not part.get("valid") or part.get("solids") != 1:
            raise ValueError(f"CAD manifest does not report one valid solid: {part['name']}")
        stl = source_dir / part["stl"]
        step = source_dir / part["step"]
        source_hashes[str(stl.relative_to(PROJECT))] = digest(stl)
        source_hashes[str(step.relative_to(PROJECT))] = digest(step)
        points = read_stl_points(stl)
        vertices, triangles, weld = weld_vertices(points)
        vertices, triangles, stats = helper.validate_mesh(vertices, triangles, part["name"])
        vertex_topology = check_vertex_links(vertices, triangles)
        mesh_file = work / (part["name"] + ".mesh.json")
        write_json(mesh_file, {"vertices": vertices, "triangles": triangles})
        source_hashes[str(mesh_file.relative_to(PROJECT))] = digest(mesh_file)
        bounds = helper.bbox(vertices)
        mesh_reports.append({"name": part["name"], "source_stl": str(stl.relative_to(PROJECT)),
                             "source_stl_sha256": digest(stl), "mesh_sha256": digest(mesh_file),
                             "weld": weld, "edge_manifold_and_winding": "PASS", **vertex_topology,
                             **stats, "source_bounds_mm": bounds,
                             "dimensions_mm": [bounds[1][i] - bounds[0][i] for i in range(3)],
                             "CAD_export_rotation_already_applied": part.get("rotation"),
                             "packager_rotation": "none; helper translates minima to X=Y=Z=0 before bed placement"})
        objects.append({"name": variant + "_" + part["name"], "mesh": mesh_file.name, "filament": 1})
    manifest = {"schema_version": 1, "title": f"Light Block A5 {variant} PLA fit-check only",
                "description": "PETG-intended geometry. Preserved H2D 0.6 mm PLA settings. Unsliced dimensional/assembly fit-check; PETG process, optical performance and final module fit are not qualified.",
                "margin_mm": 10, "gap_mm": 8, "objects": objects}
    manifest_file = work / "parts.manifest.json"
    write_json(manifest_file, manifest)
    with tempfile.TemporaryDirectory(prefix="light-block-3mf-") as temp:
        staged = Path(temp) / target.name
        created = helper.create(TEMPLATE, manifest_file, staged)
        validation = helper.validate_project(helper.read_archive(staged), template_data, layout=True)
        if not validation["settings_bytes_unchanged"] or validation["settings_changes"]:
            raise ValueError("Saved global settings changed")
        if validation["contains_toolpaths"] or len(validation["build_items"]) != len(parts):
            raise ValueError("Unexpected toolpaths or build-item count")
        if any(abs(item["bounds_mm"][0][2]) > 1e-7 for item in validation["build_items"]):
            raise ValueError("A part does not contact the bed at Z=0")
        for input_path, original_hash in source_hashes.items():
            if digest(PROJECT / input_path) != original_hash:
                raise ValueError(f"Input changed during packaging: {input_path}")
        shutil.copyfile(staged, target)
    source_hashes.update({str(TEMPLATE.relative_to(PROJECT)): digest(TEMPLATE),
                          str(HELPER.relative_to(PROJECT)): digest(HELPER),
                          str(Path(__file__).relative_to(PROJECT)): digest(Path(__file__)),
                          str(manifest_file.relative_to(PROJECT)): digest(manifest_file)})
    source_record = {"schema_version": 1, "variant": variant, "revision": revision,
                     "paths_relative_to": "light_block_A5 project root", "input_sha256": source_hashes,
                     "intended_material": "PETG", "saved_material": "PLA",
                     "filament_slot": 1, "source_geometry_modified": False,
                     "weld_tolerance_mm": TOLERANCE_MM,
                     "output": str(target.relative_to(PROJECT)), "output_sha256": digest(target)}
    source_record_file = work / "source_manifest.json"
    write_json(source_record_file, source_record)
    report = {"status": "UNSLICED_PLA_FIT_CHECK_STRUCTURAL_CHECKS_PASSED",
              "created_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "variant": variant, "revision": revision,
              "output": str(target.relative_to(PROJECT)), "output_bytes": target.stat().st_size,
              "output_sha256": digest(target), "part_count": len(parts),
              "printer": "Bambu Lab H2D", "nozzle_diameter_mm": [0.6, 0.6],
              "saved_material": "PLA", "intended_part_material": "PETG",
              "filament_slot": 1, "saved_slot_1_profile": "Bambu PLA Basic @BBL H2D 0.6 nozzle",
              "saved_slot_1_color": "#161616", "physical_loaded_material_verified": False,
              "template_sha256": digest(TEMPLATE), "settings_sha256": EXPECTED_SETTINGS_SHA256,
              "all_saved_global_settings_bytes_unchanged": True, "object_process_overrides": {},
              "input_geometry_modified": False, "contains_toolpaths": False,
              "source_manifest": str(source_record_file.relative_to(PROJECT)),
              "source_manifest_sha256": digest(source_record_file), "meshes": mesh_reports,
              "project_validation": validation, "removed_stale_template_cache_members": created["removed_cached_members"],
              "studio_discovery": studio, "studio_load_or_slice_performed": False,
              "limitations": ["No Bambu Studio load/slice check; no toolpaths or printer job",
                              "No PETG preset qualification; saved PLA settings preserved",
                              "No self-intersection, minimum-wall, support/brim or optical-performance qualification",
                              "CAD orientation retained; seven objects normalized to Z=0",
                              "Physical dimensional fit, thermal behavior and material suitability remain untested"]}
    write_json(validation_file, report)
    return {"variant": variant, "revision": revision, "output": str(target.relative_to(PROJECT)),
            "output_sha256": digest(target), "validation": str(validation_file.relative_to(PROJECT)),
            "validation_sha256": digest(validation_file), "part_count": len(parts),
            "status": report["status"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["2hp", "3hp"], action="append")
    parser.add_argument("--revision", default="r01")
    args = parser.parse_args()
    if not re.fullmatch(r"r[0-9]{2,}", args.revision):
        parser.error("Use a revision such as r01 or r02")
    helper = module_from_file(HELPER)
    template_data = helper.read_archive(TEMPLATE)
    if hashlib.sha256(template_data[helper.SETTINGS]).hexdigest() != EXPECTED_SETTINGS_SHA256:
        raise ValueError("The saved H2D template settings are not the inspected baseline")
    studio_result = subprocess.run([sys.executable, str(HERE / "helpers" / "studio_cli.py")],
                                   check=False, capture_output=True, text=True)
    studio = json.loads(studio_result.stdout)
    result = [package_variant(v, args.revision, helper, template_data, studio)
              for v in (args.variant or ["2hp", "3hp"])]
    index_file = HERE / "validation_index.json"
    index = json.loads(index_file.read_text()) if index_file.exists() else {"projects": {}}
    for item in result:
        index["projects"][item["variant"] + "_" + item["revision"]] = item
    write_json(index_file, index)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
