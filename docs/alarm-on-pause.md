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

## What was tested and what was not

`tests/test_notifier_recipe.py` renders the body with the delimiters Moonraker uses and delivers it
through apprise 1.8.0 to a local ntfy-style server: topic, message and max priority arrive.

Not tested: I do not own a U1, so this did not run on a printer. Two things to confirm on the machine:
that you can edit `moonraker.conf` on your firmware (stock may need root access or the extended
firmware), and that `/server/notifiers/list` shows the notifier after the restart.
