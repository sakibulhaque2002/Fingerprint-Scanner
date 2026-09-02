#!/usr/bin/env python3
"""
Local dev server for the SecuGen demo page.

Serves the static files in this folder exactly like `python -m http.server`,
but also handles POST /enroll/fingers itself: it forwards the request to the
real enrollment API server-side (adding the Authorization header there), and
relays the response back. Because the browser only ever talks to this same
localhost server, the enrollment API's CORS rejection never comes into play
-- CORS only restricts cross-origin calls made directly by browser JS.

Settings live in config.json (see CONFIG_PATH below), read once at startup.
GET/HEAD /config.json is intercepted and answered with only CONFIG["client"]
-- CONFIG["server"] (the enrollment API URL and its Authorization credential)
is never written to that response, so it never reaches the browser.
"""

import http.server
import json
import urllib.request
import urllib.error

CONFIG_PATH = "config.json"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

PORT = CONFIG["server"]["port"]
ENROLL_API_URL = CONFIG["server"]["enrollApiUrl"]
ENROLL_API_AUTHORIZATION = CONFIG["server"]["enrollApiAuthorization"]

# Only this subset ever reaches the browser (see do_GET/do_HEAD below) --
# enrollApiUrl and enrollApiAuthorization must stay server-side only, same
# reasoning as the enrollment proxy itself: the browser never sees them.
CLIENT_CONFIG_BYTES = json.dumps(CONFIG["client"]).encode("utf-8")


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/config.json":
            self.serve_client_config()
        else:
            super().do_GET()

    def do_HEAD(self):
        if self.path == "/config.json":
            self.serve_client_config(head_only=True)
        else:
            super().do_HEAD()

    def serve_client_config(self, head_only=False):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(CLIENT_CONFIG_BYTES)))
        self.end_headers()
        if not head_only:
            self.wfile.write(CLIENT_CONFIG_BYTES)

    def do_POST(self):
        if self.path == "/enroll/fingers":
            self.proxy_enroll()
        else:
            self.send_error(404, "Not Found")

    def proxy_enroll(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        req = urllib.request.Request(
            ENROLL_API_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": ENROLL_API_AUTHORIZATION,
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                self._relay(resp.status, resp.read(), resp.headers.get("Content-Type"))
        except urllib.error.HTTPError as e:
            self._relay(e.code, e.read(), "application/json")
        except urllib.error.URLError as e:
            message = (
                '{"status":"failed","failedReason":"Proxy could not reach enrollment API: %s"}'
                % str(e.reason)
            ).encode("utf-8")
            self._relay(502, message, "application/json")

    def _relay(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type or "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    with http.server.ThreadingHTTPServer(("", PORT), ProxyHandler) as httpd:
        print("Loaded settings from %s" % CONFIG_PATH)
        print("Serving this folder on http://localhost:%d" % PORT)
        print("Proxying POST /enroll/fingers -> %s" % ENROLL_API_URL)
        httpd.serve_forever()
