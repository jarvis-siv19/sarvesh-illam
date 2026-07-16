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

    bus = EventBus(snapshot_dir, cfg["snapshot_keep"], [TelegramNotifier()])
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

    app = build_app(bus, monitor, snapshot_dir)
    uvicorn.run(app, host="0.0.0.0", port=cfg["api_port"], log_level="warning")


if __name__ == "__main__":
    main()
