from highrise.models import User

from dz_highrise_bot.commands import CommandHandler, parse_command
from dz_highrise_bot.config import load_config


class FakeActions:
    def __init__(self) -> None:
        self.calls = []

    async def chat(self, message):
        self.calls.append(("chat", message))

    async def whisper(self, user_id, message):
        self.calls.append(("whisper", user_id, message))

    async def walk_to(self, position):
        self.calls.append(("walk_to", position))

    async def teleport(self, user_id, position):
        self.calls.append(("teleport", user_id, position))

    async def get_room_users(self):
        return []


class FakeDesiZone:
    async def search_song(self, query):
        return []


def test_parse_command_extracts_name_and_raw_args() -> None:
    parsed = parse_command("!req 123 play this", "!")

    assert parsed is not None
    assert parsed.name == "req"
    assert parsed.args == ["123", "play", "this"]
    assert parsed.raw_args == "123 play this"


async def test_floor_map_teleport_position_is_available() -> None:
    config = load_config("config")

    assert config.floor_maps[config.authentication.room]["floor 2"].x == 16.5


async def test_command_walk_requires_developer() -> None:
    config = load_config("config")
    actions = FakeActions()
    handler = CommandHandler(config, actions, FakeDesiZone(), __import__("logging").getLogger("test"))

    await handler.handle_text(User("1", "notadev"), "!walk")
    await handler.handle_text(User("2", "FaF86"), "!walk")

    assert len(actions.calls) == 1
    assert actions.calls[0][0] == "walk_to"
