# A phone alarm when the U1 pauses or stops (no patch)

Asked on the forum: [Fault Alarm - How?](https://forum.snapmaker.com/t/44319). The U1 has no sounder,
but the Moonraker it ships can already push a notification when the job changes state.

## What the firmware does (read in the source, 2.1.0)

- `klippy/extras/filament_entangle_detect.py`: on a tangle it sends the pause command and runs `PAUSE`.
  So a tangle ends as a **paused** job, the same state a runout leaves.
- `moonraker/components/job_state.py` turns that into the event `job_state:paused`, and
  `moonraker/components/notifier.py` forwards the events `started, complete, error, cancelled, paused,
  resumed` to any service [Apprise](https://github.com/caronc/apprise/wiki) knows.
- `pyproject.toml` of Snapmaker/u1-moonraker pins `apprise==1.8.0`, so the dependency is part of the
  firmware's own requirement list. The shipped `lava/moonraker.conf` has no `[notifier]` section.

## The recipe

Add to `moonraker.conf` and restart Moonraker:

```ini
[notifier night_alarm]
url: ntfy://u1-alarm-PICK-A-LONG-RANDOM-NAME?priority=max
events: paused, error, cancelled
title: Snapmaker U1
body: U1 {event_name}: {event_args[1].filename}
```

Install the free [ntfy](https://ntfy.sh) app on the phone, subscribe to the same topic name and let
it override Do Not Disturb for max priority: that is the audible alarm. The topic name is the only
secret on the public ntfy.sh server, so make it long. For a printer with no internet, point the URL at
a ntfy server on the LAN (`ntfy://192.168.x.y/topic`) or use any other Apprise URL (Telegram, Pushover,
e-mail, a Home Assistant webhook that rings a speaker).

Check it without waiting for a tangle: `curl http://<printer>:7125/server/notifiers/list` must show
`night_alarm`, then pause a print by hand and the phone should ring. (The component also has a test
call, `/debug/notifiers/test`, but it only exists when Moonraker runs in debug mode.)

## Without the false alarm on an automatic refill

Pointed out by ReplixCast in the same topic: a runout is also a pause, and the U1 can carry on by
itself. Read in `klippy/extras/filament_switch_sensor.py` and `print_task_config.py` (2.1.0): on a
runout the sensor runs `PAUSE IS_RUNOUT=1`, then `INNER_AUTO_REPLENISH_FILAMENT`. If another head holds
a matching spool (`auto_replenish_filament` defaults to on) it issues `RESUME REPLENISH=1` in the same
handler and the print goes on; only when no head matches does it raise the runout exception and stay
paused. A tangle never takes the refill path. So `events: paused` rings for a refill that needed
nobody.

Moonraker cannot tell the two apart at the moment of the pause, but time can: ring only when the same
pause has lasted longer than a refill does. Take `paused` out of the notifier and let Klipper call it:

```ini
# moonraker.conf
[notifier night_alarm]
url: ntfy://u1-alarm-PICK-A-LONG-RANDOM-NAME?priority=max
events: error, cancelled
title: Snapmaker U1
body: U1 {event_name} {event_message}{event_args[1].filename if event_args else ""}
```

```ini
# Klipper config
[gcode_macro NIGHT_ALARM]
# seconds one pause must last before the phone rings (longer than a refill on your machine)
variable_wait: 120
# print_duration of the pause being watched (-1 = none), when it was first seen, and if it rang
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

How it tells one pause from the next: in `klippy/extras/print_stats.py` (2.1.0) `print_duration` stops
while the job is paused and moves again as soon as it prints, while `total_duration` keeps running. So
the frozen `print_duration` names the pause and `total_duration` measures it. A print that resumed and
paused again between two looks (pointed out by ReplixCast: a counter of looks misses that) comes back
with a different `print_duration`, so the wait starts over, and a new pause can ring again after an
earlier alarm. It looks every 5 s and rings once, between `wait` and `wait` + 10 s after the pause
began. Edge left: before the first extrusion `print_duration` does not move, so two pauses then would
read as one.

`notify` is the remote method the notifier component registers (`notifier.py`,
`register_remote_method("notify", ...)`), and `action_call_remote_method` is in the U1 Klipper
(`gcode_macro.py`). The price is one more file to edit (Klipper config) and a pause you made by hand
also rings after `wait`. For a tracker that reads the API instead: `print_stats.exception` carries the
runout code in both cases, and `machine_state_manager.action_code` at `PRINT_REPLENISHING` (131) is a
hint, not a verdict (ReplixCast: it is also set for a reload on the same head and drops to 0 after a
success and after a failure alike). What decides is the print going on: the same `print_duration`
moving again.

## What was tested and what was not

`tests/test_notifier_recipe.py` renders the body with the delimiters Moonraker uses and delivers it
through apprise 1.8.0 to a local ntfy-style server: topic, message and max priority arrive. For the
debounced variant it cuts the macro out of this page and runs it on virtual time with Klipper's
template delimiters, against a model of `print_stats` built from the 2.1.0 `get_status`, at several
timer phases: a pause that resumes before `wait` does not call `notify`; one that stays calls it once,
between `wait` and `wait` + 10 s; a print that resumes and pauses again between two looks restarts the
wait; a pause after an alarm rings again; and the body renders for both a job event and the remote
call. How long the U1 stays in `paused` during a real refill was not measured (no printer here), so
`wait: 120` is a guess with room; set it above what your machine takes.

Not tested: I do not own a U1, so this did not run on a printer. Two things to confirm on the machine:
that you can edit `moonraker.conf` on your firmware (stock may need root access or the extended
firmware), and that `/server/notifiers/list` shows the notifier after the restart.
