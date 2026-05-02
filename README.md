# DesiZone Highrise Python Bot

This is the side-by-side Python migration of the existing Node Highrise DJ bot. The Node bot remains unchanged and can stay in production while this app is validated.

## Why Python

This version uses the official `highrise-bot-sdk==25.1.0`, which is newer and better maintained than the current unofficial Node dependency. The first Python milestone targets core runtime parity: connection events, commands, joins/leaves, Firebase radio updates, outfit changes, periodic messages, logging, Pushover, Sentry, and Linear reporting.

## Setup

Install `uv`, then run from this folder. The app is pinned to Python 3.11 because the current Highrise SDK dependency tree does not build cleanly on Python 3.12.

```bash
uv sync
cp .env.example .env
```

Fill in `.env` values. Secrets stay in the environment; non-secret room/radio settings live in `config/*.yaml`.

## Run

Recommended local command:

```bash
uv run python -m dz_highrise_bot --config config.test --outfit formal
```

The official Highrise CLI also works:

```bash
DZ_BOT_CONFIG=config.test DZ_BOT_OUTFIT=formal uv run highrise dz_highrise_bot.bot:DesiZoneBot "$HIGHRISE_ROOM_ID" "$HIGHRISE_TOKEN_TEST"
```

The Highrise CLI currently emits a `pkg_resources` deprecation warning from the SDK. The project pins `setuptools<81` so the CLI still works.

## Windows Service with NSSM

Use NSSM when the bot should run continuously on a Windows server and restart after crashes or reboots.

1. Install Python 3.11, Node.js, `uv`, and NSSM.
2. Clone or copy this repository to a stable path, for example `C:\bots\dz-highrise-djbot-js`.
3. Open PowerShell as Administrator and prepare the Python app:

```powershell
cd C:\bots\dz-highrise-djbot-js\python-bot
uv sync
copy .env.example .env
notepad .env
```

Fill `.env` with the required live values. At minimum, set `HIGHRISE_TOKEN`, `HIGHRISE_ROOM_ID`, `HIGHRISE_BOT_ID`, `DESIZONE_API_KEY`, and `FIREBASE_CREDENTIALS_PATH`.

Create log folders for NSSM stdout and stderr:

```powershell
mkdir C:\bots\dz-highrise-djbot-js\logs\nssm
```

Install the service:

```powershell
nssm install DzHighriseBot
```

In the NSSM window, use these values:

- **Application path:** `C:\Users\<user>\.local\bin\uv.exe` or the full path returned by `where uv`
- **Startup directory:** `C:\bots\dz-highrise-djbot-js\python-bot`
- **Arguments:** `run python -m dz_highrise_bot --config config --outfit formal`
- **Output:** `C:\bots\dz-highrise-djbot-js\logs\nssm\dz-highrise-bot.out.log`
- **Error:** `C:\bots\dz-highrise-djbot-js\logs\nssm\dz-highrise-bot.err.log`

On the **Exit actions** tab, set **Restart** for the default action. On the **I/O** tab, enable file rotation if the server will run for long periods.

Start and manage the service:

```powershell
nssm start DzHighriseBot
nssm status DzHighriseBot
nssm restart DzHighriseBot
nssm stop DzHighriseBot
```

For a test-room service, install a second service with a different name and config:

```powershell
nssm install DzHighriseBotTest
```

Use the same application path and startup directory, but set arguments to:

```text
run python -m dz_highrise_bot --config config.test --outfit formal
```

To update the bot, stop the service, pull/copy the latest code, sync dependencies, then restart:

```powershell
nssm stop DzHighriseBot
cd C:\bots\dz-highrise-djbot-js\python-bot
uv sync
nssm start DzHighriseBot
```

## Smoke Check

This validates imports and all three config files without opening a Highrise websocket:

```bash
uv run python -m dz_highrise_bot --config config.test --smoke
```

## Tests

```bash
uv run pytest
```

## Migration Notes

- `config/config.yaml`, `config/config2.yaml`, and `config/config.test.yaml` mirror the existing JS config names.
- Outfit data is loaded from the existing legacy JS outfit modules during the side-by-side phase to avoid hand-copying large arrays.
- Logs continue to write under the parent repo's `logs/` directory with the same radio-specific naming pattern.
- Firebase paths remain `DesiZoneRadio/Stations/Radio<radioid>/playing/0` and `DesiZoneRadio/Stations/Radio<radioid>/currentevent/0`.
- Azure deployment is intentionally not migrated yet.


## Repo
This project was split out from dz-highrise-djbot-js (branch codex/compare-node-and-python-maintenance) into dz-highrise-djbot-py.
