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


if __name__ == "__main__":
    unittest.main()
