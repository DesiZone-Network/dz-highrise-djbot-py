from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .config import RadioConfig


BASE_URL = "https://desizoneradio.com/api/v1"


@dataclass(frozen=True)
class DesiZoneHeaders:
    api_key: str | None
    app_version: str
    radio: RadioConfig

    def as_dict(self, include_app: bool = True) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "x-device-platform": "Highrise",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        if include_app:
            headers["x-app-version"] = self.app_version
            headers["x-app-name"] = f"DesiZone Highrise DJ Bot {self.radio.radio_id}"
        return headers


class DesiZoneClient:
    def __init__(self, api_key: str | None, radio: RadioConfig, app_version: str) -> None:
        self.headers = DesiZoneHeaders(api_key=api_key, app_version=app_version, radio=radio)
        self.radio = radio
        self.client = httpx.AsyncClient(timeout=15)

    async def search_song(self, query: str) -> list[dict[str, Any]]:
        if not self.headers.api_key:
            return []
        response = await self.client.get(
            f"{BASE_URL}/search",
            headers=self.headers.as_dict(),
            params={"radio": self.radio.radio_id, "q": query, "type": "all", "limit": 3},
        )
        response.raise_for_status()
        return list(response.json())

    async def request_song(self, song_id: str, requester: str, request_message: str = "") -> Any:
        response = await self.client.get(
            f"{BASE_URL}/request",
            headers=self.headers.as_dict(include_app=False),
            params=build_request_params(self.radio.radio_id, song_id, requester, request_message),
        )
        response.raise_for_status()
        return response.json()

    async def get_song_info(self, song_id: str) -> dict[str, Any]:
        response = await self.client.get(
            f"{BASE_URL}/songinfo",
            headers=self.headers.as_dict(include_app=False),
            params={"radio": self.radio.radio_id, "songID": song_id},
        )
        response.raise_for_status()
        data = response.json()
        return data[0] if data else {}

    async def close(self) -> None:
        await self.client.aclose()


def build_request_params(
    radio_id: int,
    song_id: str,
    requester: str,
    request_message: str = "",
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "radio": radio_id,
        "songID": song_id,
        "requester": requester,
        "app": True,
    }
    if request_message:
        params["requestmsg"] = request_message
    return params
