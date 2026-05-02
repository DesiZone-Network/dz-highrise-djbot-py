from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from .config import LEGACY_ROOT, BotConfig


def configure_logging(config: BotConfig) -> logging.Logger:
    logs_dir = LEGACY_ROOT / "logs"
    chat_dir = logs_dir / "chathistory"
    logs_dir.mkdir(exist_ok=True)
    chat_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("dz_highrise_bot")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(event_id)s] %(message)s")
    general_handler = logging.FileHandler(logs_dir / f"dzlog{config.radio.radio_id}.log")
    general_handler.setFormatter(formatter)
    general_handler.addFilter(_DefaultEventId())
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(_DefaultEventId())
    logger.addHandler(general_handler)
    logger.addHandler(stream_handler)

    chat_logger = logging.getLogger("dz_highrise_bot.chat")
    chat_logger.setLevel(logging.INFO)
    chat_logger.handlers.clear()
    chat_logger.propagate = False
    chat_file = chat_dir / f"chatradio{config.radio.radio_id}-.{datetime.now(UTC).date().isoformat()}.log"
    chat_handler = logging.FileHandler(chat_file)
    chat_handler.setFormatter(formatter)
    chat_handler.addFilter(_DefaultEventId())
    chat_logger.addHandler(chat_handler)
    return logger


def chat_history(data: str, message: str, event_id: str) -> None:
    logging.getLogger("dz_highrise_bot.chat").info(
        "%s - %s",
        data,
        message,
        extra={"event_id": event_id},
    )


class _DefaultEventId(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "event_id"):
            record.event_id = "GENERAL"
        return True
