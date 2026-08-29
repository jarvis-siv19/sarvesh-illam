"""Single-owner, microphone-driven light control for the local dashboard."""
import threading
import time
from typing import Any

from .home import HomeAssistant


class MusicReactive:
    """Accept audio levels from one dashboard while keeping HA writes server-side."""

    def __init__(self, home: HomeAssistant, config: dict[str, Any] | None = None):
        config = config or {}
        self.home = home
        self.light_id = config.get("light_id", "philips_bulb")
        self.timeout = max(5, min(60, int(config.get("source_timeout", 12))))
        self._lock = threading.Lock()
        self._owner: dict[str, str] | None = None
        self._expires = 0.0
        self._last_write = 0.0
        self._last_colour = 0.0

    def _clear_expired(self) -> None:
        if self._owner and time.monotonic() >= self._expires:
            self._owner = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._clear_expired()
            return {"active": bool(self._owner), "owner": self._owner,
                    "expires_in": max(0, round(self._expires - time.monotonic(), 1)) if self._owner else 0}

    def claim(self, client_id: str, name: str, take_over: bool = False) -> dict[str, Any]:
        with self._lock:
            self._clear_expired()
            if self._owner and self._owner["id"] != client_id and not take_over:
                raise PermissionError("Music reactive mode is already running on another device")
            self._owner = {"id": client_id, "name": name[:60] or "This device"}
            self._expires = time.monotonic() + self.timeout
        return self.status()

    def stop(self, client_id: str, take_over: bool = False) -> dict[str, Any]:
        with self._lock:
            self._clear_expired()
            if self._owner and self._owner["id"] != client_id and not take_over:
                raise PermissionError("Only the active audio source can stop this mode")
            self._owner = None
        return self.status()

    def update(self, client_id: str, level: float, beat: bool, hue: int) -> dict[str, Any]:
        with self._lock:
            self._clear_expired()
            if not self._owner or self._owner["id"] != client_id:
                raise PermissionError("This device is not the active audio source")
            self._expires = time.monotonic() + self.timeout
            now = time.monotonic()
            if now - self._last_write < 0.28:
                return self.status()
            self._last_write = now
            brightness = max(8, min(100, round(12 + max(0.0, min(1.0, level)) * 88)))
            data: dict[str, Any] = {"brightness_pct": brightness}
            if beat and now - self._last_colour > 0.8:
                self._last_colour = now
                data["rgb_color"] = self._hsv_to_rgb(hue % 360, 0.82, 1.0)
        self.home.command(self.light_id, "set", data)
        return self.status()

    @staticmethod
    def _hsv_to_rgb(hue: int, saturation: float, value: float) -> list[int]:
        chroma = value * saturation
        x = chroma * (1 - abs((hue / 60) % 2 - 1))
        m = value - chroma
        r, g, b = ((chroma, x, 0) if hue < 60 else (x, chroma, 0) if hue < 120 else
                   (0, chroma, x) if hue < 180 else (0, x, chroma) if hue < 240 else
                   (x, 0, chroma) if hue < 300 else (chroma, 0, x))
        return [round((component + m) * 255) for component in (r, g, b)]
