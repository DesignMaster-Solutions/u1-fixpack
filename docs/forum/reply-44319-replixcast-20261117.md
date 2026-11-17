Good catch on both, thanks. I fixed the logic instead of tuning the numbers: the watch now tells one pause from the next by `print_stats.print_duration`. In the 2.1.0 `print_stats.py` it freezes while the job is paused and moves again as soon as it prints, while `total_duration` keeps running. So the frozen value names the pause and `total_duration` measures it. A resume and a new pause between two looks comes back with a different `print_duration`, so the wait starts over, and a pause after an earlier alarm rings again.

```ini
[gcode_macro NIGHT_ALARM]
# seconds one pause must last before the phone rings (longer than a refill on your machine)
variable_wait: 120
variable_pause_id: -1.0
variable_since: 0.0
variable_rang: 0
gcode:

[delayed_gcode night_alarm_watch]
initial_duration: 5
gcode:
  {% set v = printer["gcode_macro NIGHT_ALARM"] %}
  {% set ps = printer.print_stats %}
  {% if ps.state == "paused" %}
    {% if ps.print_duration != v.pause_id %}
      SET_GCODE_VARIABLE MACRO=NIGHT_ALARM VARIABLE=pause_id VALUE={ps.print_duration}
      SET_GCODE_VARIABLE MACRO=NIGHT_ALARM VARIABLE=since VALUE={ps.total_duration}
      SET_GCODE_VARIABLE MACRO=NIGHT_ALARM VARIABLE=rang VALUE=0
    {% elif v.rang == 0 and ps.total_duration - v.since >= v.wait %}
      {action_call_remote_method("notify", name="night_alarm", message="paused " ~ (ps.total_duration - v.since)|int ~ " s: " ~ ps.filename)}
      SET_GCODE_VARIABLE MACRO=NIGHT_ALARM VARIABLE=rang VALUE=1
    {% endif %}
  {% elif v.pause_id != -1 %}
    SET_GCODE_VARIABLE MACRO=NIGHT_ALARM VARIABLE=pause_id VALUE=-1.0
  {% endif %}
  UPDATE_DELAYED_GCODE ID=night_alarm_watch DURATION=5
```

It looks every 5 s and rings once, between `wait` and `wait` + 10 s after the pause began, so the 45 s case no longer depends on the phase. `wait: 120` is a guess with room until someone times a real refill (CrazyIvan, your next video would settle it). The moonraker.conf part is the same as before. One edge left: before the first extrusion `print_duration` does not move, so two pauses there would read as one.

Agreed on 131: the page now calls it a hint, not a verdict.

Tested: the macro runs on virtual time against a model of `print_stats` built from the 2.1.0 `get_status`, at several timer phases, including your two cases; the old counter logic, put back as a mutant, fails both. Still not run on a printer. Page: [alarm-on-pause.md](https://github.com/DesignMaster-Solutions/u1-fixpack/blob/main/docs/alarm-on-pause.md)
