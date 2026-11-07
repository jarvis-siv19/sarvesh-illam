"""Minimal home-device API; intentionally independent of camera services."""
import logging
import os
from pathlib import Path

import uvicorn

from .api import build_app
from .home import HomeAssistant
from .music import MusicReactive
from .settings import load_config
from .smarteefi import SmarteefiProvider


class _NoCameraBus:
    def recent(self, _limit):
        return []


class _NoCameraMonitor:
    def snapshot_states(self):
        return {}


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname).3s %(name)s: %(message)s",
        datefmt="%H:%M:%S")
    config_dir = Path(os.environ.get("SARVESH_CONFIG_DIR", "/config"))
    data_dir = Path(os.environ.get("SARVESH_DATA_DIR", "/data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(config_dir)
    smarteefi = SmarteefiProvider(cfg.get("smarteefi", {}))
    home = HomeAssistant(cfg.get("home_assistant", {}), data_dir / "home-layout.json",
                         providers=[smarteefi])
    music = MusicReactive(home, cfg.get("music_reactive", {}))
    app = build_app(_NoCameraBus(), _NoCameraMonitor(), data_dir, home, music)
    port = int(os.environ.get("HOME_API_PORT", "8090"))
    logging.getLogger(__name__).info(
        "Home API ready on port %d (%d local provider(s))", port, len(home.providers))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
