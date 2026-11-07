"""Entry point: wire readers → health monitor → event bus → Telegram + API."""
import logging
import os
import threading
import time
from pathlib import Path

import uvicorn
from .api import build_app
from .events import EventBus
from .health import HealthMonitor
from .home import HomeAssistant
from .smarteefi import SmarteefiProvider
from .music import MusicReactive
from .home_notify import HomeAssistantNotifier
from .notify import TelegramNotifier
from .reader import CameraReader
from .settings import load_config

log = logging.getLogger(__name__)

BASE = Path(os.environ.get("SARVESH_CONFIG_DIR", Path(__file__).resolve().parent.parent))
DATA = Path(os.environ.get("SARVESH_DATA_DIR", BASE))


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname).3s %(name)s: %(message)s",
        datefmt="%H:%M:%S")

    cfg = load_config(BASE)
    cfg["go2rtc_rtsp"] = os.environ.get("GO2RTC_RTSP", cfg["go2rtc_rtsp"])
    snapshot_dir = DATA / cfg["snapshot_dir"]
    reconnect = cfg.get("camera_reconnect", {})

    readers = {
        cam: CameraReader(
            cam,
            f"{cfg['go2rtc_rtsp']}/{cam}_sub",
            fast_retries=reconnect.get("fast_retries", 3),
            offline_retry=reconnect.get("offline_retry", 300),
            open_timeout=reconnect.get("open_timeout", 5),
        )
        for cam in cfg["cameras"]
    }
    for r in readers.values():
        r.start()

    home_enabled = os.environ.get("ALERTS_HOME_ENABLED", "1") != "0"
    smarteefi = SmarteefiProvider(cfg.get("smarteefi", {})) if home_enabled else None
    home = HomeAssistant(cfg.get("home_assistant", {}), DATA / "home-layout.json",
                         providers=[smarteefi] if smarteefi else []) if home_enabled else None
    music = MusicReactive(home, cfg.get("music_reactive", {})) if home else None
    notifier = TelegramNotifier(cfg.get("telegram", {}).get("mute_kinds", ()))
    notifiers = [notifier]
    if home:
        notifiers.append(HomeAssistantNotifier(home))
    bus = EventBus(snapshot_dir, cfg["snapshot_keep"], notifiers)
    monitor = HealthMonitor(cfg, bus, readers)

    def health_loop():
        # Camera connection runs independently; publish offline state promptly.
        time.sleep(1)
        while True:
            try:
                monitor.tick()
            except Exception:
                log.exception("health tick failed")
            time.sleep(2)

    threading.Thread(target=health_loop, name="health", daemon=True).start()

    def person_loop():
        log.info("Person detection waiting for the first available camera frame")
        while not any(reader.latest()[0] is not None for reader in readers.values()):
            time.sleep(10)
        from .person import PersonDetector
        from .rider import RiderWatcher
        det = PersonDetector(cfg, bus, readers, monitor, DATA,
                             rider=RiderWatcher(cfg, bus, DATA))
        log.info("Camera frame available; person detection started")
        while True:
            t0 = time.time()
            try:
                det.tick()
            except Exception:
                log.exception("person tick failed")
            time.sleep(max(0.1, cfg["detection"]["interval"] - (time.time() - t0)))

    threading.Thread(target=person_loop, name="person", daemon=True).start()

    app = build_app(bus, monitor, snapshot_dir, home, music)
    port = int(os.environ.get("ALERTS_API_PORT", cfg["api_port"]))
    log.info("Alerts API ready on port %s; camera retries run in the background", port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
