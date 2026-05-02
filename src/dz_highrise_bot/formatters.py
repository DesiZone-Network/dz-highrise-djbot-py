from __future__ import annotations

import re
from typing import Any


REQUEST_SOURCES = {
    0: "Web Request by: {requester}",
    1: "Mobileweb Request by: {requester}",
    2: "Discord Request by: {requester}",
    3: "Android App Request by: {requester}",
    4: "iOS App Request by: {requester}",
    5: "Windows App Request by: {requester}",
    6: "macOS App Request by: {requester}",
    7: "Linux App Request by: {requester}",
    8: "Highrise Request by: @{requester}",
    100: "Playlist of the Week by: {requester}",
    101: "Playlist Request by: {requester}",
}


def format_now_playing(data: dict[str, Any]) -> tuple[str, str]:
    requested_text = ""
    if str(data.get("requested")) == "1":
        requester = data.get("requester", "")
        source = REQUEST_SOURCES.get(_as_int(data.get("apprequest")))
        if source:
            requested_text = f"\n\n{source.format(requester=requester)}"

    request_message = ""
    raw_request_message = data.get("requestmsg")
    if (
        raw_request_message
        and raw_request_message != "null"
        and not re.search(r"[^a-zA-Z0-9]", str(raw_request_message))
    ):
        request_message = f"\nRequest Message: {raw_request_message}"

    base = f"\nNow playing: \n{data.get('title')}\n\nby {data.get('artist')}{requested_text}"
    return base + request_message, base


def format_current_event(data: dict[str, Any], max_length: int = 200) -> str:
    message = f"Current Show: \n{data.get('title')}:\n\n{data.get('smalldesc')}"
    if len(message) > max_length:
        return message[:max_length] + "..."
    return message


def is_soundtrack(data: dict[str, Any]) -> bool:
    return "Soundtrack" in str(data.get("genre", ""))


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
