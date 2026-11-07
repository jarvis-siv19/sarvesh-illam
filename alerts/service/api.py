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


class HomeEntityCreate(BaseModel):
    entity_id: str
    name: str | None = None
    room: str | None = None
    icon: str | None = None


class HomeEntityEdit(BaseModel):
    name: str | None = None
    room: str | None = None
    icon: str | None = None


class RoomName(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class MusicClaim(BaseModel):
    client_id: str = Field(min_length=8, max_length=120)
    name: str = Field(default="This device", max_length=60)
    take_over: bool = False


class MusicLevel(BaseModel):
    client_id: str = Field(min_length=8, max_length=120)
    level: float = Field(ge=0, le=1)
    beat: bool = False
    hue: int = Field(default=210, ge=0, le=359)


def build_app(bus, monitor, snapshot_dir: Path, home=None, music=None) -> FastAPI:
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
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="A home device provider is unreachable") from exc

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
        except (httpx.HTTPError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail="Device command failed") from exc

    @app.post("/api/home/entities")
    def home_add_entity(entity: HomeEntityCreate):
        if not home or not home.enabled:
            raise HTTPException(status_code=503, detail="Home Assistant is not configured")
        try:
            return home.add_entity(entity.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/home/entities/{item_id}")
    def home_edit_entity(item_id: str, entity: HomeEntityEdit):
        if not home:
            raise HTTPException(status_code=503, detail="Home Assistant is not configured")
        try:
            return home.update_entity(item_id, entity.model_dump(exclude_unset=True))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown device") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/home/entities/{item_id}")
    def home_remove_entity(item_id: str):
        if not home:
            raise HTTPException(status_code=503, detail="Home Assistant is not configured")
        try:
            home.remove_entity(item_id)
            return {"ok": True}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown device") from exc

    @app.post("/api/home/rooms")
    def home_add_room(room: RoomName):
        if not home:
            raise HTTPException(status_code=503, detail="Home Assistant is not configured")
        try:
            return {"rooms": home.add_room(room.name)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/home/rooms/{room}")
    def home_rename_room(room: str, payload: RoomName):
        if not home:
            raise HTTPException(status_code=503, detail="Home Assistant is not configured")
        try:
            return {"rooms": home.rename_room(room, payload.name)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/home/rooms/{room}/turn_off")
    def home_turn_off_room(room: str):
        if not home or not home.enabled:
            raise HTTPException(status_code=503, detail="Home Assistant is not configured")
        return home.turn_off_room(room)

    @app.get("/api/home/music-reactive")
    def music_status():
        return music.status() if music and home and home.enabled else {"active": False, "available": False}

    @app.post("/api/home/music-reactive/claim")
    def music_claim(request: MusicClaim):
        if not music or not home or not home.enabled:
            raise HTTPException(status_code=503, detail="Home Assistant is not configured")
        try:
            return music.claim(request.client_id, request.name, request.take_over)
        except PermissionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/home/music-reactive/level")
    def music_level(level: MusicLevel):
        if not music or not home or not home.enabled:
            raise HTTPException(status_code=503, detail="Home Assistant is not configured")
        try:
            return music.update(level.client_id, level.level, level.beat, level.hue)
        except PermissionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Home Assistant command failed") from exc

    @app.post("/api/home/music-reactive/stop")
    def music_stop(request: MusicClaim):
        if not music:
            raise HTTPException(status_code=503, detail="Music reactive mode is unavailable")
        try:
            return music.stop(request.client_id, request.take_over)
        except PermissionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app
