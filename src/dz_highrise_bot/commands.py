from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any

from highrise.models import AnchorPosition, Position, User

from .actions import HighriseActions
from .config import BotConfig, PositionConfig
from .desizone import DesiZoneClient
from .legacy_outfits import select_outfit


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    args: list[str]
    raw_args: str


class CommandHandler:
    def __init__(
        self,
        config: BotConfig,
        actions: HighriseActions,
        desizone: DesiZoneClient,
        logger: logging.Logger,
    ) -> None:
        self.config = config
        self.actions = actions
        self.desizone = desizone
        self.logger = logger
        self.users_by_name: dict[str, str] = {}
        self.positions_by_id: dict[str, PositionConfig] = {}
        self.dance_task: asyncio.Task[None] | None = None

    def remember_user(self, user: User, position: Any | None = None) -> None:
        self.users_by_name[user.username.lower()] = user.id
        if isinstance(position, Position):
            self.positions_by_id[user.id] = PositionConfig(position.x, position.y, position.z, position.facing)

    async def refresh_room_users(self) -> None:
        for user, position in await self.actions.get_room_users():
            self.remember_user(user, position)

    async def handle_text(self, user: User, message: str, *, whisper: bool = False) -> None:
        parsed = parse_command(message, self.config.settings.prefix)
        if parsed is None:
            if message.strip() == "dance":
                await self.command_emote(user, ParsedCommand("emote", [], ""))
            return

        commands = {
            "come": self.command_come,
            "emoteall": self.command_emote_all,
            "search": self.command_search,
            "req": self.command_request,
            "emote": self.command_emote,
            "walk": self.command_walk,
            "outfit": self.command_outfit,
            "dance": self.command_dance,
            "stopdance": self.command_stop_dance,
            "summon": self.command_summon,
            "goto": self.command_goto,
            "teleport": self.command_teleport,
            "join": self.command_join,
        }
        handler = commands.get(parsed.name)
        if handler:
            await handler(user, parsed)

    async def command_come(self, user: User, _: ParsedCommand) -> None:
        if not self._is_developer(user):
            return
        position = await self._position_for_user(user.id)
        if position:
            await self.actions.walk_to(position)

    async def command_emote(self, user: User, parsed: ParsedCommand) -> None:
        if not self._is_developer(user):
            return
        await self.actions.emote(parsed.args[0] if parsed.args else "emote", self.config.authentication.bot_id)

    async def command_emote_all(self, user: User, _: ParsedCommand) -> None:
        if not self._is_moderator(user):
            return
        await self.refresh_room_users()
        emote = random.choice(["idle-dance-casual", "emote-wave", "emote-hello"])
        for target_id in list(self.positions_by_id):
            await self.actions.emote(emote, target_id)

    async def command_search(self, user: User, parsed: ParsedCommand) -> None:
        query = parsed.raw_args.strip()
        if not query:
            await self.actions.whisper(user.id, "Please search with a song name.")
            return
        await self.actions.chat(f"Searching for you @{user.username}...")
        results = await self.desizone.search_song(query)
        if not results:
            await self.actions.whisper(user.id, "No search results found")
            return
        for index, result in enumerate(results[:3], start=1):
            delay = (index - 1) * 5
            asyncio.create_task(self._delayed_search_result(user.id, index, result, delay))
        asyncio.create_task(
            self._delayed_whisper(
                user.id,
                "If the song you want to request is not listed, please refine your search query",
                15,
            )
        )

    async def command_request(self, user: User, parsed: ParsedCommand) -> None:
        if not parsed.args:
            await self.actions.whisper(user.id, "Use the request command with a song ID.")
            return
        song_id = parsed.args[0]
        request_message = " ".join(parsed.args[1:])
        try:
            await self.desizone.request_song(song_id, user.username, request_message)
            song_info = await self.desizone.get_song_info(song_id)
            await self.actions.emote("emote-celebrate", user.id)
            await self.actions.emote("emote-hello", self.config.authentication.bot_id)
            await self.actions.chat(
                "Your requested song\n"
                f"{song_info.get('title')} by {song_info.get('artist')}\n"
                f"has been accepted @{user.username}!"
            )
        except Exception as error:
            self.logger.exception("Song request failed")
            await self.actions.emote("emote-sad", self.config.authentication.bot_id)
            await self.actions.chat(f"Failed to request the song @{user.username}:\n{error}")

    async def command_walk(self, user: User, _: ParsedCommand) -> None:
        if self._is_developer(user):
            await self.actions.walk_to(self.config.settings.coordinates)

    async def command_outfit(self, user: User, parsed: ParsedCommand) -> None:
        if not self._is_developer(user):
            return
        outfit_name = parsed.args[0] if parsed.args else "formal"
        emote = {"casual": "emote-teleporting", "party": "emote-gravity", "formal": "emote-float"}.get(outfit_name)
        if not emote:
            return
        await self.actions.emote(emote, self.config.authentication.bot_id)
        await asyncio.sleep(9 if outfit_name == "casual" else 6)
        await self.actions.set_outfit(select_outfit(self.config.outfits.legacy_module, outfit_name))

    async def command_dance(self, _: User, __: ParsedCommand) -> None:
        if self.dance_task and not self.dance_task.done():
            return
        self.dance_task = asyncio.create_task(self._dance_loop())

    async def command_stop_dance(self, _: User, __: ParsedCommand) -> None:
        if self.dance_task:
            self.dance_task.cancel()
            self.dance_task = None

    async def command_summon(self, user: User, parsed: ParsedCommand) -> None:
        if not self._is_moderator(user) or not parsed.args:
            return
        target_id = await self._user_id_for_name(parsed.args[0])
        user_position = await self._position_for_user(user.id)
        if target_id and user_position:
            await self.actions.teleport(target_id, user_position)

    async def command_goto(self, user: User, parsed: ParsedCommand) -> None:
        if not self._is_moderator(user) or not parsed.args:
            return
        target_id = await self._user_id_for_name(parsed.args[0])
        target_position = await self._position_for_user(target_id) if target_id else None
        if target_position:
            await self.actions.teleport(user.id, target_position)

    async def command_teleport(self, user: User, parsed: ParsedCommand) -> None:
        if not self._is_developer(user) or len(parsed.args) < 2:
            return
        target_id = await self._user_id_for_name(parsed.args[0])
        destination = await self._parse_destination(parsed.args[1])
        if target_id and destination:
            await self.actions.teleport(target_id, destination)

    async def command_join(self, user: User, _: ParsedCommand) -> None:
        await self.actions.whisper(user.id, "Join command received.")

    async def _parse_destination(self, value: str) -> PositionConfig | None:
        if value.startswith("@"):
            user_id = await self._user_id_for_name(value)
            return await self._position_for_user(user_id) if user_id else None
        if "," not in value:
            return None
        x, y, z = value.split(",", maxsplit=2)
        return PositionConfig(float(x), float(y), float(z), "FrontRight")

    async def _position_for_user(self, user_id: str | None) -> PositionConfig | None:
        if not user_id:
            return None
        if user_id not in self.positions_by_id:
            await self.refresh_room_users()
        return self.positions_by_id.get(user_id)

    async def _user_id_for_name(self, username: str) -> str | None:
        clean = username.replace("@", "").lower()
        if clean not in self.users_by_name:
            await self.refresh_room_users()
        return self.users_by_name.get(clean)

    async def _delayed_search_result(self, user_id: str, index: int, result: dict[str, Any], delay: int) -> None:
        await self._delayed_whisper(
            user_id,
            f"{index}{ordinal_suffix(index)} search result:\n"
            f"{result.get('title')} by {result.get('artist')} \n"
            f"To request, Use {self.config.settings.prefix}req {result.get('ID')} <optional request message>",
            delay,
        )

    async def _delayed_whisper(self, user_id: str, message: str, delay: int) -> None:
        await asyncio.sleep(delay)
        await self.actions.whisper(user_id, message)

    async def _dance_loop(self) -> None:
        while True:
            await self.actions.emote("idle-dance-casual", self.config.authentication.bot_id)
            await asyncio.sleep(8.65)

    def _is_developer(self, user: User) -> bool:
        return user.username in self.config.settings.developers

    def _is_moderator(self, user: User) -> bool:
        return user.username in self.config.settings.moderators


def parse_command(message: str, prefix: str) -> ParsedCommand | None:
    if not message.startswith(prefix):
        return None
    body = message[len(prefix) :].strip()
    if not body:
        return None
    parts = body.split()
    name = parts[0].lower()
    raw_args = body[len(parts[0]) :].strip()
    return ParsedCommand(name=name, args=parts[1:], raw_args=raw_args)


def ordinal_suffix(index: int) -> str:
    return {1: "st", 2: "nd", 3: "rd"}.get(index, "th")
