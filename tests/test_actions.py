from dz_highrise_bot.actions import HighriseActions
from dz_highrise_bot.config import PositionConfig


class FakeHighrise:
    def __init__(self) -> None:
        self.calls = []

    async def chat(self, message):
        self.calls.append(("chat", message))

    async def send_whisper(self, user_id, message):
        self.calls.append(("whisper", user_id, message))

    async def send_emote(self, emote_id, target_user_id=None):
        self.calls.append(("emote", emote_id, target_user_id))

    async def react(self, reaction, target_user_id):
        self.calls.append(("react", reaction, target_user_id))

    async def walk_to(self, position):
        self.calls.append(("walk_to", position.x, position.y, position.z, position.facing))

    async def teleport(self, user_id, position):
        self.calls.append(("teleport", user_id, position.x, position.y, position.z, position.facing))

    async def move_user_to_room(self, user_id, room_id):
        self.calls.append(("move_user_to_room", user_id, room_id))

    async def set_outfit(self, items):
        self.calls.append(("set_outfit", items[0].id))


async def test_highrise_actions_delegate_to_sdk_methods() -> None:
    fake = FakeHighrise()
    actions = HighriseActions(fake)

    await actions.chat("hello")
    await actions.whisper("u1", "secret")
    await actions.emote("emote-wave", "u2")
    await actions.react("u3", "heart")
    await actions.walk_to(PositionConfig(1, 2, 3, "FrontRight"))
    await actions.teleport("u4", PositionConfig(4, 5, 6, "FrontLeft"))
    await actions.move_user_to_room("u5", "room")
    await actions.set_outfit([{"type": "clothing", "amount": 1, "id": "shirt"}])

    assert fake.calls[0] == ("chat", "hello")
    assert ("teleport", "u4", 4, 5, 6, "FrontLeft") in fake.calls
    assert fake.calls[-1] == ("set_outfit", "shirt")
