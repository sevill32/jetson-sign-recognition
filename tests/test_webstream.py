import os
import sys
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from signrec.webstream import FrameBuffer, LiveStreamServer

JPEG = b"\xff\xd8\xff\xe0fake-jpeg\xff\xd9"


class FrameBufferTest(unittest.TestCase):
    def test_publish_and_latest(self):
        buffer = FrameBuffer()
        self.assertEqual(buffer.latest(), (None, 0))
        buffer.publish(JPEG)
        self.assertEqual(buffer.latest(), (JPEG, 1))

    def test_wait_for_next_returns_new_frame(self):
        buffer = FrameBuffer()
        buffer.publish(JPEG)
        frame, sequence = buffer.wait_for_next(0, timeout=0.1)
        self.assertEqual(frame, JPEG)
        self.assertEqual(sequence, 1)

    def test_close_releases_waiters(self):
        buffer = FrameBuffer()
        buffer.close()
        frame, sequence = buffer.wait_for_next(0, timeout=0.1)
        self.assertIsNone(frame)
        self.assertEqual(sequence, 0)


class LiveStreamServerTest(unittest.TestCase):
    def setUp(self):
        self.server = LiveStreamServer(host="127.0.0.1", port=0).start()
        self.base = "http://127.0.0.1:%d" % self.server.address[1]

    def tearDown(self):
        self.server.stop()

    def test_index_page(self):
        with urllib.request.urlopen(self.base + "/", timeout=3) as response:
            body = response.read().decode("utf-8")
        self.assertIn("/stream.mjpg", body)

    def test_snapshot_returns_latest_frame(self):
        self.server.buffer.publish(JPEG)
        with urllib.request.urlopen(self.base + "/snapshot.jpg",
                                    timeout=3) as response:
            self.assertEqual(response.read(), JPEG)

    def test_health(self):
        with urllib.request.urlopen(self.base + "/health",
                                    timeout=3) as response:
            self.assertEqual(response.read(), b"ok")

    def test_unknown_path_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(self.base + "/missing", timeout=3)
        self.assertEqual(context.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
