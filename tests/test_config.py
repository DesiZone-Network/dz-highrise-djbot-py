from dz_highrise_bot.config import load_config
from dz_highrise_bot.legacy_outfits import load_legacy_outfits


def test_load_config2_preserves_radio_and_room() -> None:
    config = load_config("config2")

    assert config.radio.radio_id == 2
    assert config.authentication.room == "661f8dac913674fc6fef2233"
    assert config.settings.prefix == "!"


def test_load_test_config_uses_question_prefix() -> None:
    config = load_config("config.test")

    assert config.settings.prefix == "?"
    assert config.authentication.bot_id == "660e562d55cf728f6e9506aa"


def test_legacy_outfit_loader_reads_existing_js_outfits() -> None:
    config = load_config("config")
    outfits = load_legacy_outfits(config.outfits.legacy_module)

    assert outfits["casual"]
    assert outfits["formal"]
    assert outfits["party"]
    assert outfits["formal"][0]["type"] == "clothing"
