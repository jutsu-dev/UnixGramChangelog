from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from aiogram import Bot

from unixgram_changelog.config import Settings


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    result: dict[str, object] = {
        "bot_token_valid": False,
        "bot_username": None,
        "channel_id": settings.channel_id,
        "channel_accessible": False,
        "database_exists": False,
        "sqlite_quick_check": "missing",
        "admin_ids": sorted(settings.admin_ids),
    }

    database_path = Path(settings.database_path)
    if database_path.exists():
        result["database_exists"] = True
        connection = sqlite3.connect(database_path)
        try:
            check = connection.execute("PRAGMA quick_check").fetchone()
            result["sqlite_quick_check"] = check[0] if check else "unknown"
        finally:
            connection.close()

    bot = Bot(settings.bot_token)
    try:
        me = await bot.get_me()
        result["bot_token_valid"] = True
        result["bot_username"] = me.username
        await bot.get_chat(settings.channel_id)
        result["channel_accessible"] = True
    finally:
        await bot.session.close()

    print(json.dumps(result, ensure_ascii=True))
    if (
        result["bot_token_valid"] is not True
        or result["channel_accessible"] is not True
        or result["sqlite_quick_check"] not in {"ok", "missing"}
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
