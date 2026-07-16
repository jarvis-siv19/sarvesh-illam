"""Telegram notifier. Runs sends on a worker thread so a slow network
never stalls detection. Without a token it stays silent (the dashboard
event feed still works)."""
import logging
import os
import queue
import threading

import httpx

log = logging.getLogger(__name__)

_KIND_ICON = {
    "down": "📵", "black": "⬛", "covered": "🫣",
    "person": "🚶", "no_helmet": "🪖",
}


class TelegramNotifier:
    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)
        if not self.enabled:
            log.warning("Telegram disabled — TELEGRAM_BOT_TOKEN / "
                        "TELEGRAM_CHAT_ID not set; events go to log + dashboard only")
            return
        self._q: queue.Queue = queue.Queue(maxsize=100)
        threading.Thread(target=self._worker, name="telegram", daemon=True).start()

    def send(self, event, snapshot_dir):
        if not self.enabled:
            return
        try:
            self._q.put_nowait((event, snapshot_dir))
        except queue.Full:
            log.warning("telegram queue full, dropping event %s", event.id)

    def _worker(self):
        api = f"https://api.telegram.org/bot{self.token}"
        client = httpx.Client(timeout=20)
        while True:
            event, snapshot_dir = self._q.get()
            icon = _KIND_ICON.get(event.kind, "⚠️")
            prefix = icon if event.state == "alert" else "✅"
            caption = f"{prefix} {event.message}"
            try:
                if event.snapshot:
                    with open(snapshot_dir / event.snapshot, "rb") as f:
                        r = client.post(f"{api}/sendPhoto",
                                        data={"chat_id": self.chat_id,
                                              "caption": caption},
                                        files={"photo": (event.snapshot, f,
                                                         "image/jpeg")})
                else:
                    r = client.post(f"{api}/sendMessage",
                                    data={"chat_id": self.chat_id,
                                          "text": caption})
                if r.status_code != 200:
                    log.error("telegram %s: %s", r.status_code, r.text[:200])
            except Exception:
                log.exception("telegram send failed")
