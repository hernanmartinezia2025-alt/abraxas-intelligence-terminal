from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from backend.app.storage.sqlite import connect, initialize_database


def _config_payload(indicators: list[dict]) -> tuple[str, str]:
    payload = json.dumps(indicators, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return payload, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _preset_detail(connection, preset_id: int) -> dict:
    row = connection.execute(
        """
        SELECT p.*, v.id AS version_id, v.indicators_json, v.config_hash, v.created_at AS version_created_at
        FROM chart_indicator_presets p
        LEFT JOIN chart_indicator_preset_versions v
          ON v.preset_id = p.id AND v.version_number = p.active_version
        WHERE p.id = ?
        """,
        (preset_id,),
    ).fetchone()
    if not row:
        raise ValueError("Chart indicator preset not found.")
    payload = dict(row)
    payload["indicators"] = json.loads(payload.pop("indicators_json") or "[]")
    return payload


def save_indicator_preset(name: str, symbol: str, timeframe: str, indicators: list[dict]) -> dict:
    initialize_database()
    now = datetime.now(timezone.utc).isoformat()
    config_json, config_hash = _config_payload(indicators)
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM chart_indicator_presets WHERE name = ? AND symbol = ? AND timeframe = ?",
            (name, symbol.upper(), timeframe),
        ).fetchone()
        if row:
            preset_id = int(row["id"])
            existing = connection.execute(
                "SELECT version_number FROM chart_indicator_preset_versions WHERE preset_id = ? AND config_hash = ?",
                (preset_id, config_hash),
            ).fetchone()
            if existing:
                version = int(existing["version_number"])
            else:
                version = int(row["active_version"] or 0) + 1
                connection.execute(
                    """
                    INSERT INTO chart_indicator_preset_versions (
                        preset_id, version_number, indicators_json, config_hash, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (preset_id, version, config_json, config_hash, now),
                )
            connection.execute(
                """
                UPDATE chart_indicator_presets
                SET status = 'active', active_version = ?, updated_at = ?
                WHERE id = ?
                """,
                (version, now, preset_id),
            )
        else:
            cursor = connection.execute(
                """
                INSERT INTO chart_indicator_presets (
                    name, symbol, timeframe, status, active_version, created_at, updated_at
                ) VALUES (?, ?, ?, 'active', 1, ?, ?)
                """,
                (name, symbol.upper(), timeframe, now, now),
            )
            preset_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO chart_indicator_preset_versions (
                    preset_id, version_number, indicators_json, config_hash, created_at
                ) VALUES (?, 1, ?, ?, ?)
                """,
                (preset_id, config_json, config_hash, now),
            )
        return _preset_detail(connection, preset_id)


def list_indicator_presets(symbol: str = "", timeframe: str = "", include_archived: bool = False) -> list[dict]:
    initialize_database()
    clauses: list[str] = []
    values: list[object] = []
    if symbol:
        clauses.append("p.symbol = ?")
        values.append(symbol.upper())
    if timeframe:
        clauses.append("p.timeframe = ?")
        values.append(timeframe)
    if not include_archived:
        clauses.append("p.status = 'active'")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT p.*, v.id AS version_id, v.indicators_json, v.config_hash,
                   v.created_at AS version_created_at
            FROM chart_indicator_presets p
            LEFT JOIN chart_indicator_preset_versions v
              ON v.preset_id = p.id AND v.version_number = p.active_version
            {where}
            ORDER BY p.updated_at DESC, p.id DESC
            """,
            values,
        ).fetchall()
    payloads = []
    for row in rows:
        payload = dict(row)
        payload["indicators"] = json.loads(payload.pop("indicators_json") or "[]")
        payloads.append(payload)
    return payloads


def archive_indicator_preset(preset_id: int) -> dict:
    initialize_database()
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        cursor = connection.execute(
            "UPDATE chart_indicator_presets SET status = 'archived', updated_at = ? WHERE id = ?",
            (now, int(preset_id)),
        )
        if cursor.rowcount != 1:
            raise ValueError("Chart indicator preset not found.")
        return _preset_detail(connection, int(preset_id))
