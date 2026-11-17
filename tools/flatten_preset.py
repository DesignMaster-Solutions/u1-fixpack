#!/usr/bin/env python3
"""Turn a preset that inherits from a "Project-inside preset" into a full, standalone preset.

Snapmaker Orca saves a user preset as the few keys that differ from its parent plus
"inherits": "<parent name>". When the parent only lives inside a .3mf, the saved preset
is unusable in any other project (Snapmaker/OrcaSlicer#1207). This resolves the chain
from the presets embedded in the .3mf and writes one JSON with every key and no parent.

    python3 flatten_preset.py project.3mf                      # lists the presets inside
    python3 flatten_preset.py project.3mf "Preset name"        # a preset stored in the 3mf
    python3 flatten_preset.py project.3mf saved_user_preset.json   # the partial file from AppData
    python3 flatten_preset.py --system <slicer>/system/Snapmaker/process saved_user_preset.json
                                                               # parent is a system preset: freeze a full copy

Then in the slicer: File > Import > Import Configs, and pick the written file.
"""
import argparse
import json
import os
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


# Preset::print_options() of Snapmaker Orca 2.4.1: what the slicer copies out of the project config
PROCESS_KEYS = frozenset("""
layer_height initial_layer_print_height wall_loops alternate_extra_wall slice_closing_radius spiral_mode
spiral_mode_smooth spiral_mode_max_xy_smoothing spiral_starting_flow_ratio spiral_finishing_flow_ratio
slicing_mode top_shell_layers top_shell_thickness top_surface_density bottom_surface_density
bottom_shell_layers bottom_shell_thickness top_color_penetration_layers bottom_color_penetration_layers
extra_perimeters_on_overhangs ensure_vertical_shell_thickness reduce_crossing_wall detect_thin_wall
detect_overhang_wall overhang_reverse overhang_reverse_threshold overhang_reverse_internal_only
wall_direction seam_position staggered_inner_seams wall_sequence is_infill_first sparse_infill_density
fill_multiline sparse_infill_pattern lateral_lattice_angle_1 lateral_lattice_angle_2 infill_overhang_angle
top_surface_pattern bottom_surface_pattern infill_direction solid_infill_direction counterbore_hole_bridging
infill_shift_step sparse_infill_rotate_template solid_infill_rotate_template symmetric_infill_y_axis
skeleton_infill_density infill_lock_depth skin_infill_depth skin_infill_density
align_infill_direction_to_model extra_solid_infills minimum_sparse_infill_area reduce_infill_retraction
internal_solid_infill_pattern gap_fill_target ironing_type ironing_pattern ironing_flow ironing_speed
ironing_spacing ironing_angle ironing_inset support_ironing support_ironing_pattern support_ironing_flow
support_ironing_spacing max_travel_detour_distance fuzzy_skin fuzzy_skin_thickness fuzzy_skin_point_distance
fuzzy_skin_first_layer fuzzy_skin_noise_type fuzzy_skin_mode fuzzy_skin_scale fuzzy_skin_octaves
fuzzy_skin_persistence max_volumetric_extrusion_rate_slope
max_volumetric_extrusion_rate_slope_segment_length extrusion_rate_smoothing_external_perimeter_only
inner_wall_speed outer_wall_speed sparse_infill_speed internal_solid_infill_speed top_surface_speed
support_speed support_object_xy_distance support_object_first_layer_gap support_interface_speed bridge_speed
internal_bridge_speed gap_infill_speed travel_speed travel_speed_z initial_layer_speed
outer_wall_acceleration initial_layer_acceleration top_surface_acceleration default_acceleration skirt_type
skirt_loops skirt_speed min_skirt_length skirt_distance skirt_start_angle skirt_height
single_loop_draft_shield draft_shield brim_width brim_object_gap brim_type brim_ears_max_angle
brim_ears_detection_length enable_support support_type support_threshold_angle support_threshold_overlap
enforce_support_layers raft_layers raft_first_layer_density raft_first_layer_expansion raft_contact_distance
raft_expansion support_base_pattern support_base_pattern_spacing support_expansion support_style
independent_support_layer_height support_angle support_interface_top_layers support_interface_bottom_layers
support_interface_pattern support_interface_spacing support_interface_loop_pattern
support_interface_min_area support_top_z_distance support_on_build_plate_only support_critical_regions_only
bridge_no_support thick_bridges thick_internal_bridges dont_filter_internal_bridges
enable_extra_bridge_layer max_bridge_length print_sequence print_order support_remove_small_overhang
filename_format wall_filament support_bottom_z_distance sparse_infill_filament solid_infill_filament
support_filament support_interface_filament support_interface_not_for_body ooze_prevention
standby_temperature_delta preheat_time delta_temperature preheat_steps interface_shells line_width
initial_layer_line_width inner_wall_line_width outer_wall_line_width sparse_infill_line_width
internal_solid_infill_line_width skin_infill_line_width skeleton_infill_line_width top_surface_line_width
support_line_width infill_wall_overlap top_bottom_infill_wall_overlap bridge_flow internal_bridge_flow
elefant_foot_compensation elefant_foot_compensation_layers xy_contour_compensation xy_hole_compensation
resolution enable_prime_tower prime_tower_width prime_tower_brim_width prime_volume prime_tower_brim_chamfer
prime_tower_brim_chamfer_max_width enable_tower_interface_features
enable_tower_interface_cooldown_during_tower wipe_tower_no_sparse_layers compatible_printers
compatible_printers_condition inherits flush_into_infill flush_into_objects flush_into_support
tree_support_branch_angle tree_support_angle_slow tree_support_wall_count tree_support_top_rate
tree_support_branch_distance tree_support_tip_diameter tree_support_branch_diameter
tree_support_branch_diameter_angle detect_narrow_internal_solid_infill gcode_add_line_number
enable_arc_fitting precise_z_height infill_combination infill_combination_max_layer_height
adaptive_layer_height support_bottom_interface_spacing enable_overhang_speed slowdown_for_curled_perimeters
overhang_1_4_speed overhang_2_4_speed overhang_3_4_speed overhang_4_4_speed initial_layer_infill_speed
only_one_wall_top timelapse_type wall_generator wall_transition_length wall_transition_filter_deviation
wall_transition_angle wall_distribution_count min_feature_size min_bead_width post_process min_length_factor
small_perimeter_speed small_perimeter_threshold bridge_angle internal_bridge_angle filter_out_gap_fill
travel_acceleration first_layer_travel_acceleration inner_wall_acceleration min_width_top_surface
default_jerk outer_wall_jerk inner_wall_jerk infill_jerk top_surface_jerk initial_layer_jerk travel_jerk
first_layer_travel_jerk default_junction_deviation top_solid_infill_flow_ratio
bottom_solid_infill_flow_ratio only_one_wall_first_layer print_flow_ratio seam_gap role_based_wipe_speed
wipe_speed accel_to_decel_enable accel_to_decel_factor wipe_on_loops wipe_before_external_loop
bridge_density internal_bridge_density precise_outer_wall bridge_acceleration sparse_infill_acceleration
internal_solid_infill_acceleration tree_support_adaptive_layer_height tree_support_auto_brim
tree_support_brim_width gcode_comments gcode_label_objects initial_layer_travel_speed exclude_object
slow_down_layers infill_anchor infill_anchor_max initial_layer_min_bead_width make_overhang_printable
make_overhang_printable_angle make_overhang_printable_hole_size notes wipe_tower_cone_angle
wipe_tower_extra_spacing wipe_tower_max_purge_speed local_z_wipe_tower_purge_lines wipe_tower_wall_type
wipe_tower_extra_rib_length wipe_tower_rib_width wipe_tower_fillet_wall wipe_tower_filament
wiping_volumes_extruders wipe_tower_bridging wipe_tower_extra_flow single_extruder_multi_material_priming
wipe_tower_rotation_angle wipe_tower_wall_gap prime_tower_enable_framework
tree_support_branch_distance_organic tree_support_branch_diameter_organic tree_support_branch_angle_organic
tree_support_transition_layers support_transition_perimeter support_transition_speed
support_transition_flow_ratio hole_to_polyhole hole_to_polyhole_threshold hole_to_polyhole_twisted
mmu_segmented_region_max_width mmu_segmented_region_interlocking_depth small_area_infill_flow_compensation
small_area_infill_flow_compensation_model seam_slope_type seam_slope_conditional scarf_angle_threshold
scarf_joint_speed scarf_joint_flow_ratio seam_slope_start_height seam_slope_entire_loop
seam_slope_min_length seam_slope_steps seam_slope_inner_walls scarf_overhang_threshold interlocking_beam
interlocking_orientation interlocking_beam_layer_count interlocking_depth interlocking_boundary_avoidance
interlocking_beam_width dithering_local_z_mode dithering_local_z_whole_objects dithering_local_z_infill
calib_flowrate_topinfill_special_order process_flow_support
""".split())


