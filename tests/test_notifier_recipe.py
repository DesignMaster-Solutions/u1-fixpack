"""Forum 44319 ("Fault Alarm - How?"): a phone alarm when the U1 pauses or stops overnight.

No patch here: the shipped Moonraker already carries the `[notifier]` component and pins apprise
(pyproject.toml: apprise==1.8.0, jinja2==3.1.4). This pins down the recipe in docs/alarm-on-pause.md
with those versions: the body is rendered with the delimiters Moonraker's template component uses
(jinja2.Environment('{%', '%}', '{', '}')) and delivered through apprise to a local ntfy-style server.

Not covered: Moonraker itself is not started and nothing here ran on a printer.

Run: uv run --with apprise==1.8.0,jinja2==3.1.4 python3 -m unittest -v tests.test_notifier_recipe
"""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    import apprise
    import jinja2
except ImportError:  # the Docker image has the firmware only
    apprise = None

BODY = "U1 {event_name}: {event_args[1].filename}"  # same line as docs/alarm-on-pause.md
# The debounced variant (a runout the U1 refills on its own must not ring): body that also renders for
# the remote call, which arrives with event_args == [].
BODY2 = "U1 {event_name} {event_message}{event_args[1].filename if event_args else \"\"}"


@unittest.skipIf(apprise is None, "needs apprise and jinja2")
class NotifierRecipe(unittest.TestCase):
    def setUp(self):
        got = self.got = []

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                got.append((dict(self.headers), self.rfile.read(int(self.headers.get("Content-Length", 0)))))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *a):
                pass

        self.srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.shutdown)

    def test_recipe_is_in_the_doc(self):
        with open("docs/alarm-on-pause.md") as f:
            self.assertIn("body: " + BODY, f.read())

    def test_paused_job_reaches_the_phone_topic(self):
        env = jinja2.Environment("{%", "%}", "{", "}")
        new_stats = {"state": "paused", "filename": "benchy.gcode"}
        body = env.from_string(BODY).render(event_name="paused", event_args=[{}, new_stats])
        self.assertEqual(body, "U1 paused: benchy.gcode")
        a = apprise.Apprise()
        self.assertTrue(a.add("ntfy://127.0.0.1:%d/u1-alarm?priority=max" % self.srv.server_port))
        self.assertTrue(a.notify(body=body, title="Snapmaker U1"))
        headers, raw = self.got[0]
        msg = json.loads(raw)
        self.assertEqual((msg["topic"], msg["message"]), ("u1-alarm", body))
        self.assertEqual(headers.get("X-Priority"), "max")


def _watch_template():
    """The gcode of [delayed_gcode night_alarm_watch], cut out of the doc."""
    with open("docs/alarm-on-pause.md") as f:
        doc = f.read()
    start = doc.index("[delayed_gcode night_alarm_watch]")
    block = doc[start:doc.index("```", start)]
    return block.split("gcode:\n", 1)[1]


def _macro_vars():
    """variable_* defaults of [gcode_macro NIGHT_ALARM], cut out of the doc (Klipper literal_eval's them)."""
    import ast
    with open("docs/alarm-on-pause.md") as f:
        doc = f.read()
    start = doc.index("[gcode_macro NIGHT_ALARM]")
    block = doc[start:doc.index("gcode:", start)]
    return {l.split(":", 1)[0][len("variable_"):]: ast.literal_eval(l.split(":", 1)[1].strip())
            for l in block.splitlines() if l.startswith("variable_")}


def _print_stats(t, events):
    """Klipper print_stats.get_status at time t (2.1.0 print_stats.py): print_duration freezes while
    paused, total_duration keeps running. events = [(time, "pause"|"resume")], print starts at 0."""
    paused_since, paused_total = None, 0.0
    for when, ev in events:
        if when > t:
            break
        if ev == "pause" and paused_since is None:
            paused_since = when
        elif ev == "resume" and paused_since is not None:
            paused_total += when - paused_since
            paused_since = None
    cur = t - paused_since if paused_since is not None else 0.0
    return {"state": "paused" if paused_since is not None else "printing", "filename": "benchy.gcode",
            "total_duration": float(t), "print_duration": t - paused_total - cur}


