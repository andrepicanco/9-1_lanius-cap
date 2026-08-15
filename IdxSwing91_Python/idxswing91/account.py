"""Optional broker account configuration - lets scripts log in to a specific MT5
account/server themselves instead of requiring the terminal to already be open and
logged in manually. See config/account.example.yaml for the file format.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class AccountConfig:
    login: int | None = None
    password: str | None = None
    server: str | None = None
    path: str | None = None  # full path to terminal64.exe, only needed if MT5 can't find it itself

    def to_mt5_kwargs(self) -> dict:
        kwargs = {}
        if self.path:
            kwargs["path"] = self.path
        if self.login is not None:
            kwargs["login"] = self.login
        if self.password is not None:
            kwargs["password"] = self.password
        if self.server is not None:
            kwargs["server"] = self.server
        return kwargs


def load_account_config(path: str | Path) -> AccountConfig | None:
    """Returns None if the file doesn't exist - callers should fall back to connecting
    to whatever MT5 terminal is already open and logged in."""
    path = Path(path)
    if not path.exists():
        return None

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return AccountConfig(
        login=data.get("login"),
        password=data.get("password"),
        server=data.get("server"),
        path=data.get("path"),
    )
