from __future__ import annotations

from backend.app.storage.bots import create_bot, create_bot_version, get_bot, list_bots


def list_saved_bots(limit: int = 100) -> dict:
    return list_bots(limit=limit)


def create_saved_bot(payload: dict) -> dict:
    return create_bot(payload=payload)


def get_saved_bot(bot_id: int) -> dict:
    return get_bot(bot_id=bot_id)


def create_saved_bot_version(bot_id: int, payload: dict) -> dict:
    return create_bot_version(bot_id=bot_id, payload=payload)