def project_process_preset(path):
    """(name, preset) the slicer builds when the 3mf has no process_settings_N.config.

    Projects written by converters (U1convert) or older slicers carry only the merged
    project_settings.config; the slicer cuts the process keys out of it and shows the
    result as "<print_settings_id>(<file name>)" under Project-inside presets.
    shortcut: process presets only; filament and printer need their own key lists.
    """
    with zipfile.ZipFile(path) as z:
        try:
            d = json.loads(z.read("Metadata/project_settings.config"))
        except KeyError:
            return None
    base = d.get("print_settings_id")
    if not isinstance(base, str) or not base:
        return None
    preset = {k: v for k, v in d.items() if k in PROCESS_KEYS}
    preset.update(name=base, print_settings_id=base, inherits="")
    if d.get("print_compatible_printers"):
        preset["compatible_printers"] = d["print_compatible_printers"]
    return f"{base}({os.path.basename(path)})", preset


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
            raise KeyError(f'parent preset "{parent}" is not inside this 3mf. If it is a system preset '
                           "(it ships with the slicer), the saved file already works in any project, and "
                           "--system <slicer process folder> makes a copy that no longer depends on it; "
                           "otherwise pass the project the preset was first saved from")
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
    if "setting_id" not in leaf:
        full.pop("setting_id", None)  # a system parent's id (GP004...) is not this preset's
    full["inherits"] = ""
    full["from"] = "User"
    return full


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", help=".3mf that holds the parent preset (leave it out when the parent is a system preset)")
    ap.add_argument("--system", metavar="DIR",
                    help="folder with the slicer\x27s own process presets, for a preset whose parent ships with "
                         "the slicer, e.g. %%AppData%%\\\\Snapmaker_Orca\\\\system\\\\Snapmaker\\\\process")
    ap.add_argument("preset", nargs="?", help="preset name inside the 3mf, or a saved preset .json")
    ap.add_argument("-o", "--out", help="output file (default: <preset name>.json)")
    ap.add_argument("--printer", action="append",
                    help="printer the preset is for; default is the project's printer. "
                         'Repeat for more than one, or pass "" to keep the parent\'s list')
    a = ap.parse_args(argv)

    if a.project.lower().endswith(".json") and not a.preset:  # only a saved preset: its parent is a system one
        a.project, a.preset = None, a.project
    presets = embedded_presets(a.project) if a.project else {}
    built = project_process_preset(a.project) if a.project else None
    if built:
        presets.setdefault(*built)
    for fn in sorted(os.listdir(a.system)) if a.system else ():
        if fn.lower().endswith(".json"):
            with open(os.path.join(a.system, fn), encoding="utf-8-sig") as f:  # the shipped files carry a BOM
                d = json.load(f)
            presets.setdefault(d.get("name"), d)
    if not a.preset:
        for name, d in presets.items():
            print(f'{name}   (inherits: {d.get("inherits") or "-"})')
        return 0
    if a.preset.lower().endswith(".json"):
        with open(a.preset, encoding="utf-8-sig") as f:
            leaf = json.load(f)
    elif a.preset in presets:
        leaf = presets[a.preset]
    else:
        print(f'no preset named "{a.preset}" in {a.project}; run without a name to list them', file=sys.stderr)
        return 2
    parent = leaf.get("inherits")
    if built and parent and parent not in presets and parent.startswith(built[1]["name"] + "("):
        presets[parent] = built[1]  # same project under another file name: the suffix is the name it had then
    try:
        full = flatten(leaf, presets)
    except (KeyError, ValueError) as e:
        print(e.args[0], file=sys.stderr)
        return 2

    # A converted parent often still lists the printers it came from (e.g. Bambu Lab X1),
    # and a standalone preset with that list is hidden on the U1.
    printers = a.printer if a.printer is not None else [project_printer(a.project) if a.project else None]
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
