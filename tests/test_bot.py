from dz_highrise_bot.bot import outfit_for_hour, position_matches
from dz_highrise_bot.config import PositionConfig


class PositionLike:
    x = 16.5
    y = 6.25
    z = 19.5


def test_outfit_for_hour_matches_existing_windows() -> None:
    assert outfit_for_hour(3) == "casual"
    assert outfit_for_hour(11) == "formal"
    assert outfit_for_hour(19) == "party"


def test_position_matches_ignores_facing_like_node_trigger() -> None:
    assert position_matches(PositionLike(), PositionConfig(16.5, 6.25, 19.5, "FrontRight"))
