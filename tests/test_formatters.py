from dz_highrise_bot.formatters import format_current_event, format_now_playing, is_soundtrack


def test_format_now_playing_highrise_request() -> None:
    room_message, whisper_message = format_now_playing(
        {
            "ID": 123,
            "title": "Song",
            "artist": "Artist",
            "requested": "1",
            "apprequest": "8",
            "requester": "listener",
            "requestmsg": "Hello",
        }
    )

    assert "Now playing" in room_message
    assert "Highrise Request by: @listener" in room_message
    assert "Request Message: Hello" in room_message
    assert "Request Message" not in whisper_message


def test_format_current_event_truncates_long_messages() -> None:
    message = format_current_event({"title": "Show", "smalldesc": "x" * 300}, max_length=40)

    assert len(message) == 43
    assert message.endswith("...")


def test_is_soundtrack_checks_genre() -> None:
    assert is_soundtrack({"genre": "Bollywood Soundtrack"})
    assert not is_soundtrack({"genre": "Pop"})
