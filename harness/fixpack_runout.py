"""Klipper extras module for the U1 Fix Pack: a filament runout and a reload, in batch mode.

FIXPACK_UI_RUNOUT EXTRUDER=n SPOOL=... in a print file is the moment the head's filament runs
out. From there everything a U1 owner and the U1 hardware do is delivered through the
firmware's own entry points; the firmware's own code does the rest:

- the head's filament switch reads "empty": EncoderSensor.encoder_event(), the callback the
  MCU's button/ADC report calls. While printing, the firmware then watches the extruder and,
  once it has pulled detection_length (0.5 mm) past the empty switch, its timer calls
  RunoutHelper.note_filament_present(False, True), which backs up the filament info, sends the
  runout event and pauses with PAUSE IS_RUNOUT=1. Batch mode's MCU clock stays at 0, so that
  timer can never see the extruder move; the call it makes is made here, right after the pin
  event, with the same arguments;
- the RFID reader answers, for every switch change filament_detect turns into a reader request:
  "card cleared" on removal, the card read on insertion (an untagged spool reads as the empty
  FILAMENT_INFO_STRUCT, is_clear False). Batch mode cannot load the reader (fm175xx_reader,
  filament_detect), so the answer goes where filament_detect sends it: the callback
  print_task_config registers with it, called from the reactor as filament_detect does;
- once paused, after the switch's event_delay, the user feeds a spool: the switch reads
  "present" (encoder_event again);
- then the user presses Resume: pause_resume's webhook handler, as Moonraker calls it.

FIXPACK_FLOW_K LABEL=x reports the head's live pressure_advance and the factor persisted in
snapmaker/flow_calibrator.json, the two values the #8 reporter polled through Moonraker.
"""
import copy
import json
import os

EVENT_DELAY_S = 3.5  # the switch ignores changes for event_delay (3 s) after the runout
# filament_protocol.FILAMENT_INFO_STRUCT, the fields print_task_config reads, same defaults (the
# module itself imports cryptography, which the image lacks: the reason filament_detect cannot load)
EMPTY_CARD = {"VENDOR": "NONE", "MANUFACTURER": "NONE", "MAIN_TYPE": "NONE", "SUB_TYPE": "NONE",
              "ALPHA": 0xFF, "MULTI_MODE": 0, "COLOR_NUMS": 1, "ARGB_COLOR": 0xFFFFFFFF,
              "RGB_1": 0xFFFFFF, "RGB_2": 0xFFFFFF, "RGB_3": 0xFFFFFF, "RGB_4": 0xFFFFFF,
              "RGB_5": 0xFFFFFF, "SKU": 0, "OFFICIAL": False}


class FixpackRunout:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.runout = None
        self.gcode.register_command("FIXPACK_UI_RUNOUT", self.cmd_FIXPACK_UI_RUNOUT)
        self.gcode.register_command("FIXPACK_FLOW_K", self.cmd_FIXPACK_FLOW_K)
        self.printer.register_event_handler("filament_switch_sensor:runout", self._reader_answers)

    def _extruder(self, index):
        return self.printer.lookup_object("extruder" if index == 0 else "extruder%d" % index)

    def report(self, index, label):
        name = self._extruder(index).get_name()
        path = os.path.join(self.printer.get_snapmaker_config_dir(), "flow_calibrator.json")
        with open(path) as f:
            store = json.load(f)["factor"][name]
        live = self._extruder(index).get_status(self.reactor.monotonic())["pressure_advance"]
        self.gcode.respond_info("FIXPACK: flow_k %s %s live=%.6f store=%.6f" % (label, name, live, store))

    def cmd_FIXPACK_FLOW_K(self, gcmd):
        index = gcmd.get_int("EXTRUDER", self.printer.lookup_object("toolhead").get_extruder().extruder_index)
        self.report(index, gcmd.get("LABEL"))

    def cmd_FIXPACK_UI_RUNOUT(self, gcmd):
        index = gcmd.get_int("EXTRUDER")
        # SPOOL=untagged, or SPOOL=VENDOR:MAIN_TYPE:SUB_TYPE:SKU for an RFID-tagged one
        spool = gcmd.get("SPOOL")
        info = dict(EMPTY_CARD)
        if spool != "untagged":
            vendor, main_type, sub_type, sku = spool.split(":")
            info.update(VENDOR=vendor, MANUFACTURER=vendor, MAIN_TYPE=main_type, SUB_TYPE=sub_type,
                        SKU=int(sku), OFFICIAL=True)
        self.runout = {"index": index, "spool": spool, "tag": info, "phase": "running", "t": 0.}
        self.report(index, "before-runout")
        gcmd.respond_info("FIXPACK: e%d filament runs out" % index)
        sensor = self.printer.lookup_object("filament_motion_sensor e%d_filament" % index)
        # A batch print reaches this line within the switch's 2 s boot hold-off; a real one runs for minutes
        while self.reactor.monotonic() < sensor.runout_helper.min_event_systime + 0.1:
            self.reactor.pause(self.reactor.monotonic() + 0.1)
        sensor.encoder_event(self.reactor.monotonic(), False)
        sensor.runout_helper.note_filament_present(False, True)
        self.pause_resume = self.printer.lookup_object("pause_resume")
        self.print_stats = self.printer.lookup_object("print_stats")
        self.reactor.register_timer(self._watch, self.reactor.NOW)
        # batch mode never waits on the MCU: yield once so the runout handler reaches the G-code lock
        self.reactor.pause(self.reactor.monotonic() + 0.05)

    def _reader_answers(self, index, present):
        if self.runout is None or index != self.runout["index"]:
            return
        if present:
            info, is_clear = copy.deepcopy(self.runout["tag"]), False
        else:
            info, is_clear = dict(EMPTY_CARD), True
        ptc = self.printer.lookup_object("print_task_config")
        self.reactor.register_async_callback(
            lambda e: ptc._rfid_filament_info_update_cb(index, info, is_clear))

    def _watch(self, eventtime):
        r = self.runout
        paused = self.print_stats.state == "paused" and self.pause_resume.is_paused
        if r["phase"] == "running" and paused:
            r["phase"], r["t"] = "paused", eventtime
            self.report(r["index"], "runout-paused")
        elif r["phase"] == "paused" and eventtime > r["t"] + EVENT_DELAY_S:
            r["phase"], r["t"] = "fed", eventtime
            self.gcode.respond_info("FIXPACK: user feeds the spool back (%s)" % r["spool"])
            sensor = self.printer.lookup_object("filament_motion_sensor e%d_filament" % r["index"])
            sensor.encoder_event(eventtime, True)
        elif r["phase"] == "fed" and eventtime > r["t"] + 1.5:
            r["phase"] = "resumed"
            self.report(r["index"], "after-feed")
            self.gcode.respond_info("FIXPACK: user presses Resume")
            self.reactor.register_callback(lambda e: self.pause_resume._handle_resume_request(None))
            return self.reactor.NEVER
        return eventtime + 0.2


def load_config(config):
    return FixpackRunout(config)
