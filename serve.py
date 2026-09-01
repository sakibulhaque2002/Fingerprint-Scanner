#!/usr/bin/env python3
"""
Local dev server for the SecuGen demo page.

Serves the static files in this folder exactly like `python -m http.server`,
but also handles POST /enroll/fingers itself: it forwards the request to the
real enrollment API server-side (adding the Authorization header there), and
relays the response back. Because the browser only ever talks to this same
localhost server, the enrollment API's CORS rejection never comes into play
-- CORS only restricts cross-origin calls made directly by browser JS.
"""

import http.server
import urllib.request
import urllib.error

PORT = 8080
ENROLL_API_URL = "http://10.140.0.33:8079/enroll/fingers"
ENROLL_API_AUTHORIZATION = "Basic Z3Vlc3Q6Z3Vlc3Q="


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
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
        print("Serving this folder on http://localhost:%d" % PORT)
        print("Proxying POST /enroll/fingers -> %s" % ENROLL_API_URL)
        httpd.serve_forever()
