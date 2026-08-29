"""Home Assistant boundary for Sarvesh Illam.

The browser never receives the Home Assistant access token. This module keeps
the dashboard on a deliberately small allow-list of configured entities.
"""
import logging
import os
from typing import Any

import httpx

log = logging.getLogger(__name__)


class HomeAssistant:
    def __init__(self, config: dict[str, Any]):
        self.config = config or {}
        self.url = os.environ.get("HOME_ASSISTANT_URL", "").rstrip("/")
        self.token = os.environ.get("HOME_ASSISTANT_TOKEN", "")
        self.entities = {item["id"]: item for item in self.config.get("entities", [])
                         if item.get("id") and item.get("entity_id")}

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.token and self.entities)

    def public_config(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "configured": bool(self.entities),
                "entities": [{k: v for k, v in item.items()
                              if k in {"id", "entity_id", "name", "room", "icon", "type"}}
                             for item in self.entities.values()]}

    def _client(self):
        if not self.enabled:
            raise RuntimeError("Home Assistant is not configured")
        return httpx.Client(base_url=self.url, timeout=8,
                            headers={"Authorization": f"Bearer {self.token}"})

    def states(self) -> list[dict[str, Any]]:
        with self._client() as client:
            result = []
            for item in self.entities.values():
                response = client.get(f"/api/states/{item['entity_id']}")
                response.raise_for_status()
                raw = response.json()
                result.append({"id": item["id"], "entity_id": item["entity_id"],
                               "name": item.get("name", item["id"]),
                               "room": item.get("room", "Home"),
                               "icon": item.get("icon", "⌂"),
                               "type": item.get("type", item["entity_id"].split(".")[0]),
                               "state": raw.get("state", "unknown"),
                               "attributes": raw.get("attributes", {})})
            return result

    def command(self, item_id: str, action: str, data: dict[str, Any] | None = None):
        item = self.entities.get(item_id)
        if not item:
            raise KeyError(item_id)
        domain = item["entity_id"].split(".", 1)[0]
        if domain not in {"light", "switch"}:
            raise ValueError("this entity is read-only")
        allowed = {"turn_on", "turn_off"}
        if domain == "light":
            allowed.add("set")
        if action not in allowed:
            raise ValueError("unsupported action")
        payload: dict[str, Any] = {"entity_id": item["entity_id"]}
        if action == "set":
            data = data or {}
            if "brightness_pct" in data:
                payload["brightness_pct"] = max(1, min(100, int(data["brightness_pct"])))
            if "color_temp_kelvin" in data:
                payload["color_temp_kelvin"] = max(1500, min(6500, int(data["color_temp_kelvin"])))
            if "rgb_color" in data and isinstance(data["rgb_color"], list) and len(data["rgb_color"]) == 3:
                payload["rgb_color"] = [max(0, min(255, int(v))) for v in data["rgb_color"]]
            service = "turn_on"
        else:
            service = action
        with self._client() as client:
            response = client.post(f"/api/services/{domain}/{service}", json=payload)
            response.raise_for_status()
        return {"ok": True}

    def publish_event(self, event) -> None:
        if not self.enabled or not self.config.get("publish_camera_events", False):
            return
        try:
            with self._client() as client:
                response = client.post("/api/events/sarvesh_illam_camera_alert",
                    json={"camera": event.camera, "label": event.label,
                          "kind": event.kind, "state": event.state,
                          "message": event.message, "timestamp": event.ts})
                response.raise_for_status()
        except Exception:
            log.exception("Home Assistant camera event publish failed")
