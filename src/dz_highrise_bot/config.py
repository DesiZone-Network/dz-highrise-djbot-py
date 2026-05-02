from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


APP_ROOT = Path(__file__).resolve().parents[2]
LEGACY_ROOT = APP_ROOT.parent


@dataclass(frozen=True)
class PositionConfig:
    x: float
    y: float
    z: float
    facing: str = "FrontRight"


@dataclass(frozen=True)
class AnchorConfig:
    entity_id: str
    anchor_ix: int


@dataclass(frozen=True)
class SettingsConfig:
    prefix: str
    developers: list[str]
    moderators: list[str]
    action: str
    emote: str
    coordinates: PositionConfig
    object: AnchorConfig


@dataclass(frozen=True)
class PeriodicConfig:
    type: str
    is_enabled: bool
    duration_minutes: int
    messages: list[str]


@dataclass(frozen=True)
class AuthenticationConfig:
    room: str
    token: str | None
    bot_id: str


@dataclass(frozen=True)
class RadioConfig:
    radio_id: int
    radio_name: str
    radio_name_short: str
    dj_name: str


@dataclass(frozen=True)
class OutfitConfig:
    legacy_module: Path


@dataclass(frozen=True)
class TeleportTrigger:
    match: PositionConfig
    destination: PositionConfig


@dataclass(frozen=True)
class BotConfig:
    name: str
    settings: SettingsConfig
    periodic: PeriodicConfig
    authentication: AuthenticationConfig
    radio: RadioConfig
    outfits: OutfitConfig
    excluded_user_ids: set[str]
    floor_maps: dict[str, dict[str, PositionConfig]]
    teleport_triggers: list[TeleportTrigger]
    desizone_api_key: str | None
    firebase_credentials_path: Path | None
    sentry_dsn: str | None
    linear_api_key: str | None
    linear_team_id: str | None
    linear_project_id: str | None
    pushover_user_key: str | None
    pushover_api_token: str | None


def load_config(name: str = "config") -> BotConfig:
    load_dotenv(LEGACY_ROOT / ".env", override=False)
    load_dotenv(APP_ROOT / ".env", override=False)

    config_path = APP_ROOT / "config" / f"{name}.yaml"
    if not config_path.exists():
        allowed = sorted(path.stem for path in (APP_ROOT / "config").glob("*.yaml"))
        raise ValueError(f"Unknown config {name!r}. Allowed: {', '.join(allowed)}")

    data = yaml.safe_load(config_path.read_text()) or {}
    auth_data = data["authentication"]
    token = os.getenv(auth_data.get("token_env", "HIGHRISE_TOKEN"))
    room = os.getenv("HIGHRISE_ROOM_ID") or auth_data["room"]
    bot_id = os.getenv("HIGHRISE_BOT_ID") or auth_data["bot_id"]
    firebase_path = _optional_path(os.getenv("FIREBASE_CREDENTIALS_PATH"))
    if firebase_path is None:
        legacy_firebase = LEGACY_ROOT / "firebaseapi.json"
        firebase_path = legacy_firebase if legacy_firebase.exists() else None

    return BotConfig(
        name=name,
        settings=_settings(data["settings"]),
        periodic=_periodic(data["periodic"]),
        authentication=AuthenticationConfig(room=room, token=token, bot_id=bot_id),
        radio=RadioConfig(**data["radio"]),
        outfits=OutfitConfig(legacy_module=_resolve_path(data["outfits"]["legacy_module"])),
        excluded_user_ids=set(data.get("excluded_user_ids", [])) | {bot_id},
        floor_maps=_floor_maps(data.get("floor_maps", {})),
        teleport_triggers=_teleport_triggers(data.get("teleport_triggers", [])),
        desizone_api_key=os.getenv("DESIZONE_API_KEY"),
        firebase_credentials_path=firebase_path,
        sentry_dsn=os.getenv("SENTRY_DSN"),
        linear_api_key=os.getenv("LINEAR_API_KEY"),
        linear_team_id=os.getenv("LINEAR_TEAM_ID"),
        linear_project_id=os.getenv("LINEAR_PROJECT_ID"),
        pushover_user_key=os.getenv("PUSHOVER_USER_KEY") or os.getenv("PUSHOVER_USER"),
        pushover_api_token=os.getenv("PUSHOVER_API_TOKEN") or os.getenv("PUSHOVER_TOKEN"),
    )


def _settings(data: dict[str, Any]) -> SettingsConfig:
    return SettingsConfig(
        prefix=data["prefix"],
        developers=list(data["developers"]),
        moderators=list(data["moderators"]),
        action=data["action"],
        emote=data["emote"],
        coordinates=_position(data["coordinates"]),
        object=AnchorConfig(**data["object"]),
    )


def _periodic(data: dict[str, Any]) -> PeriodicConfig:
    return PeriodicConfig(
        type=data["type"],
        is_enabled=bool(data["is_enabled"]),
        duration_minutes=int(data["duration_minutes"]),
        messages=list(data["messages"]),
    )


def _floor_maps(data: dict[str, dict[str, Any]]) -> dict[str, dict[str, PositionConfig]]:
    return {
        room_id: {command: _position(position) for command, position in commands.items()}
        for room_id, commands in data.items()
    }


def _teleport_triggers(data: list[dict[str, Any]]) -> list[TeleportTrigger]:
    return [
        TeleportTrigger(match=_position(item["match"]), destination=_position(item["destination"]))
        for item in data
    ]


def _position(data: dict[str, Any]) -> PositionConfig:
    return PositionConfig(
        x=float(data["x"]),
        y=float(data["y"]),
        z=float(data["z"]),
        facing=data.get("facing", "FrontRight"),
    )


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = APP_ROOT / path
    return path.resolve()


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = APP_ROOT / path
    return path.resolve()
