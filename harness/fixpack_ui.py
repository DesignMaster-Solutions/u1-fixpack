"""Klipper extras module for the U1 Fix Pack: plays the touchscreen / Moonraker in batch mode.

Batch mode has no UI. A print file asks for a UI action with FIXPACK_UI_PAUSE at the point
where a user would press Pause. The press is delivered the way Moonraker delivers it: through
the firmware's own webhook handler (pause_resume/pause, then pause_resume/resume once the
printer reports it is paused), from outside the file, at the next line boundary where the
virtual_sdcard loop lets go of the G-code lock. Nothing in the firmware is replaced.

The print is started the way Moonraker starts it: SDCARD_PRINT_FILE, sent once klippy reports
"ready" (some U1 ready handlers yield, so input that arrives earlier would race them).
Filament switches read "present" (see _ready): batch mode has no pins.
Every console response the firmware writes is appended to $FIXPACK_RESPONSES, and klippy is
asked to exit when the print ends (batch mode already exits on the first error).
"""
import logging
import os


class FixpackUI:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.out = open(os.environ.get("FIXPACK_RESPONSES", "/tmp/responses.txt"), "w", buffering=1)
        self.resume_armed = False
        self.started = False
        self.requested = False
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode.register_output_handler(self._respond)
        self.gcode.register_command("FIXPACK_UI_PAUSE", self.cmd_FIXPACK_UI_PAUSE)
        self.printer.register_event_handler("klippy:ready", self._ready)

    def _respond(self, msg):
        self.out.write(msg + "\n")

    def _ready(self):
        self.pause_resume = self.printer.lookup_object("pause_resume")
        self.print_stats = self.printer.lookup_object("print_stats")
        # Loaded heads: each filament switch reports "present" through the firmware's own pin-event
        # entry point, as the MCU does at boot. While it reads present, no runout timer runs.
        now = self.reactor.monotonic()
        for name, sensor in self.printer.lookup_objects("filament_motion_sensor"):
            sensor.encoder_event(now, True)
        # The auto-feed modules' startup check calls the RFID reader (filament_detect), which batch
        # mode cannot load; left alone it crashes klippy ~20 s in. Cancelled: the feeders stay in
        # their boot state, and nothing in pause/resume reads them.
        for name, feed in self.printer.lookup_objects("filament_feed"):
            if feed.filament_detect is None:
                self.reactor.update_timer(feed._check_init_state_timer, self.reactor.NEVER)
        self.reactor.register_timer(self._watch, self.reactor.NOW)

    def _start(self):
        self.gcode.run_script("G28\nSDCARD_PRINT_FILE FILENAME=%s" % os.environ.get("FIXPACK_PRINT", "print.gcode"))

    def cmd_FIXPACK_UI_PAUSE(self, gcmd):
        self.out.write("FIXPACK: user presses Pause\n")
        self.resume_armed = True
        self.reactor.register_callback(lambda e: self.pause_resume._handle_pause_request(None))
        # On the printer the file loop yields whenever the toolhead waits for the MCU; batch mode
        # never waits, so yield once here to let the request reach the G-code lock queue.
        self.reactor.pause(self.reactor.monotonic() + 0.05)

    def _watch(self, eventtime):
        if not self.started and self.printer.get_state_message()[1] != "ready":
            return eventtime + 0.2
        if not self.started and self.print_stats.state == "standby" and not self.requested:
            self.requested = True
            self.reactor.register_callback(lambda e: self._start())
        state = self.print_stats.state
        if state == "printing":
            self.started = True
        # batch mode never waits on the MCU, so a whole print can run between two polls
        self.started = self.started or (self.requested and state != "standby")
        if self.resume_armed and state == "paused" and self.pause_resume.is_paused:
            self.resume_armed = False
            self.out.write("FIXPACK: user presses Resume\n")
            self.reactor.register_callback(lambda e: self.pause_resume._handle_resume_request(None))
        elif self.started and state in ("complete", "cancelled", "error"):
            self.out.write("FIXPACK: print ended, state %s\n" % (state,))
            logging.info("fixpack_ui: print ended (%s), exiting", state)
            self.printer.request_exit("exit")
            return self.reactor.NEVER
        return eventtime + 0.2


def load_config(config):
    return FixpackUI(config)
