"""Person detection over all cameras with YOLO11n.

One model instance, all cameras batched per pass. Frames come from the
readers' latest-frame buffers, so detection cadence is independent of the
15fps streams. A person must persist across consecutive passes before an
alert fires, and each camera then goes quiet for a cooldown period.
"""
import logging
import time
from pathlib import Path

import cv2

log = logging.getLogger(__name__)

PERSON = 0  # COCO class id


class PersonDetector:
    def __init__(self, cfg: dict, bus, readers: dict, monitor, base: Path):
        self.d = cfg["detection"]
        self.cams = [c for c, v in cfg["cameras"].items() if v.get("person_alerts")]
        self.labels = {c: v["label"] for c, v in cfg["cameras"].items()}
        self.bus = bus
        self.readers = readers
        self.monitor = monitor
        self.hits: dict[str, int] = {c: 0 for c in self.cams}

        from ultralytics import YOLO
        weights = base / "models" / self.d["model"]
        weights.parent.mkdir(exist_ok=True)
        self.model = YOLO(str(weights))  # auto-downloads on first run
        log.info("YOLO loaded: %s", self.d["model"])

    def tick(self):
        batch, order = [], []
        for cam in self.cams:
            st = self.monitor.states[cam]
            if st.down or st.black:
                self.hits[cam] = 0
                continue
            frame, ts = self.readers[cam].latest()
            if frame is None or time.time() - ts > 5:
                self.hits[cam] = 0
                continue
            batch.append(frame)
            order.append(cam)
        if not batch:
            return

        results = self.model(batch, classes=[PERSON], imgsz=self.d["imgsz"],
                             conf=min(self.d["conf_day"], self.d["conf_night"]),
                             verbose=False)

        for cam, res in zip(order, results):
            st = self.monitor.states[cam]
            conf_needed = (self.d["conf_night"] if st.mode == "night"
                           else self.d["conf_day"])
            boxes = [b for b in res.boxes if float(b.conf) >= conf_needed]
            if not boxes:
                self.hits[cam] = 0
                continue
            self.hits[cam] += 1
            if self.hits[cam] < self.d["consecutive"]:
                continue
            label = self.labels[cam]
            n = len(boxes)
            frame = res.orig_img.copy()
            for b in boxes:
                x1, y1, x2, y2 = map(int, b.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (60, 60, 255), 2)
                cv2.putText(frame, f"{float(b.conf):.2f}", (x1, max(12, y1 - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60, 60, 255), 1)
            who = "person" if n == 1 else f"{n} people"
            self.bus.fire(cam, label, "person", self.d["cooldown"],
                          f"{label}: {who} detected ({st.mode})", frame)
