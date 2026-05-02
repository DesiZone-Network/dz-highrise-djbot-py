from dz_highrise_bot.desizone import build_request_params


def test_build_request_params_without_optional_message() -> None:
    params = build_request_params(1, "123", "FaF86")

    assert params == {
        "radio": 1,
        "songID": "123",
        "requester": "FaF86",
        "app": True,
    }


def test_build_request_params_with_optional_message() -> None:
    params = build_request_params(2, "456", "listener", "play this")

    assert params["radio"] == 2
    assert params["requestmsg"] == "play this"
