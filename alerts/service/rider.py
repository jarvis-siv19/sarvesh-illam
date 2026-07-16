"""Rider detection on the parking camera (helmet-check scaffolding).

A "rider" is a person box overlapping a motorcycle box on the configured
camera. Each sighting grabs an HD frame from the camera's main stream and
files it under dataset/riders/ — that archive becomes the training data
for a helmet classifier fine-tuned on this exact camera angle, replacing
the unvetted third-party weights we chose not to load. Until then rider
events surface on the dashboard only (muted for Telegram in config).
"""
import logging
import time
from datetime import datetime
from pathlib import Path

import cv2

log = logging.getLogger(__name__)

MOTORCYCLE = 3  # COCO class id


class RiderWatcher:
    def __init__(self, cfg: dict, bus, base: Path):
        self.h = cfg["helmet"]
        self.camera = self.h["camera"]
        self.label = cfg["cameras"][self.camera]["label"]
        self.rtsp_main = f"{cfg['go2rtc_rtsp']}/{self.camera}"
        self.bus = bus
        self.dataset = base / self.h["dataset_dir"]
        self.dataset.mkdir(parents=True, exist_ok=True)

    def check(self, cam: str, persons, res) -> None:
        """Called by PersonDetector with the already-filtered person boxes
        and the raw result (which still holds motorcycle boxes)."""
        if cam != self.camera or not persons:
            return
        motos = [b for b in res.boxes
                 if int(b.cls) == MOTORCYCLE
                 and float(b.conf) >= self.h["motorcycle_conf"]]
        if not motos:
            return
        riders = [p for p in persons
                  if any(self._overlap(p, m) >= self.h["overlap"] for m in motos)]
        if not riders:
            return

        sub_h, sub_w = res.orig_img.shape[:2]
        hd = self._grab_hd()
        frame = hd if hd is not None else res.orig_img.copy()
        sx, sy = frame.shape[1] / sub_w, frame.shape[0] / sub_h

        if hd is not None:
            name = datetime.now().strftime("%Y%m%d-%H%M%S") + ".jpg"
            cv2.imwrite(str(self.dataset / name), hd,
                        [cv2.IMWRITE_JPEG_QUALITY, 92])
            self._prune()

        for b in riders + motos:
            x1, y1, x2, y2 = (int(v * s) for v, s in
                              zip(map(float, b.xyxy[0]), (sx, sy, sx, sy)))
            color = (60, 60, 255) if int(b.cls) != MOTORCYCLE else (255, 180, 60)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        self.bus.fire(self.camera, self.label, "rider", self.h["cooldown"],
                      f"{self.label}: rider on two-wheeler", frame)

    @staticmethod
    def _overlap(p, m) -> float:
        """Intersection area as a fraction of the person box area."""
        px1, py1, px2, py2 = map(float, p.xyxy[0])
        mx1, my1, mx2, my2 = map(float, m.xyxy[0])
        ix = max(0.0, min(px2, mx2) - max(px1, mx1))
        iy = max(0.0, min(py2, my2) - max(py1, my1))
        parea = max(1.0, (px2 - px1) * (py2 - py1))
        return ix * iy / parea

    def _grab_hd(self):
        """One-shot 720p frame from the main stream (go2rtc dedups the pull)."""
        cap = cv2.VideoCapture(self.rtsp_main, cv2.CAP_FFMPEG)
        try:
            deadline = time.time() + 5
            while time.time() < deadline:
                ok, frame = cap.read()
                if ok:
                    return frame
        finally:
            cap.release()
        log.warning("%s: HD grab failed, using sub frame", self.camera)
        return None

    def _prune(self):
        snaps = sorted(self.dataset.glob("*.jpg"))
        for p in snaps[:-self.h["dataset_keep"]]:
            p.unlink(missing_ok=True)
