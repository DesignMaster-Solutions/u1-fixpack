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


@unittest.skipIf(apprise is None, "needs apprise and jinja2")
class DebouncedAlarm(unittest.TestCase):
    """Runs the watch macro tick by tick with Klipper's template delimiters and a recorded remote call."""

    def run_ticks(self, states):
        env = jinja2.Environment("{%", "%}", "{", "}")
        tpl = env.from_string(_watch_template())
        ticks, calls = 0, []
        for state in states:
            printer = {"print_stats": {"state": state, "filename": "benchy.gcode"},
                       "gcode_macro NIGHT_ALARM": {"paused_ticks": ticks}}
            out = tpl.render(printer=printer,
                             action_call_remote_method=lambda m, **kw: calls.append((m, kw)) or "")
            sets = [l for l in out.splitlines() if "SET_GCODE_VARIABLE" in l]
            self.assertEqual(len(sets), 1, out)
            ticks = int(sets[0].rsplit("VALUE=", 1)[1])
            self.assertIn("UPDATE_DELAYED_GCODE ID=night_alarm_watch DURATION=30", out)
        return calls

    def test_refill_that_resumes_does_not_ring(self):
        self.assertEqual(self.run_ticks(["printing", "paused", "printing", "printing"]), [])

    def test_pause_that_stays_rings_once(self):
        calls = self.run_ticks(["printing", "paused", "paused", "paused", "paused"])
        self.assertEqual(calls, [("notify", {"name": "night_alarm", "message": "still paused: benchy.gcode"})])

    def test_second_pause_rings_again(self):
        self.assertEqual(len(self.run_ticks(["paused", "paused", "printing", "paused", "paused"])), 2)

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
