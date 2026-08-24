"""Telegram Bot API client - sendMessage/sendPhoto only. Reads the bot token and chat id
from environment variables ONLY (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) - never from YAML
or a CLI flag, so they can't accidentally end up committed in a config file.
"""

import os
from pathlib import Path

import requests

_API_BASE = "https://api.telegram.org/bot{token}/{method}"


class TelegramConfigError(RuntimeError):
    pass


def _credentials() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise TelegramConfigError(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must both be set as environment variables"
        )
    return token, chat_id


def send_message(text: str) -> None:
    token, chat_id = _credentials()
    url = _API_BASE.format(token=token, method="sendMessage")
    resp = requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=30)
    resp.raise_for_status()


def send_photo(path: str | Path, caption: str | None = None) -> None:
    token, chat_id = _credentials()
    url = _API_BASE.format(token=token, method="sendPhoto")
    with open(path, "rb") as f:
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        resp = requests.post(url, data=data, files={"photo": f}, timeout=60)
    resp.raise_for_status()
