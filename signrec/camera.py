"""Camera sources for Jetson Nano.

The stock JetPack OpenCV 3.2 is built without GStreamer support, therefore
cv2.VideoCapture() cannot open the CSI camera. The CSI backend below uses
GStreamer/Argus directly through PyGObject and an appsink. A USB webcam
backend based on cv2.VideoCapture is also provided.
"""

import cv2
import numpy as np


class CameraError(RuntimeError):
    pass


FLIP_CODES = {
    "none": None,
    "horizontal": 1,
    "vertical": 0,
    "rotate180": -1,
}


def _apply_flip(frame, flip):
    if frame is None:
        return frame
    code = FLIP_CODES.get(flip)
    if code is None:
        return frame
    return cv2.flip(frame, code)


class GStreamerCamera(object):
    def __init__(self, sensor_id=0, width=1280, height=720, fps=30,
                 process_width=640, flip="none"):
        self.sensor_id = int(sensor_id)
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)
        self.process_width = int(process_width)
        self.flip = flip
        self.output_width = self.process_width
        self.output_height = int(round(
            self.height * self.output_width / float(self.width) / 2.0) * 2)
        self._pipeline = None
        self._sink = None
        self._gst = None

    def open(self):
        try:
            import gi
            gi.require_version("Gst", "1.0")
            from gi.repository import Gst
        except Exception as exc:
            raise CameraError(
                "PyGObject/GStreamer tidak tersedia: %s" % exc)

        Gst.init(None)
        self._gst = Gst
        description = (
            "nvarguscamerasrc sensor-id=%d ! "
            "video/x-raw(memory:NVMM),width=%d,height=%d,framerate=%d/1 ! "
            "nvvidconv ! "
            "video/x-raw,format=BGRx,width=%d,height=%d ! "
            "appsink name=signrec_sink max-buffers=1 drop=true sync=false"
        ) % (self.sensor_id, self.width, self.height, self.fps,
             self.output_width, self.output_height)

        try:
            self._pipeline = Gst.parse_launch(description)
        except Exception as exc:
            raise CameraError("Gagal membuat pipeline GStreamer: %s" % exc)

        self._sink = self._pipeline.get_by_name("signrec_sink")
        if self._sink is None:
            raise CameraError("appsink tidak ditemukan pada pipeline")

        result = self._pipeline.set_state(Gst.State.PLAYING)
        if result == Gst.StateChangeReturn.FAILURE:
            self._pipeline.set_state(Gst.State.NULL)
            raise CameraError("Pipeline GStreamer gagal masuk state PLAYING")

        result, state, pending = self._pipeline.get_state(8 * Gst.SECOND)
        if result == Gst.StateChangeReturn.FAILURE:
            self._pipeline.set_state(Gst.State.NULL)
            raise CameraError("Kamera CSI gagal start (cek nvargus-daemon)")
        return self

    def read(self):
        if self._sink is None:
            return None
        Gst = self._gst
        sample = None
        if hasattr(self._sink, "try_pull_sample"):
            sample = self._sink.try_pull_sample(2 * Gst.SECOND)
        else:
            sample = self._sink.emit("pull-sample")
        if sample is None:
            return None

        buffer = sample.get_buffer()
        mapped, info = buffer.map(Gst.MapFlags.READ)
        if not mapped:
            return None
        try:
            caps = sample.get_caps().get_structure(0)
            width = int(caps.get_value("width"))
            height = int(caps.get_value("height"))
            array = np.ndarray(shape=(height, width, 4), dtype=np.uint8,
                               buffer=info.data)
            frame = array[:, :, :3].copy()
        finally:
            buffer.unmap(info)
        return _apply_flip(frame, self.flip)

    def release(self):
        if self._pipeline is not None:
            self._pipeline.set_state(self._gst.State.NULL)
            self._pipeline = None
            self._sink = None


class UsbCamera(object):
    def __init__(self, index=0, width=1280, height=720, fps=30, flip="none"):
        self.index = int(index)
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)
        self.flip = flip
        self._capture = None

    def open(self):
        self._capture = cv2.VideoCapture(self.index)
        if not self._capture.isOpened():
            raise CameraError("Webcam USB index %d tidak dapat dibuka" %
                              self.index)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._capture.set(cv2.CAP_PROP_FPS, self.fps)
        return self

    def read(self):
        if self._capture is None:
            return None
        ok, frame = self._capture.read()
        if not ok:
            return None
        return _apply_flip(frame, self.flip)

    def release(self):
        if self._capture is not None:
            self._capture.release()
            self._capture = None


class VideoFileCamera(object):
    """Offline video source used for demos and repeatable pipeline tests."""

    def __init__(self, path, flip="none", loop=True):
        self.path = path
        self.flip = flip
        self.loop = loop
        self._capture = None

    def open(self):
        self._capture = cv2.VideoCapture(self.path)
        if not self._capture.isOpened():
            raise CameraError("Video tidak dapat dibuka: %s" % self.path)
        return self

    def read(self):
        if self._capture is None:
            return None
        ok, frame = self._capture.read()
        if not ok and self.loop:
            self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._capture.read()
        if not ok:
            return None
        return _apply_flip(frame, self.flip)

    def release(self):
        if self._capture is not None:
            self._capture.release()
            self._capture = None


def open_camera(config, kind=None, sensor_id=None, usb_index=None,
                flip=None, video_path=None):
    camera = config["camera"]
    kind = (kind or camera.get("type", "csi")).lower()
    flip_override = flip
    if kind == "video":
        if not video_path:
            raise CameraError("Sumber video membutuhkan --video PATH")
        video_flip = flip_override if flip_override is not None else "none"
        return VideoFileCamera(video_path, flip=video_flip).open()
    flip = flip_override if flip_override is not None else camera.get(
        "flip", "none")
    if kind == "usb":
        index = camera.get("usb_index", 0) if usb_index is None else usb_index
        return UsbCamera(index=index, width=camera.get("width", 1280),
                         height=camera.get("height", 720),
                         fps=camera.get("fps", 30),
                         flip=flip).open()
    if kind == "csi":
        sensor = camera.get("sensor_id", 0) if sensor_id is None else sensor_id
        return GStreamerCamera(
            sensor_id=sensor,
            width=camera.get("width", 1280),
            height=camera.get("height", 720),
            fps=camera.get("fps", 30),
            process_width=camera.get("process_width", 640),
            flip=flip).open()
    raise CameraError("Tipe kamera tidak dikenal: %s" % kind)
