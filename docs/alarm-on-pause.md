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

Moonraker cannot tell the two apart at the moment of the pause, but time can: ring only when the job is
still paused on the second look. Take `paused` out of the notifier and let Klipper call it:

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
variable_paused_ticks: 0
gcode:

[delayed_gcode night_alarm_watch]
initial_duration: 30
gcode:
  {% set n = printer["gcode_macro NIGHT_ALARM"].paused_ticks %}
  {% if printer.print_stats.state == "paused" %}
    {% if n == 1 %}
      {action_call_remote_method("notify", name="night_alarm", message="still paused: " ~ printer.print_stats.filename)}
    {% endif %}
    SET_GCODE_VARIABLE MACRO=NIGHT_ALARM VARIABLE=paused_ticks VALUE={n + 1}
  {% else %}
    SET_GCODE_VARIABLE MACRO=NIGHT_ALARM VARIABLE=paused_ticks VALUE=0
  {% endif %}
  UPDATE_DELAYED_GCODE ID=night_alarm_watch DURATION=30
```

It looks every 30 s and rings once, 30 to 60 s after a pause that is still there; a pause that resumed
before the second look never rings, and the next pause rings again. `notify` is the remote method the
notifier component registers (`notifier.py`, `register_remote_method("notify", ...)`), and
`action_call_remote_method` is in the U1 Klipper (`gcode_macro.py`). The price is one more file to edit
(Klipper config) and a pause you made by hand also rings after a minute. For a tracker that reads the
API instead: `print_stats.exception` carries the runout code in both cases, so the reliable signal is
`paused` followed by `resumed`, or `machine_state_manager.action_code` at `PRINT_REPLENISHING` (131).

## What was tested and what was not

`tests/test_notifier_recipe.py` renders the body with the delimiters Moonraker uses and delivers it
through apprise 1.8.0 to a local ntfy-style server: topic, message and max priority arrive. For the
debounced variant it cuts the watch macro out of this page and runs it tick by tick with Klipper's
template delimiters: a pause that resumes does not call `notify`, one that stays calls it once, a second
pause calls it again, and the body renders for both a job event and the remote call. How long the U1
stays in `paused` during a real refill was not measured (no printer here); if it is longer than 30 s on
yours, raise the two `30`.

Not tested: I do not own a U1, so this did not run on a printer. Two things to confirm on the machine:
that you can edit `moonraker.conf` on your firmware (stock may need root access or the extended
firmware), and that `/server/notifiers/list` shows the notifier after the restart.
