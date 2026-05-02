from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

import sentry_sdk
from highrise import BaseBot
from highrise.models import AnchorPosition, CurrencyItem, Item, Position, SessionMetadata, User

from .actions import HighriseActions
from .commands import CommandHandler
from .config import BotConfig, PositionConfig, load_config
from .desizone import DesiZoneClient
from .firebase_service import FirebaseRadioListener
from .formatters import format_current_event, format_now_playing, is_soundtrack
from .legacy_outfits import select_outfit
from .linear_reporter import LinearReporter
from .logging_config import chat_history, configure_logging
from .notifications import PushoverNotifier


class DesiZoneBot(BaseBot):
    def __init__(self, config_name: str | None = None, launch_outfit: str | None = None) -> None:
        self.config = load_config(config_name or os.getenv("DZ_BOT_CONFIG", "config"))
        self.launch_outfit = launch_outfit or os.getenv("DZ_BOT_OUTFIT", "formal")
        self.logger = configure_logging(self.config)
        if self.config.sentry_dsn:
            sentry_sdk.init(dsn=self.config.sentry_dsn, environment=os.getenv("NODE_ENV", "development"))
        self.actions: HighriseActions | None = None
        self.commands: CommandHandler | None = None
        self.desizone: DesiZoneClient | None = None
        self.firebase_listener: FirebaseRadioListener | None = None
        self.notifier = PushoverNotifier(
            self.config.pushover_user_key,
            self.config.pushover_api_token,
            self.logger,
        )
        self.linear = LinearReporter(
            self.config.linear_api_key,
            self.config.linear_team_id,
            self.config.linear_project_id,
            self.logger,
        )
        self.current_song_id: Any = None
        self.playing_message: str | None = None
        self.current_event_message: str | None = None
        self.started_background_tasks = False

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        self.logger.info(
            "Bot connected successfully to room: %s",
            session_metadata.room_info.room_name,
            extra={"event_id": "READY"},
        )
        self.actions = HighriseActions(self.highrise, self.logger)
        self.desizone = DesiZoneClient(self.config.desizone_api_key, self.config.radio, "0.1.0")
        self.commands = CommandHandler(self.config, self.actions, self.desizone, self.logger)
        await self._handle_ready_action(session_metadata)
        await self.actions.chat(
            f"Hi, {self.config.radio.dj_name} here in {session_metadata.room_info.room_name}, "
            f"playing for you the best music on {self.config.radio.radio_name}, enjoy your stay!"
        )
        if not self.started_background_tasks:
            self.started_background_tasks = True
            asyncio.create_task(self._change_outfit_after_delay(20, self.launch_outfit))
            asyncio.create_task(self._periodic_messages())
            asyncio.create_task(self._start_firebase_after_delay(10))

    async def on_chat(self, user: User, message: str) -> None:
        await self._safe("chat", self._on_chat(user, message))

    async def on_whisper(self, user: User, message: str) -> None:
        await self._safe("whisper", self._on_whisper(user, message))

    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        self.logger.info(
            "Direct message received: user=%s conversation=%s is_new=%s",
            user_id,
            conversation_id,
            is_new_conversation,
            extra={"event_id": "DIRECT_MESSAGE"},
        )

    async def on_user_join(self, user: User, position: Position | AnchorPosition) -> None:
        await self._safe("user_join", self._on_user_join(user, position))

    async def on_user_leave(self, user: User) -> None:
        self.logger.info("[PLAYER LEFT]: %s:%s", user.username, user.id, extra={"event_id": "LEAVE"})
        if user.id not in self.config.excluded_user_ids:
            chat_history(f"{user.username} ({user.id})", "LEFT", "LEFT")

    async def on_emote(self, user: User, emote_id: str, receiver: User | None) -> None:
        if user.id not in self.config.excluded_user_ids:
            receiver_text = f" to {receiver.username} ({receiver.id})" if receiver else ""
            chat_history(f"{user.username} ({user.id}):", f"sent emote: {emote_id}{receiver_text}", "EMOTE")

    async def on_reaction(self, user: User, reaction: str, receiver: User) -> None:
        if self.actions and receiver.id == self.config.authentication.bot_id and reaction == "heart":
            await self.actions.react(user.id, "heart")
        if user.id not in self.config.excluded_user_ids:
            chat_history(
                f"{user.username} ({user.id}):",
                f"sent reaction: {reaction} to {receiver.username} ({receiver.id})",
                "REACT",
            )

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem | Item) -> None:
        self.logger.info(
            "Tip reaction from %s to %s: %s %s",
            sender.username,
            receiver.username,
            getattr(tip, "amount", ""),
            getattr(tip, "type", ""),
            extra={"event_id": "TIP"},
        )

    async def on_user_move(self, user: User, destination: Position | AnchorPosition) -> None:
        if self.commands:
            self.commands.remember_user(user, destination)
        if isinstance(destination, Position):
            self.logger.info(
                "%s moved to coordinates: %s, %s, %s, %s",
                user.username,
                destination.x,
                destination.y,
                destination.z,
                destination.facing,
                extra={"event_id": "MOVE"},
            )
            await self._handle_teleport_trigger(user, destination)

    async def on_voice_change(self, users: list[tuple[User, str]], seconds_left: int) -> None:
        self.logger.info("Voice seconds left: %s users=%s", seconds_left, users, extra={"event_id": "VOICE"})

    async def on_moderate(
        self,
        moderator_id: str,
        target_user_id: str,
        moderation_type: str,
        duration: int | None,
    ) -> None:
        self.logger.info(
            "Moderation event: moderator=%s target=%s type=%s duration=%s",
            moderator_id,
            target_user_id,
            moderation_type,
            duration,
            extra={"event_id": "MODERATE"},
        )

    async def _on_chat(self, user: User, message: str) -> None:
        if self.commands:
            self.commands.remember_user(user)
        await self._handle_floor_command(user, message)
        if self.commands:
            await self.commands.handle_text(user, message)
        if user.id not in self.config.excluded_user_ids:
            chat_history(f"{user.username} ({user.id}):", message, "CHAT")

    async def _on_whisper(self, user: User, message: str) -> None:
        self.logger.info("[WHISPER]: %s:%s %s", user.username, user.id, message, extra={"event_id": "WHISPER"})
        if self.commands:
            self.commands.remember_user(user)
            await self.commands.handle_text(user, message, whisper=True)

    async def _on_user_join(self, user: User, position: Position | AnchorPosition) -> None:
        self.logger.info("[PLAYER JOINED]: %s:%s", user.username, user.id, extra={"event_id": "JOIN"})
        if self.commands:
            self.commands.remember_user(user, position)
        await self.notifier.send(
            f"Player Joined {self.config.radio.radio_name} Room",
            f"Player name: {user.username}",
        )
        if self.actions:
            await self.actions.whisper(
                user.id,
                f"Welcome {user.username}!\nI'm @{self.config.radio.dj_name} and you are currently listening to "
                f"{self.config.radio.radio_name}, enjoy your stay!\n\nWant to request songs on "
                f"{self.config.radio.radio_name_short}? \nJust use the command "
                f"{self.config.settings.prefix}search <songname> to find your favorite songs",
            )
            asyncio.create_task(self._delayed_user_context(user.id))
            await self._handle_special_join(user)
        if user.id not in self.config.excluded_user_ids:
            chat_history(f"{user.username} ({user.id})", "JOINED", "JOIN")

    async def _handle_ready_action(self, session_metadata: SessionMetadata) -> None:
        if not self.actions:
            return
        if self.config.settings.action == "walk":
            await self.actions.walk_to(self.config.settings.coordinates)
        elif self.config.settings.action == "teleport":
            await self.actions.teleport(str(session_metadata.user_id), self.config.settings.coordinates)
        elif self.config.settings.action == "sit":
            await self.actions.sit(self.config.settings.object)

    async def _handle_floor_command(self, user: User, message: str) -> None:
        if not self.actions:
            return
        floor_map = self.config.floor_maps.get(self.config.authentication.room, {})
        position = floor_map.get(message.lower())
        if position:
            await self.actions.teleport(user.id, position)

    async def _handle_special_join(self, user: User) -> None:
        if not self.actions:
            return
        if self.config.authentication.bot_id == "660d6c1f7a7d0f5af43ff89f" and user.username == "ibbygamer2008":
            await self.actions.chat("Welcome to DesiZone Radio, Sending you!")
            await self.actions.emote("emote-wave", self.config.authentication.bot_id)
            await asyncio.sleep(3)
            await self.actions.emote("emote-wave", self.config.authentication.bot_id)
            await asyncio.sleep(3)
            await self.actions.move_user_to_room(user.id, "66146f7c7d15905c4161bb27")
        elif user.username == "FaF86":
            await self.actions.chat("The Owner of DesiZone Radio has joined!! @FaF86")
            await self.actions.emote("emote-wave", self.config.authentication.bot_id)
            await asyncio.sleep(3)
            await self.actions.emote("emote-wave", self.config.authentication.bot_id)
            await asyncio.sleep(3)
            await self.actions.emote("emote-kiss", self.config.authentication.bot_id)
        else:
            await self.actions.emote("emote-hello", self.config.authentication.bot_id)

    async def _handle_teleport_trigger(self, user: User, position: Position) -> None:
        if not self.actions:
            return
        for trigger in self.config.teleport_triggers:
            if position_matches(position, trigger.match):
                await self.actions.whisper(user.id, "Teleporting you the the room")
                await self.actions.teleport(user.id, trigger.destination)
                await self.actions.emote("emote-wave", self.config.authentication.bot_id)
                await asyncio.sleep(3)
                await self.actions.emote("emote-wave", self.config.authentication.bot_id)

    async def _delayed_user_context(self, user_id: str) -> None:
        if not self.actions:
            return
        await asyncio.sleep(5)
        if self.playing_message:
            await self.actions.whisper(user_id, self.playing_message)
        await asyncio.sleep(5)
        if self.current_event_message:
            await self.actions.whisper(user_id, self.current_event_message)

    async def _periodic_messages(self) -> None:
        if not self.config.periodic.is_enabled:
            return
        while True:
            await asyncio.sleep(self.config.periodic.duration_minutes * 60)
            if not self.actions:
                continue
            message = self.config.periodic.messages[0]
            if self.config.periodic.type == "multiple":
                message = self.config.periodic.messages[datetime.now().microsecond % len(self.config.periodic.messages)]
            await self.actions.chat(message)

    async def _start_firebase_after_delay(self, delay: int) -> None:
        await asyncio.sleep(delay)
        if self.firebase_listener:
            return
        self.firebase_listener = FirebaseRadioListener(
            self.config,
            self.handle_now_playing,
            self.handle_current_event,
            self.logger,
        )
        self.firebase_listener.start()

    async def handle_now_playing(self, data: dict[str, Any]) -> None:
        if data.get("ID") == self.current_song_id:
            return
        self.current_song_id = data.get("ID")
        room_message, whisper_message = format_now_playing(data)
        self.playing_message = whisper_message
        if self.actions:
            await self.actions.chat(room_message)
            if is_soundtrack(data):
                await asyncio.sleep(5)
                await self.actions.chat("From the movie: \n" + str(data.get("album")))

    async def handle_current_event(self, data: dict[str, Any]) -> None:
        self.current_event_message = format_current_event(data)
        if self.actions:
            await self.actions.chat(self.current_event_message)

    async def _change_outfit_after_delay(self, delay: int, outfit_name: str) -> None:
        await asyncio.sleep(delay)
        await self.change_outfit(outfit_name)

    async def change_outfit(self, outfit_name: str | None = None) -> None:
        if not self.actions:
            return
        selected = outfit_name or outfit_for_hour(datetime.now().hour)
        emote = {"casual": "emote-teleporting", "formal": "emote-float", "party": "emote-gravity"}.get(selected)
        if emote:
            await self.actions.emote(emote, self.config.authentication.bot_id)
            await asyncio.sleep(9 if selected == "casual" else 6)
        await self.actions.set_outfit(select_outfit(self.config.outfits.legacy_module, selected))

    async def _safe(self, event_name: str, coroutine: Any) -> None:
        try:
            await coroutine
        except Exception as error:
            self.logger.exception("Unhandled bot event error: %s", event_name)
            sentry_sdk.capture_exception(error)
            await self.linear.report_exception(
                f"HR DJBot Radio{self.config.radio.radio_id} {event_name}",
                repr(error),
                str(error),
            )


def outfit_for_hour(hour: int) -> str:
    if 3 <= hour < 11:
        return "casual"
    if 11 <= hour < 19:
        return "formal"
    return "party"


def position_matches(position: Position, expected: PositionConfig) -> bool:
    return position.x == expected.x and position.y == expected.y and position.z == expected.z
