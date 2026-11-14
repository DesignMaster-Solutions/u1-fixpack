#!/usr/bin/env python3
"""Turn a preset that inherits from a "Project-inside preset" into a full, standalone preset.

Snapmaker Orca saves a user preset as the few keys that differ from its parent plus
"inherits": "<parent name>". When the parent only lives inside a .3mf, the saved preset
is unusable in any other project (Snapmaker/OrcaSlicer#1207). This resolves the chain
from the presets embedded in the .3mf and writes one JSON with every key and no parent.

    python3 flatten_preset.py project.3mf                      # lists the presets inside
    python3 flatten_preset.py project.3mf "Preset name"        # a preset stored in the 3mf
    python3 flatten_preset.py project.3mf saved_user_preset.json   # the partial file from AppData

Then in the slicer: File > Import > Import Configs, and pick the written file.
"""
import argparse
import json
import sys
import zipfile

# kept from the leaf so the parent's identity never overwrites it
ID_KEYS = ("name", "print_settings_id", "filament_settings_id", "printer_settings_id")


def embedded_presets(path):
    """name -> preset dict for every Metadata/*_settings_N.config in the 3mf."""
    out = {}
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if n.startswith("Metadata/") and "_settings_" in n and n.endswith(".config"):
                d = json.loads(z.read(n))
                if isinstance(d, dict) and d.get("name"):
                    out[d["name"]] = d
    return out


def project_printer(path):
    with zipfile.ZipFile(path) as z:
        try:
            return json.loads(z.read("Metadata/project_settings.config")).get("printer_settings_id")
        except KeyError:
            return None


def flatten(leaf, presets):
    chain, seen = [leaf], {leaf.get("name")}
    while chain[-1].get("inherits"):
        parent = chain[-1]["inherits"]
        if parent not in presets:
            raise KeyError(f'parent preset "{parent}" is not inside this 3mf; '
                           "pass the project the preset was first saved from")
        if parent in seen:
            raise ValueError(f'inheritance loop at "{parent}"')
        seen.add(parent)
        chain.append(presets[parent])
    full = {}
    for p in reversed(chain):  # root first, so the child wins
        full.update(p)
    for k in ID_KEYS:
        # a parent's own id (a string equal to its name) must not survive under the child's name
        if k not in leaf and isinstance(full.get(k), str):
            full[k] = leaf["name"]
    full["inherits"] = ""
    full["from"] = "User"
    return full


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", help=".3mf that holds the parent preset")
    ap.add_argument("preset", nargs="?", help="preset name inside the 3mf, or a saved preset .json")
    ap.add_argument("-o", "--out", help="output file (default: <preset name>.json)")
    ap.add_argument("--printer", action="append",
                    help="printer the preset is for; default is the project's printer. "
                         'Repeat for more than one, or pass "" to keep the parent\'s list')
    a = ap.parse_args(argv)

    presets = embedded_presets(a.project)
    if not a.preset:
        for name, d in presets.items():
            print(f'{name}   (inherits: {d.get("inherits") or "-"})')
        return 0
    if a.preset.lower().endswith(".json"):
        with open(a.preset, encoding="utf-8") as f:
            leaf = json.load(f)
    elif a.preset in presets:
        leaf = presets[a.preset]
    else:
        print(f'no preset named "{a.preset}" in {a.project}; run without a name to list them', file=sys.stderr)
        return 2
    try:
        full = flatten(leaf, presets)
    except (KeyError, ValueError) as e:
        print(e.args[0], file=sys.stderr)
        return 2

    # A converted parent often still lists the printers it came from (e.g. Bambu Lab X1),
    # and a standalone preset with that list is hidden on the U1.
    printers = a.printer if a.printer is not None else [project_printer(a.project)]
    printers = [p for p in printers if p]
    if printers and "compatible_printers" in full:
        full["compatible_printers"] = printers

    out = a.out or full["name"].replace("/", "_") + ".json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(full, f, indent=4, ensure_ascii=False)
    print(f'{out}: {len(full)} keys, inherits nothing, compatible_printers = {full.get("compatible_printers")}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
