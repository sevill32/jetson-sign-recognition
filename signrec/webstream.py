"""MJPEG web streaming for the live camera view.

Only the Python standard library is used, so this works on the stock
JetPack Python (3.6) without installing extra packages.
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

PAGE = """<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jetson Live Camera</title>
<style>
  html, body { margin: 0; height: 100%; background: #101010; color: #eee;
               font-family: sans-serif; }
  header { padding: 8px 14px; background: #1c1c1c; font-size: 14px; }
  header b { color: #6fd36f; }
  .wrap { height: calc(100% - 38px); display: flex; align-items: center;
          justify-content: center; }
  img { max-width: 100%; max-height: 100%; }
</style>
</head>
<body>
<header>Jetson Sign Recognition &mdash; <b>LIVE</b>
  &nbsp;|&nbsp; <a href="/snapshot.jpg" style="color:#8cf">snapshot</a></header>
<div class="wrap"><img src="/stream.mjpg" alt="live camera"></div>
</body>
</html>
"""

BOUNDARY = "signrecframe"


class FrameBuffer(object):
    """Thread-safe holder for the latest JPEG frame(s)."""

    def __init__(self):
        self._condition = threading.Condition()
        self._jpeg = None
        self._sequence = 0
        self._closed = False

    def publish(self, jpeg):
        with self._condition:
            self._jpeg = jpeg
            self._sequence += 1
            self._condition.notify_all()

    def close(self):
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def latest(self):
        with self._condition:
            return self._jpeg, self._sequence

    def wait_for_next(self, sequence, timeout=5.0):
        """Return (jpeg, sequence), waiting for a newer frame if available."""
        with self._condition:
            if not self._closed and self._sequence == sequence:
                self._condition.wait(timeout)
            return self._jpeg, self._sequence


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _handler(buffer, page):
    class StreamHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send_bytes(200, "text/html; charset=utf-8",
                                 page.encode("utf-8"))
            elif path in ("/stream.mjpg", "/stream", "/video"):
                self._stream(buffer)
            elif path == "/snapshot.jpg":
                jpeg, _ = buffer.latest()
                if jpeg is None:
                    self._send_bytes(503, "text/plain", b"no frame yet")
                else:
                    self._send_bytes(200, "image/jpeg", jpeg)
            elif path == "/health":
                self._send_bytes(200, "text/plain", b"ok")
            else:
                self._send_bytes(404, "text/plain", b"not found")

        def _send_bytes(self, code, content_type, body):
            try:
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _stream(self, buffer):
            try:
                self.send_response(200)
                self.send_header("Content-Type",
                                 "multipart/x-mixed-replace; boundary=%s"
                                 % BOUNDARY)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                sequence = -1
                while not buffer._closed:
                    jpeg, sequence = buffer.wait_for_next(sequence,
                                                          timeout=2.0)
                    if jpeg is None:
                        continue
                    self.wfile.write(
                        b"--" + BOUNDARY.encode("ascii") + b"\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " +
                        str(len(jpeg)).encode("ascii") + b"\r\n\r\n" +
                        jpeg + b"\r\n")
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

    return StreamHandler


class LiveStreamServer(object):
    """Serve the newest frame as an MJPEG stream in a background thread."""

    def __init__(self, host="0.0.0.0", port=8000):
        self.host = host
        self.port = int(port)
        self.buffer = FrameBuffer()
        self._server = _ThreadingHTTPServer(
            (self.host, self.port), _handler(self.buffer, PAGE))
        self._thread = None

    @property
    def address(self):
        return self._server.server_address

    def start(self):
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        kwargs={"poll_interval": 0.2})
        self._thread.daemon = True
        self._thread.start()
        return self

    def stop(self):
        self.buffer.close()
        try:
            self._server.shutdown()
        finally:
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
