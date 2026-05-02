from __future__ import annotations

import logging

import httpx


class PushoverNotifier:
    def __init__(self, user_key: str | None, api_token: str | None, logger: logging.Logger) -> None:
        self.user_key = user_key
        self.api_token = api_token
        self.logger = logger

    async def send(self, title: str, message: str, priority: int = 0) -> None:
        if not self.user_key or not self.api_token:
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    "https://api.pushover.net/1/messages.json",
                    data={
                        "token": self.api_token,
                        "user": self.user_key,
                        "title": title,
                        "message": message,
                        "priority": priority,
                    },
                )
        except Exception:
            self.logger.exception("Failed to send Pushover notification")
