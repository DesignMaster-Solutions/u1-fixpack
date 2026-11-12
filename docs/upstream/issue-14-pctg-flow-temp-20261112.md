I read the code path for this in the three public releases (1.6.0 `10f2f69`, 2.0.0 `93cb12f`, 2.1.0 `7ac453b`). It is the same in all three, so 2.1.0 does not change it. I do not have a U1 here, so this is from the source only.

**Where the 220 comes from**

- `filament_parameters.py` has no `PCTG` key in any of the five tables (0 matches; same for `BVOH`, `EVA`, `HIPS`, `PHA` from the comment above). `_search_filament_param_value()` finds nothing, so `print_temp` stays at `FILAMENT_FLOW_TEMP_UNKNOWN = 220` (line 6, used at 1779).
- `FLOW_CALIBRATE` (`flow_calibrator.py`) starts from that table value (line 726 to 735) and then tries to replace it with the temperature of the print file: `gcode_temp = print_task_config_2['nozzle_temp'][filament_index]` (line 765), `flow_temp = gcode_temp` (line 792).
- That replacement is all or nothing. One `if` (lines 771 to 777) checks line width, layer height, max volumetric speed, acceleration, flow ratio and the temperature together. If any single one is missing or out of range the whole block is dropped, including a perfectly good nozzle temperature, and the calibration runs at the table value. For a type that is not in the table, that is 220.

So a PCTG print calibrates at 220 only when the print-file parameters were not accepted. klippy.log says which path was taken, one line per calibrated head:

```
[flow_calibrate] using gcode parameters for extruder      <- file temperature used
[flow_calibrate] gcode parameters not valid for extruder  <- fell back to the table (220 for PCTG)
```

and the values the screen passed for the print are in the line that starts with `[print_task_config] SET_PRINT_TASK_PARAMETERS` (look for `NOZZLE_TEMP=`).

@SchmartMaker if you still have a klippy.log from one of those PCTG prints, those two lines would tell whether the fix belongs in the table (add PCTG) or in that `if` (keep the file temperature when only the speed fields are unusable). I can write the second one as a small patch with a test once the log shows that is the path.

**Related, same file**

`is_allow_to_print()` rejects every main type that starts with `PC` on a 0.2 mm nozzle (line 1953, `filament_main_type.startswith('PC')`). That was presumably meant for polycarbonate, but it also matches `PCTG`, while `PETG` is allowed on 0.2. If that is not intended, the check needs to be `== 'PC'` or `startswith('PC-')`.