@unittest.skipIf(apprise is None, "needs apprise and jinja2")
class DebouncedAlarm(unittest.TestCase):
    """Runs the watch macro on virtual time with Klipper's template delimiters and a recorded remote call.
    Not covered: real Klipper timers and how long a real U1 refill stays paused."""

    def setUp(self):
        self.wait = _macro_vars()["wait"]

    def ring_times(self, events, end, phase=0.0):
        env = jinja2.Environment("{%", "%}", "{", "}")
        tpl = env.from_string(_watch_template())
        v = _macro_vars()
        calls, t = [], phase
        while t <= end:
            out = tpl.render(printer={"print_stats": _print_stats(t, events), "gcode_macro NIGHT_ALARM": dict(v)},
                             action_call_remote_method=lambda m, **kw: calls.append((t, m, kw)) or "")
            for l in out.splitlines():
                if "SET_GCODE_VARIABLE" in l:
                    var, val = l.split("VARIABLE=", 1)[1].split(" VALUE=")
                    v[var] = float(val) if "." in val or "e" in val else int(val)
            step = [l for l in out.splitlines() if "UPDATE_DELAYED_GCODE ID=night_alarm_watch" in l]
            self.assertEqual(len(step), 1, out)
            t += float(step[0].rsplit("DURATION=", 1)[1])
        for _, m, kw in calls:
            self.assertEqual((m, kw["name"]), ("notify", "night_alarm"))
            self.assertIn("benchy.gcode", kw["message"])
        return [c[0] for c in calls]

    def test_refill_that_resumes_does_not_ring(self):
        for phase in (0, 1.7, 4.9):
            self.assertEqual(self.ring_times([(100, "pause"), (100 + self.wait - 6, "resume")], 600, phase), [])

    def test_pause_that_stays_rings_once_after_the_wait(self):
        for phase in (0, 1.7, 4.9):
            rings = self.ring_times([(100, "pause")], 1000, phase)
            self.assertEqual(len(rings), 1)
            self.assertTrue(100 + self.wait <= rings[0] <= 100 + self.wait + 10, rings)

    def test_resume_and_new_pause_between_two_looks_restarts_the_wait(self):
        # ReplixCast 44319/7: pause seen, prints a moment between two looks, pauses again
        # looks at 100.5 and 105.5: the resume at 101 and the pause at 103 fall between them
        rings = self.ring_times([(100, "pause"), (101, "resume"), (103, "pause")], 1000, 0.5)
        self.assertEqual(len(rings), 1)
        self.assertGreaterEqual(rings[0], 103 + self.wait)

    def test_second_pause_after_an_alarm_rings_again(self):
        r = self.ring_times([(100, "pause")], 1000, 1.0)[0]
        # resume and pause again between the look that rang and the next one
        rings = self.ring_times([(100, "pause"), (r + 1, "resume"), (r + 3, "pause")], 2000, 1.0)
        self.assertEqual(len(rings), 2)
        self.assertGreaterEqual(rings[1], r + 3 + self.wait)

    def test_body_renders_for_job_event_and_remote_call(self):
        env = jinja2.Environment("{%", "%}", "{", "}")
        with open("docs/alarm-on-pause.md") as f:
            self.assertIn("body: " + BODY2, f.read())
        t = env.from_string(BODY2)
        self.assertEqual(t.render(event_name="error", event_args=[{}, {"filename": "a.gcode"}], event_message=""),
                         "U1 error a.gcode")
        self.assertEqual(t.render(event_name="remote_action", event_args=[], event_message="still paused: a.gcode"),
                         "U1 remote_action still paused: a.gcode")


if __name__ == "__main__":
    unittest.main()
