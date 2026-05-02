from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from highrise.models import AnchorPosition, Item, Position

from .config import AnchorConfig, PositionConfig


class HighriseActions:
    def __init__(self, highrise: Any, logger: logging.Logger | None = None) -> None:
        self.highrise = highrise
        self.logger = logger or logging.getLogger("dz_highrise_bot")

    async def safe_operation(
        self,
        name: str,
        operation: Callable[[], Awaitable[Any]],
        retries: int = 3,
    ) -> Any:
        for attempt in range(1, retries + 1):
            try:
                return await operation()
            except Exception as error:
                if _target_missing(error):
                    self.logger.warning("%s target not present: %s", name, error)
                    return None
                if attempt >= retries:
                    self.logger.exception("%s failed after %s attempts", name, retries)
                    raise
                await asyncio.sleep(min(2 ** (attempt - 1), 10))
        return None

    async def chat(self, message: str) -> Any:
        return await self.safe_operation("chat", lambda: self.highrise.chat(message))

    async def whisper(self, user_id: str, message: str) -> Any:
        return await self.safe_operation("whisper", lambda: self.highrise.send_whisper(user_id, message))

    async def emote(self, emote_id: str, target_user_id: str | None = None) -> Any:
        return await self.safe_operation(
            "emote",
            lambda: self.highrise.send_emote(emote_id, target_user_id),
        )

    async def react(self, target_user_id: str, reaction: str) -> Any:
        return await self.safe_operation("react", lambda: self.highrise.react(reaction, target_user_id))

    async def walk_to(self, position: PositionConfig) -> Any:
        return await self.safe_operation("walk_to", lambda: self.highrise.walk_to(to_position(position)))

    async def sit(self, anchor: AnchorConfig) -> Any:
        return await self.safe_operation(
            "sit",
            lambda: self.highrise.walk_to(AnchorPosition(anchor.entity_id, anchor.anchor_ix)),
        )

    async def teleport(self, user_id: str, position: PositionConfig) -> Any:
        return await self.safe_operation(
            "teleport",
            lambda: self.highrise.teleport(user_id, to_position(position)),
        )

    async def move_user_to_room(self, user_id: str, room_id: str) -> Any:
        return await self.safe_operation(
            "move_user_to_room",
            lambda: self.highrise.move_user_to_room(user_id, room_id),
        )

    async def set_outfit(self, outfit: list[dict[str, Any]]) -> Any:
        items = [to_item(item) for item in outfit]
        return await self.safe_operation("set_outfit", lambda: self.highrise.set_outfit(items))

    async def get_room_users(self) -> list[tuple[Any, Any]]:
        response = await self.highrise.get_room_users()
        if hasattr(response, "content"):
            return list(response.content)
        return []


def to_position(position: PositionConfig) -> Position:
    return Position(position.x, position.y, position.z, position.facing)


def to_item(item: dict[str, Any]) -> Item:
    return Item(
        type=item.get("type", "clothing"),
        amount=int(item.get("amount", 1)),
        id=item["id"],
        account_bound=bool(item.get("account_bound", False)),
        active_palette=item.get("active_palette"),
    )


def _target_missing(error: Exception) -> bool:
    message = str(error)
    return "Target user not in room" in message or "not in room" in message
