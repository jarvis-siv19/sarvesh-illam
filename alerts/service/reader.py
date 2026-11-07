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

    def __init__(self, name: str, url: str, *, fast_retries: int = 3,
                 offline_retry: float = 300.0, open_timeout: float = 5.0):
        super().__init__(name=f"reader-{name}", daemon=True)
        self.cam = name
        self.url = url
        self.fast_retries = max(1, int(fast_retries))
        self.offline_retry = max(30.0, float(offline_retry))
        self.open_timeout = max(1.0, min(30.0, float(open_timeout)))
        self._lock = threading.Lock()
        self._frame = None
        self.last_frame_ts = 0.0
        self._stop = threading.Event()
        self.failures = 0
        self.offline = False
        self.retry_in = 0.0

    def latest(self):
        """Newest decoded frame (BGR) and its timestamp, or (None, 0)."""
        with self._lock:
            return self._frame, self.last_frame_ts

    def stop(self):
        self._stop.set()

    def _open_capture(self):
        """Open RTSP with a bounded timeout so one DVR cannot stall startup."""
        cap = cv2.VideoCapture()
        open_timeout = getattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC", None)
        read_timeout = getattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC", None)
        params = []
        if open_timeout is not None:
            params.extend((open_timeout, round(self.open_timeout * 1000)))
        if read_timeout is not None:
            params.extend((read_timeout, round(self.open_timeout * 1000)))
        if params:
            cap.open(self.url, cv2.CAP_FFMPEG, params)
        else:
            cap.open(self.url, cv2.CAP_FFMPEG)
        return cap

    def _wait_after_failure(self, backoff: float, reason: str) -> float:
        self.failures += 1
        self.offline = self.failures >= self.fast_retries
        delay = self.offline_retry if self.offline else backoff
        self.retry_in = delay
        if self.offline:
            log.warning(
                "%s: offline after %d attempts (%s); dashboard remains available; "
                "retrying in %.0fs", self.cam, self.failures, reason, delay)
        else:
            log.warning("%s: %s, retrying in %.0fs", self.cam, reason, delay)
        self._stop.wait(delay)
        return min(backoff * 2, self.RECONNECT_MAX)

    def run(self):
        backoff = self.RECONNECT_MIN
        while not self._stop.is_set():
            cap = self._open_capture()
            if not cap.isOpened():
                cap.release()
                backoff = self._wait_after_failure(backoff, "connect failed")
                continue
            received_frame = False
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    break
                if not received_frame:
                    received_frame = True
                    self.failures = 0
                    self.offline = False
                    self.retry_in = 0.0
                    backoff = self.RECONNECT_MIN
                    log.info("%s: connected", self.cam)
                with self._lock:
                    self._frame = frame
                    self.last_frame_ts = time.time()
            cap.release()
            if not self._stop.is_set():
                reason = "stream ended" if received_frame else "connected but no frames arrived"
                backoff = self._wait_after_failure(backoff, reason)
