"""Camera health + day/night (IR) analysis.

Everything here is plain OpenCV statistics on the newest frame of each
camera — no ML. The IR state feeds every other detector: thresholds differ
between color (day) and IR (night) frames, and health alerts are suppressed
briefly around a flip so the cameras' own mode switch never reads as
"camera covered".
"""
import logging
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

log = logging.getLogger(__name__)


@dataclass
class CamState:
    mode: str = "day"            # "day" | "night"
    mode_since: float = 0.0      # when the current mode was entered
    _pending_mode: str | None = None
    _pending_since: float = 0.0
    # rolling per-mode baselines (EMA): what this camera normally looks like.
    # Judging against its own baseline instead of absolute thresholds matters —
    # e.g. a camera whose IR doesn't reach the scene is legitimately near-black
    # at night, and "black" can only mean anything where there's signal to lose.
    baseline: dict = field(default_factory=lambda: {
        "day": {"luma": 0.0, "sharp": 0.0},
        "night": {"luma": 0.0, "sharp": 0.0}})
    down: bool = False
    black: bool = False
    covered: bool = False

    def to_json(self):
        return {"mode": self.mode, "down": self.down,
                "black": self.black, "covered": self.covered}


def frame_stats(frame) -> tuple[float, float, float]:
    """(mean luma, mean saturation, Laplacian variance) on a downsized frame."""
    small = cv2.resize(frame, (176, 144), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    sat = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)[:, :, 1]
    lap = cv2.Laplacian(gray, cv2.CV_64F).var()
    return float(gray.mean()), float(sat.mean()), float(lap)


class HealthMonitor:
    STARTUP_GRACE = 60  # s to wait for a camera's FIRST frame before "down"

    def __init__(self, cfg: dict, bus, readers: dict):
        self.h = cfg["health"]
        self.n = cfg["night"]
        self.labels = {c: v["label"] for c, v in cfg["cameras"].items()}
        self.bus = bus
        self.readers = readers
        self.states = {cam: CamState(mode_since=time.time()) for cam in readers}
        self.started = time.time()

    def tick(self):
        """Run one health pass over all cameras. Called every ~2s."""
        now = time.time()
        for cam, reader in self.readers.items():
            st = self.states[cam]
            label = self.labels[cam]
            frame, ts = reader.latest()

            # -- down: no fresh frame (readers connect staggered at startup,
            #    so a camera that has never delivered gets a longer leash) --
            if ts == 0.0:
                stale = (now - self.started) > self.STARTUP_GRACE
            else:
                stale = (now - ts) > self.h["down_after"]
            st.down = stale
            self.bus.update_condition(
                cam, label, "down", stale,
                sustain=0, recover_after=self.h["recover_after"],
                cooldown=self.h["cooldown"],
                message=f"{label}: no video — camera or DVR down")
            if stale or frame is None:
                continue

            luma, sat, lap = frame_stats(frame)
            self._update_mode(st, cam, label, sat, now)
            in_grace = (now - st.mode_since) < self.n["flip_grace"]

            base = st.baseline[st.mode]

            # -- black / blinded: brightness collapse vs this camera's norm --
            black = (base["luma"] > self.h["black_min_base"]
                     and luma < base["luma"] * self.h["black_ratio"])
            st.black = black and not in_grace
            self.bus.update_condition(
                cam, label, "black", st.black,
                sustain=self.h["sustain"], recover_after=self.h["recover_after"],
                cooldown=self.h["cooldown"],
                message=f"{label}: image went dark — lens blocked or video lost",
                frame=frame)

            # -- covered: sharpness collapse vs this camera's norm --
            covered = (base["sharp"] > self.h["covered_min_base"]
                       and lap < base["sharp"] * self.h["covered_ratio"])
            st.covered = covered and not black and not in_grace
            self.bus.update_condition(
                cam, label, "covered", st.covered,
                sustain=self.h["sustain"], recover_after=self.h["recover_after"],
                cooldown=self.h["cooldown"],
                message=f"{label}: view obstructed — camera may be covered",
                frame=frame)

            # learn baselines only from healthy frames
            if not black and not covered and not in_grace:
                a = 0.02
                base["luma"] = luma if base["luma"] == 0.0 else base["luma"] * (1 - a) + luma * a
                base["sharp"] = lap if base["sharp"] == 0.0 else base["sharp"] * (1 - a) + lap * a

    def _update_mode(self, st: CamState, cam: str, label: str,
                     sat: float, now: float):
        """Hysteresis day/night flip: the opposite mode must persist ~10s."""
        target = None
        if st.mode == "day" and sat < self.n["saturation_night"]:
            target = "night"
        elif st.mode == "night" and sat > self.n["saturation_day"]:
            target = "day"
        if target is None:
            st._pending_mode, st._pending_since = None, 0.0
            return
        if st._pending_mode != target:
            st._pending_mode, st._pending_since = target, now
            return
        if now - st._pending_since >= 10:
            st.mode, st.mode_since = target, now
            st._pending_mode, st._pending_since = None, 0.0
            log.info("%s: switched to %s mode", label, target.upper())

    def snapshot_states(self):
        return {cam: st.to_json() for cam, st in self.states.items()}
