"""Per-camera RTSP reader threads.

Each reader decodes its go2rtc sub-stream continuously (352x288 @ 15fps is
cheap) and keeps only the newest frame; detectors sample that at their own
cadence instead of consuming the stream themselves.
"""
import logging
import os
import threading
import time

import cv2

log = logging.getLogger(__name__)

# TCP avoids the packet-loss artifacts UDP RTSP shows on Wi-Fi.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")


class CameraReader(threading.Thread):
    RECONNECT_MIN = 2.0
    RECONNECT_MAX = 30.0

    def __init__(self, name: str, url: str):
        super().__init__(name=f"reader-{name}", daemon=True)
        self.cam = name
        self.url = url
        self._lock = threading.Lock()
        self._frame = None
        self.last_frame_ts = 0.0
        self._stop = threading.Event()

    def latest(self):
        """Newest decoded frame (BGR) and its timestamp, or (None, 0)."""
        with self._lock:
            return self._frame, self.last_frame_ts

    def stop(self):
        self._stop.set()

    def run(self):
        backoff = self.RECONNECT_MIN
        while not self._stop.is_set():
            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap.release()
                log.warning("%s: connect failed, retrying in %.0fs", self.cam, backoff)
                self._stop.wait(backoff)
                backoff = min(backoff * 2, self.RECONNECT_MAX)
                continue
            log.info("%s: connected", self.cam)
            backoff = self.RECONNECT_MIN
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    log.warning("%s: stream ended, reconnecting", self.cam)
                    break
                with self._lock:
                    self._frame = frame
                    self.last_frame_ts = time.time()
            cap.release()
