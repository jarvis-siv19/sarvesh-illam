"""Non-blocking optional publisher for CCTV events into Home Assistant."""
import queue
import threading


class HomeAssistantNotifier:
    def __init__(self, home):
        self.home = home
        self.enabled = home.enabled and home.config.get("publish_camera_events", False)
        if self.enabled:
            self._queue: queue.Queue = queue.Queue(maxsize=100)
            threading.Thread(target=self._worker, name="home-assistant", daemon=True).start()

    def send(self, event, _snapshot_dir):
        if not self.enabled:
            return
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            pass

    def _worker(self):
        while True:
            self.home.publish_event(self._queue.get())
