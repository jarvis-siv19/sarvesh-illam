import sys
import types
import unittest

sys.modules.setdefault("cv2", types.SimpleNamespace())

from service import reader as reader_module
from service.reader import CameraReader


class FailedCapture:
    def isOpened(self):
        return False

    def release(self):
        pass


class EmptyCapture(FailedCapture):
    def isOpened(self):
        return True

    def read(self):
        return False, None


class ParameterCapture:
    def __init__(self):
        self.open_args = None

    def open(self, *args):
        self.open_args = args


class RecordingStop:
    def __init__(self):
        self.delays = []

    def is_set(self):
        return len(self.delays) >= 3

    def wait(self, delay):
        self.delays.append(delay)
        return False


class CameraRetryTests(unittest.TestCase):
    def test_failed_camera_moves_to_quiet_background_retry(self):
        reader = CameraReader("cam1", "rtsp://offline", fast_retries=3,
                              offline_retry=120, open_timeout=5)
        reader._open_capture = FailedCapture
        reader._stop = RecordingStop()

        reader.run()

        self.assertEqual(reader._stop.delays, [2.0, 4.0, 120.0])
        self.assertTrue(reader.offline)
        self.assertEqual(reader.retry_in, 120.0)

    def test_open_stream_without_frames_uses_same_quiet_retry(self):
        reader = CameraReader("cam1", "rtsp://offline", fast_retries=3,
                              offline_retry=120, open_timeout=5)
        reader._open_capture = EmptyCapture
        reader._stop = RecordingStop()

        reader.run()

        self.assertEqual(reader._stop.delays, [2.0, 4.0, 120.0])
        self.assertTrue(reader.offline)

    def test_open_and_read_timeouts_are_passed_to_ffmpeg(self):
        capture = ParameterCapture()
        original_cv2 = reader_module.cv2
        reader_module.cv2 = types.SimpleNamespace(
            VideoCapture=lambda: capture,
            CAP_PROP_OPEN_TIMEOUT_MSEC=53,
            CAP_PROP_READ_TIMEOUT_MSEC=54,
            CAP_FFMPEG=1900,
        )
        try:
            reader = CameraReader("cam1", "rtsp://offline", open_timeout=5)
            self.assertIs(reader._open_capture(), capture)
        finally:
            reader_module.cv2 = original_cv2

        self.assertEqual(capture.open_args, (
            "rtsp://offline", 1900, [53, 5000, 54, 5000]))


if __name__ == "__main__":
    unittest.main()
