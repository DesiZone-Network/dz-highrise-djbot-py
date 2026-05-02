from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import credentials, db

from .config import BotConfig


NowPlayingCallback = Callable[[dict[str, Any]], Awaitable[None]]
EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


class FirebaseRadioListener:
    def __init__(
        self,
        config: BotConfig,
        on_now_playing: NowPlayingCallback,
        on_current_event: EventCallback,
        logger: logging.Logger,
    ) -> None:
        self.config = config
        self.on_now_playing = on_now_playing
        self.on_current_event = on_current_event
        self.logger = logger
        self.listeners: list[Any] = []
        self.loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        if not self.config.firebase_credentials_path:
            self.logger.warning("Firebase credentials not configured; radio listeners disabled")
            return
        self.loop = asyncio.get_running_loop()
        _initialize_firebase(self.config.firebase_credentials_path)
        radio_id = self.config.radio.radio_id
        self.listeners.append(
            db.reference(f"DesiZoneRadio/Stations/Radio{radio_id}/playing/0").listen(
                self._handle_now_playing
            )
        )
        self.listeners.append(
            db.reference(f"DesiZoneRadio/Stations/Radio{radio_id}/currentevent/0").listen(
                self._handle_current_event
            )
        )

    def close(self) -> None:
        for listener in self.listeners:
            close = getattr(listener, "close", None)
            if close:
                close()

    def _handle_now_playing(self, event: Any) -> None:
        if isinstance(event.data, dict) and self.loop:
            asyncio.run_coroutine_threadsafe(self.on_now_playing(event.data), self.loop)

    def _handle_current_event(self, event: Any) -> None:
        if isinstance(event.data, dict) and self.loop:
            asyncio.run_coroutine_threadsafe(self.on_current_event(event.data), self.loop)


def _initialize_firebase(credentials_path: Path) -> None:
    if firebase_admin._apps:
        return
    cred = credentials.Certificate(str(credentials_path))
    firebase_admin.initialize_app(
        cred,
        {"databaseURL": "https://pc-api-5956844866156025284-436-default-rtdb.europe-west1.firebasedatabase.app"},
    )
