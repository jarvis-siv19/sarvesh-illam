"""Entry point: wire readers → health monitor → event bus → Telegram + API."""
import logging
import threading
import time
from pathlib import Path

import uvicorn
import yaml

from .api import build_app
from .events import EventBus
from .health import HealthMonitor
from .home import HomeAssistant
from .music import MusicReactive
from .home_notify import HomeAssistantNotifier
from .notify import TelegramNotifier
from .reader import CameraReader

log = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent.parent  # alerts/


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname).3s %(name)s: %(message)s",
        datefmt="%H:%M:%S")

    cfg = yaml.safe_load((BASE / "config.yaml").read_text())
    snapshot_dir = BASE / cfg["snapshot_dir"]

    readers = {
        cam: CameraReader(cam, f"{cfg['go2rtc_rtsp']}/{cam}_sub")
        for cam in cfg["cameras"]
    }
    for r in readers.values():
        r.start()

    home = HomeAssistant(cfg.get("home_assistant", {}), BASE / "home-layout.json")
    music = MusicReactive(home, cfg.get("music_reactive", {}))
    notifier = TelegramNotifier(cfg.get("telegram", {}).get("mute_kinds", ()))
    bus = EventBus(snapshot_dir, cfg["snapshot_keep"], [notifier, HomeAssistantNotifier(home)])
    monitor = HealthMonitor(cfg, bus, readers)

    def health_loop():
        # let streams connect and the sharpness baseline start forming
        time.sleep(10)
        while True:
            try:
                monitor.tick()
            except Exception:
                log.exception("health tick failed")
            time.sleep(2)

    threading.Thread(target=health_loop, name="health", daemon=True).start()

    def person_loop():
        from .person import PersonDetector
        from .rider import RiderWatcher
        det = PersonDetector(cfg, bus, readers, monitor, BASE,
                             rider=RiderWatcher(cfg, bus, BASE))
        time.sleep(10)
        while True:
            t0 = time.time()
            try:
                det.tick()
            except Exception:
                log.exception("person tick failed")
            time.sleep(max(0.1, cfg["detection"]["interval"] - (time.time() - t0)))

    threading.Thread(target=person_loop, name="person", daemon=True).start()

    app = build_app(bus, monitor, snapshot_dir, home, music)
    uvicorn.run(app, host="0.0.0.0", port=cfg["api_port"], log_level="warning")


if __name__ == "__main__":
    main()
