"""Event pipeline: alert/recover state per (camera, kind), cooldowns,
a ring buffer for the dashboard, JPEG snapshots, and notifier fan-out.
"""
import itertools
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2

log = logging.getLogger(__name__)


@dataclass
class Event:
    id: int
    ts: float
    camera: str
    label: str
    kind: str          # "down" | "black" | "covered" | "person" | "no_helmet"
    state: str         # "alert" | "recover"
    message: str
    snapshot: str | None = None   # filename under snapshot_dir

    def to_json(self):
        return {
            "id": self.id, "ts": self.ts, "camera": self.camera,
            "label": self.label, "kind": self.kind, "state": self.state,
            "message": self.message, "snapshot": self.snapshot,
        }


@dataclass
class _Track:
    """Alert lifecycle for one (camera, kind)."""
    active: bool = False
    since: float = 0.0          # when the raw condition started being true/false
    last_alert: float = 0.0


class EventBus:
    def __init__(self, snapshot_dir: Path, snapshot_keep: int, notifiers):
        self.snapshot_dir = snapshot_dir
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_keep = snapshot_keep
        self.notifiers = notifiers
        self._ids = itertools.count(int(time.time()))
        self._lock = threading.Lock()
        self._ring: list[Event] = []
        self._tracks: dict[tuple[str, str], _Track] = {}

    # ---- sustained-condition state machine (camera health) ----

    def update_condition(self, camera: str, label: str, kind: str, raw: bool,
                         sustain: float, recover_after: float, cooldown: float,
                         message: str, frame=None) -> None:
        """Feed the current raw condition; emits alert/recover events once the
        condition has held long enough, with a per-(camera,kind) cooldown."""
        now = time.time()
        t = self._tracks.setdefault((camera, kind), _Track())
        if not t.active:
            if raw:
                if t.since == 0.0:
                    t.since = now
                if now - t.since >= sustain and now - t.last_alert >= cooldown:
                    t.active = True
                    t.last_alert = now
                    t.since = 0.0
                    self.emit(camera, label, kind, "alert", message, frame)
            else:
                t.since = 0.0
        else:
            if not raw:
                if t.since == 0.0:
                    t.since = now
                if now - t.since >= recover_after:
                    t.active = False
                    t.since = 0.0
                    self.emit(camera, label, kind, "recover",
                              f"{label}: {kind} cleared", None)
            else:
                t.since = 0.0

    # ---- instantaneous events with cooldown (person, helmet) ----

    def fire(self, camera: str, label: str, kind: str, cooldown: float,
             message: str, frame=None) -> bool:
        now = time.time()
        t = self._tracks.setdefault((camera, kind), _Track())
        if now - t.last_alert < cooldown:
            return False
        t.last_alert = now
        self.emit(camera, label, kind, "alert", message, frame)
        return True

    # ---- plumbing ----

    def emit(self, camera, label, kind, state, message, frame=None):
        ev = Event(next(self._ids), time.time(), camera, label, kind, state, message)
        if frame is not None:
            ev.snapshot = f"{ev.id}.jpg"
            cv2.imwrite(str(self.snapshot_dir / ev.snapshot), frame,
                        [cv2.IMWRITE_JPEG_QUALITY, 85])
            self._prune()
        with self._lock:
            self._ring.append(ev)
            del self._ring[:-500]
        log.info("EVENT %s %s/%s: %s", state.upper(), camera, kind, message)
        for n in self.notifiers:
            try:
                n.send(ev, self.snapshot_dir)
            except Exception:
                log.exception("notifier %s failed", type(n).__name__)

    def recent(self, limit=50):
        with self._lock:
            return [e.to_json() for e in self._ring[-limit:]][::-1]

    def _prune(self):
        snaps = sorted(self.snapshot_dir.glob("*.jpg"))
        for p in snaps[:-self.snapshot_keep]:
            p.unlink(missing_ok=True)
