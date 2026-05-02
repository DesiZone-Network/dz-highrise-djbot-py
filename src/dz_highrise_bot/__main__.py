from __future__ import annotations

import argparse
import asyncio
import os

from highrise.__main__ import BotDefinition, main as highrise_main

from .bot import DesiZoneBot
from .config import load_config


def cli() -> None:
    parser = argparse.ArgumentParser(description="Run the DesiZone Highrise Python bot.")
    parser.add_argument("--config", default=os.getenv("DZ_BOT_CONFIG", "config"))
    parser.add_argument("--outfit", default=os.getenv("DZ_BOT_OUTFIT", "formal"))
    parser.add_argument("--smoke", action="store_true", help="Load config and validate imports without connecting.")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.smoke:
        smoke_check(config.name)
        return
    if not config.authentication.token:
        raise SystemExit(f"Missing {args.config} Highrise token environment variable.")
    bot = DesiZoneBot(config_name=args.config, launch_outfit=args.outfit)
    asyncio.run(highrise_main([BotDefinition(bot, config.authentication.room, config.authentication.token)]))


def smoke_check(config_name: str) -> None:
    for name in ["config", "config2", "config.test"]:
        config = load_config(name)
        print(f"loaded {config.name}: room={config.authentication.room} radio={config.radio.radio_id}")
    selected = load_config(config_name)
    missing = []
    if not selected.authentication.token:
        missing.append("Highrise token")
    if not selected.desizone_api_key:
        missing.append("DESIZONE_API_KEY")
    if missing:
        print("optional runtime values missing for live run: " + ", ".join(missing))


if __name__ == "__main__":
    cli()
