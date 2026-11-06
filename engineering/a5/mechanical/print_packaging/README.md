# H2D PLA fit-check projects

These are **unsliced dimensional/assembly fit-check projects** for the saved Bambu Lab H2D 0.6 mm template. The finished parts are intended for PETG. The bundled template contains PLA profiles, and its settings are preserved byte for byte. A matching PETG process and physical validation are still needed.

Each project contains the seven parts listed in its final CAD `print_manifest.json`. Their print orientations come from the CAD-exported STL files. The packager applies no additional rotation; the Bambu helper normalizes each part to Z=0 and places it on one plate with a 10 mm margin and 8 mm bounding-box gap. All objects use saved filament slot 1 (`Bambu PLA Basic`, saved color `#161616`). This records the saved profile, not the material currently loaded in a printer. Optical behavior is not qualified by these fit-check files.

## Reproduce

Python 3.10 or newer is sufficient; the packaging tools use only the standard library. From this directory:

```bash
python build_fit_check_projects.py --variant 2hp --revision r02
python build_fit_check_projects.py --variant 3hp --revision r02
```

Choose a new revision because existing projects are preserved. Geometry changes belong in `../build_mechanical.py`; regenerate its CAD/STL/STEP exports first. The packager reads only named entries in `../exports/<variant>/printable/print_manifest.json`, so unrelated exports cannot silently enter a plate.

The helper and original empty template are retained under `helpers/` and `assets/`. Their exact identities, the CAD generator, input STL/STEP files, generated mesh JSONs, manifest and output project are recorded in the per-variant packaging and validation records. Rebuilding preserves settings and geometry; ZIP dates and helper-generated identifiers need not be byte-identical.

## Validation scope

Near-identical STL vertices are welded within **1e-5 mm Euclidean distance**, retaining an original representative coordinate. No CAD/STL/STEP source is modified, and no triangle is removed or reversed. Closed edges, opposite winding, positive signed volume, and a single-cycle surface link at every vertex are required. The actual written 3MF archive is then read back and checked for relationships, object membership, bed bounds, non-overlapping object rectangles, Z=0 contact, no toolpaths, and unchanged global settings.

The mesh checks do not establish absence of self-intersections, minimum printable walls, support needs, brim clearance, physical fit or material suitability. Bambu Studio was not available in this environment, so these projects have not been loaded or sliced in Studio. No job has been sent to a printer.

## Harness integration status

The final `../verification_summary.json` rejects the saved flexible cable/ribbon routing scenarios. Each variant has **16 conditional interferences**. Sampled minimum bend radii are approximately **1.07–1.53 mm** for controller-to-leaf wires, **0.20–0.28 mm** for the leaf bridge, and **1.05 mm** for the power wires. Complete harness routing is unresolved and installed assembly fit remains unapproved. Only the retained rigid-part CAD cleared the modeled interference checks.

The 3MF projects contain seven rigid printable parts per variant. Their mesh/settings/layout checks retain the scope described above; a complete routed harness still needs redesign and validation. The projects remain unchanged, unsliced PLA fit checks.
