"""Small HTTP API the dashboard polls for events and per-camera state."""
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse


class HomeCommand(BaseModel):
    action: str
    data: dict = Field(default_factory=dict)


def build_app(bus, monitor, snapshot_dir: Path, home=None) -> FastAPI:
    app = FastAPI(title="cctv-alerts")
    # trusted LAN only; the dashboard is served from :1984, a different origin
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

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

    @app.get("/api/home/config")
    def home_config():
        return home.public_config() if home else {"enabled": False, "configured": False, "entities": []}

    @app.get("/api/home/states")
    def home_states():
        if not home or not home.enabled:
            raise HTTPException(status_code=503, detail="Home Assistant is not configured")
        try:
            return home.states()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Home Assistant is unreachable") from exc

    @app.post("/api/home/entities/{item_id}")
    def home_command(item_id: str, command: HomeCommand):
        if not home or not home.enabled:
            raise HTTPException(status_code=503, detail="Home Assistant is not configured")
        try:
            return home.command(item_id, command.action, command.data)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown device") from exc
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Home Assistant command failed") from exc

    return app
