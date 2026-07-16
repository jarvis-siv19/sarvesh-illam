"""Small HTTP API the dashboard polls for events and per-camera state."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse


def build_app(bus, monitor, snapshot_dir: Path) -> FastAPI:
    app = FastAPI(title="cctv-alerts")
    # trusted LAN only; the dashboard is served from :1984, a different origin
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])

    @app.get("/api/events")
    def events(limit: int = 50):
        return bus.recent(min(limit, 200))

    @app.get("/api/health")
    def health():
        return monitor.snapshot_states()

    @app.get("/api/snapshots/{name}")
    def snapshot(name: str):
        p = (snapshot_dir / name).resolve()
        if p.parent != snapshot_dir.resolve() or not p.is_file():
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(p, media_type="image/jpeg")

    return app
