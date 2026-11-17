import json
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import flatten_preset  # noqa: E402

PARENT = {"name": "0.24mm converted(orig.3mf)", "inherits": "", "from": "project",
          "print_settings_id": "0.24mm converted(orig.3mf)", "layer_height": "0.24",
          "brim_type": "auto_brim", "enable_prime_tower": "1",
          "compatible_printers": ["Bambu Lab X1 Carbon 0.4 nozzle"]}
CHILD = {"name": "In project", "inherits": PARENT["name"], "from": "project",
         "print_settings_id": "In project", "brim_type": "no_brim"}
# what Snapmaker Orca 2.4.1 writes to AppData in Snapmaker/OrcaSlicer#1207
SAVED = {"name": "TEST", "inherits": PARENT["name"], "from": "User", "print_settings_id": "TEST",
         "brim_type": "no_brim", "enable_prime_tower": "0", "version": "0.0.0.0"}


class FlattenPresetTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.proj = os.path.join(self.dir.name, "p.3mf")
        with zipfile.ZipFile(self.proj, "w") as z:
            z.writestr("Metadata/project_settings.config",
                       json.dumps({"name": "project_settings", "printer_settings_id": "Snapmaker U1 (0.4 nozzle)"}))
            z.writestr("Metadata/process_settings_1.config", json.dumps(PARENT))
            z.writestr("Metadata/process_settings_2.config", json.dumps(CHILD))

    def run_tool(self, *args):
        out = os.path.join(self.dir.name, "out.json")
        rc = flatten_preset.main([self.proj, *args, "-o", out])
        return rc, (json.load(open(out)) if os.path.exists(out) else None)

    def test_saved_user_preset_gets_every_parent_key_and_no_parent(self):
        saved = os.path.join(self.dir.name, "saved.json")
        json.dump(SAVED, open(saved, "w"))
        rc, full = self.run_tool(saved)
        self.assertEqual(rc, 0)
        self.assertEqual(full["inherits"], "")
        self.assertEqual(full["layer_height"], "0.24")       # from the parent
        self.assertEqual(full["enable_prime_tower"], "0")    # the child wins
        self.assertEqual((full["name"], full["print_settings_id"], full["from"]), ("TEST", "TEST", "User"))
        self.assertEqual(full["compatible_printers"], ["Snapmaker U1 (0.4 nozzle)"])

    def test_preset_by_name_and_chain_of_two(self):
        grand = os.path.join(self.dir.name, "g.json")
        json.dump({"name": "G", "inherits": "In project", "enable_prime_tower": "0"}, open(grand, "w"))
        rc, full = self.run_tool(grand)
        self.assertEqual((rc, full["brim_type"], full["layer_height"], full["print_settings_id"]),
                         (0, "no_brim", "0.24", "G"))
        rc, full = self.run_tool("In project", "--printer", "")
        self.assertEqual((rc, full["compatible_printers"]), (0, PARENT["compatible_printers"]))

    def test_missing_parent_is_an_error_not_a_partial_file(self):
        lost = os.path.join(self.dir.name, "lost.json")
        json.dump({"name": "X", "inherits": "not in this project"}, open(lost, "w"))
        rc, full = self.run_tool(lost)
        self.assertEqual((rc, full), (2, None))

    def test_project_with_only_project_settings_like_u1convert_writes(self):
        # Snapmaker/OrcaSlicer#1207, second report: no process_settings_N.config in the 3mf
        proj = os.path.join(self.dir.name, "conv-U1.3mf")
        with zipfile.ZipFile(proj, "w") as z:
            z.writestr("Metadata/project_settings.config", json.dumps({
                "name": "project_settings", "from": "project", "print_settings_id": "0.24mm conv",
                "printer_settings_id": "Snapmaker U1 (0.4 nozzle)", "filament_settings_id": ["PLA"],
                "print_compatible_printers": ["Bambu Lab X1 0.4 nozzle"], "inherits_group": ["", "", ""],
                "layer_height": "0.24", "brim_type": "auto_brim", "nozzle_temperature": ["220"]}))
        saved = os.path.join(self.dir.name, "saved.json")
        # saved while the project still had another file name
        json.dump(dict(SAVED, inherits="0.24mm conv(before-rename.3mf)"), open(saved, "w"))
        out = os.path.join(self.dir.name, "o.json")
        self.assertEqual(flatten_preset.main([proj, saved, "-o", out]), 0)
        full = json.load(open(out))
        self.assertEqual((full["layer_height"], full["brim_type"], full["inherits"], full["print_settings_id"]),
                         ("0.24", "no_brim", "", "TEST"))
        self.assertNotIn("nozzle_temperature", full)  # filament key stays out of a process preset
        self.assertNotIn("filament_settings_id", full)
        self.assertEqual(full["compatible_printers"], ["Snapmaker U1 (0.4 nozzle)"])
        json.dump(dict(SAVED, inherits="some other preset(x.3mf)"), open(saved, "w"))
        self.assertEqual(flatten_preset.main([proj, saved, "-o", out]), 2)


if __name__ == "__main__":
    unittest.main()
