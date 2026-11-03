"""Derived from U1 Dry Run dryrun/dryrun_tracer.py (GPL-3.0, same author).

Klipper extras module: logs every toolhead move in batch mode.

Klipper's G-code layer and the U1 tool-change code both end in toolhead.move, so this
sees the real macro motion, not just what the slicer wrote.
"""
import os


# Commands that wait on hardware or on-printer services that do not exist in batch mode.
# They become no-ops and are listed in the report, so a reader sees what was not exercised.
# shortcut: list comes from Orca 2.4.x start/end G-code; re-check on each firmware bump.
SKIPPED_COMMANDS = (
    "DEFECT_DETECTION_START", "DEFECT_DETECTION_STOP", "DEFECT_DETECTION_DETECT",
    "DEFECT_DETECTION_DETECT_BED", "DEFECT_DETECT_NOODLE_FIRST", "DETECT_BED_PLATE",
    "TIMELAPSE_START", "TIMELAPSE_STOP", "TIMELAPSE_TAKE_FRAME",
    "SM_PRINT_AUTO_FEED", "SM_PRINT_FLOW_CALIBRATE", "SM_PRINT_END_AUTO_UNLOAD_FILAMENT",
    "BED_MESH_CALIBRATE", "WAIT_CHAMBER_TEMP", "SET_PURIFIER_MODE",
)


class DryrunTracer:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.path = os.environ.get("DRYRUN_TRACE", "/tmp/dryrun.trace")
        self.out = open(self.path, "w", buffering=1)
        self.line = 0
        self.in_gcode_move = False
        self.skipped = set()
        self.active = 0  # index of the tool on the carriage; T0 at boot like the real printer
        self.prev_xy = (0.0, 0.0)
        self.printer.register_event_handler("klippy:connect", self._connect)
        self.printer.register_event_handler("klippy:ready", self._ready)
        self.printer.register_event_handler("klippy:disconnect", self._finish)

    def _connect(self):
        self.toolhead = toolhead = self.printer.lookup_object("toolhead")
        orig_move = toolhead.move

        def traced_move(newpos, speed):
            orig_move(newpos, speed)
            self._simulate_dock(newpos)
            ext = toolhead.get_extruder().get_name()
            self.out.write(
                "M %.3f %.3f %.3f %.5f %.1f %d %s %.3f %s\n"
                % (newpos[0], newpos[1], newpos[2], newpos[3], speed,
                   self.line, ext, toolhead.print_time,
                   "G" if self.in_gcode_move else "F")
            )

        toolhead.move = traced_move
        for i, ext in enumerate(self._extruders()):
            if ext.park_detector is not None:
                ext.park_detector.get_park_detector_status = self._status_fn(i)

    def _finish(self):
        self.out.write("END %.3f\n" % (self.toolhead.get_last_move_time(),))
        self.out.close()

    def _extruders(self):
        return self.printer.lookup_object("extruder_list", [])

    def _status_fn(self, index):
        def status():
            on_carriage = self.active == index
            return {"state": "ACTIVATE" if on_carriage else "PARKED",
                    "park_pin": not on_carriage, "active_pin": on_carriage,
                    "grab_valid_pin": on_carriage}
        return status

    def _simulate_dock(self, newpos):
        # There are no sensors in batch mode. The dock is purely mechanical: at the dock Y,
        # sliding X onto a tool's park X releases it; sliding X off that spot grabs it.
        x, y = newpos[0], newpos[1]
        px, py = self.prev_xy
        self.prev_xy = (x, y)
        for i, ext in enumerate(self._extruders()):
            park = ext.xy_park_position
            if park is None or abs(y - park[1]) > 0.01 or abs(py - park[1]) > 0.01:
                continue
            if self.active == i and abs(x - park[0]) < 0.01 and abs(px - park[0]) > 0.01:
                self.active = None
            elif self.active is None and abs(px - park[0]) < 0.01 and abs(x - park[0]) > 0.01:
                self.active = i

    def _ready(self):
        gcode = self.printer.lookup_object("gcode")
        # Arc segments call gcode_move.cmd_G1 directly, bypassing the G1 dispatcher.
        for cmd in ("G0", "G1", "G2", "G3"):
            orig = gcode.register_command(cmd, None)
            if orig is not None:
                gcode.register_command(cmd, self._wrap(orig))
        gcode.register_command("DRYRUN_LINE", self._set_line)
        gcode.register_command("DRYRUN_PRINT_START", self._start_print)
        gcode.register_command("DRYRUN_FAN_DIAG", self._fan_diag)
        orig_error = gcode._respond_error

        def respond_error(msg):
            self.out.write("ERR %d %s\n" % (self.line, " ".join(msg.split())))
            orig_error(msg)

        gcode._respond_error = respond_error
        for cmd in SKIPPED_COMMANDS:
            gcode.register_command(cmd, None)
            gcode.register_command(cmd, self._skip)
        # No endstops in batch mode: homing just declares the axis at its endstop.
        gcode.register_command("G28", None)
        gcode.register_command("G28", self._home)

    def _skip(self, gcmd):
        name = gcmd.get_command()
        if name not in self.skipped:
            self.skipped.add(name)
            self.out.write("SKIP %s\n" % (name,))

    def _home(self, gcmd):
        toolhead = self.toolhead
        kin = toolhead.get_kinematics()
        axes = [i for i, a in enumerate("XYZ") if gcmd.get(a, None) is not None]
        axes = axes or [0, 1, 2]
        pos = toolhead.get_position()
        for axis in axes:
            pos[axis] = kin.rails[axis].get_homing_info().position_endstop
        toolhead.set_position(pos, homing_axes=axes)

    def _wrap(self, orig):
        def handler(gcmd):
            text = gcmd.get_commandline()
            pos = text.rfind(";L")
            if pos >= 0:
                try:
                    self.line = int(text[pos + 2:])
                except ValueError:
                    pass
            self.in_gcode_move = True
            try:
                orig(gcmd)
            finally:
                self.in_gcode_move = False
        return handler

    def _start_print(self, gcmd):
        # Batch mode has no virtual-SD lifecycle; use the real firmware transition.
        self.printer.lookup_object("print_stats").note_start()

    def _fan_diag(self, gcmd):
        fan = self.printer.lookup_object("fan").fan
        saved = self.printer.lookup_object("gcode_move").saved_states.get(
            "fan_sync_test", {}).get("fan_speed_dict", {}).get("main_fan")
        requested = getattr(fan, "get_requested_speed", lambda: fan.last_fan_value)()
        gcmd.respond_info("DRYRUN fan requested=%s status=%s saved=%s scheduled_time=%s" %
                          (requested,
                           fan.get_status(self.printer.get_reactor().monotonic())["speed"],
                           saved, fan.last_fan_time))

    def _set_line(self, gcmd):
        self.line = gcmd.get_int("N")


def load_config(config):
    return DryrunTracer(config)
