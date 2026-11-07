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
from .smarteefi import SmarteefiProvider
from .music import MusicReactive
from .home_notify import HomeAssistantNotifier
from .notify import TelegramNotifier
from .reader import CameraReader

log = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent.parent  # alerts/


def _merge_config(base, override):
    """Recursively merge a per-house local config over tracked defaults."""
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override
    merged = base.copy()
    for key, value in override.items():
        merged[key] = _merge_config(merged[key], value) if key in merged else value
    return merged


def load_config():
    config = yaml.safe_load((BASE / "config.yaml").read_text()) or {}
    local_path = BASE / "config.local.yaml"
    if local_path.is_file():
        config = _merge_config(config, yaml.safe_load(local_path.read_text()) or {})
    return config


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname).3s %(name)s: %(message)s",
        datefmt="%H:%M:%S")

    cfg = load_config()
    snapshot_dir = BASE / cfg["snapshot_dir"]
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

    smarteefi = SmarteefiProvider(cfg.get("smarteefi", {}))
    home = HomeAssistant(cfg.get("home_assistant", {}), BASE / "home-layout.json",
                         providers=[smarteefi])
    music = MusicReactive(home, cfg.get("music_reactive", {}))
    notifier = TelegramNotifier(cfg.get("telegram", {}).get("mute_kinds", ()))
    bus = EventBus(snapshot_dir, cfg["snapshot_keep"], [notifier, HomeAssistantNotifier(home)])
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
        det = PersonDetector(cfg, bus, readers, monitor, BASE,
                             rider=RiderWatcher(cfg, bus, BASE))
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
    log.info("Home dashboard API ready on port %s; camera retries run in the background",
             cfg["api_port"])
    uvicorn.run(app, host="0.0.0.0", port=cfg["api_port"], log_level="warning")


if __name__ == "__main__":
    main()
