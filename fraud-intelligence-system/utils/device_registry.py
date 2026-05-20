from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict


@dataclass
class DeviceRecord:
    device_id: str
    user_id: str | None
    status: str
    last_counter: int | None
    last_seen: str | None


_REGISTRY: Dict[str, DeviceRecord] = {}
_TABLE_READY = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _backend() -> str:
    return os.getenv("DEVICE_REGISTRY_BACKEND", "memory").lower()


def _db_url() -> str | None:
    return os.getenv("DEVICE_REGISTRY_DATABASE_URL") or os.getenv("DATABASE_URL")


def _use_postgres() -> bool:
    if _backend() == "postgres":
        return True
    return bool(_db_url())


def _get_conn():
    try:
        import psycopg2
    except Exception as exc:  # pragma: no cover - only hit when dependency missing
        raise RuntimeError(
            "psycopg2 is required for the Postgres device registry. "
            "Install requirements and set DATABASE_URL."
        ) from exc
    return psycopg2.connect(_db_url())


def _ensure_table() -> None:
    global _TABLE_READY
    if _TABLE_READY or not _use_postgres():
        return
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS device_registry (
                    device_id TEXT PRIMARY KEY,
                    user_id TEXT NULL,
                    status TEXT NOT NULL,
                    last_counter BIGINT NULL,
                    last_seen TIMESTAMPTZ NULL
                );
                """
            )
    _TABLE_READY = True


def register_device(
    device_id: str,
    user_id: str | None = None,
    status: str = "active",
    last_counter: int | None = None,
) -> DeviceRecord:
    if _use_postgres():
        _ensure_table()
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO device_registry (device_id, user_id, status, last_counter, last_seen)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (device_id) DO UPDATE
                    SET user_id = COALESCE(EXCLUDED.user_id, device_registry.user_id),
                        status = EXCLUDED.status,
                        last_counter = COALESCE(EXCLUDED.last_counter, device_registry.last_counter),
                        last_seen = EXCLUDED.last_seen
                    RETURNING device_id, user_id, status, last_counter, last_seen;
                    """,
                    (device_id, user_id, status, last_counter, _now_iso()),
                )
                row = cur.fetchone()
        return DeviceRecord(*row)

    record = _REGISTRY.get(device_id)
    if record:
        if user_id and not record.user_id:
            record.user_id = user_id
        if status:
            record.status = status
        if last_counter is not None:
            record.last_counter = last_counter
        record.last_seen = _now_iso()
        return record
    record = DeviceRecord(
        device_id=device_id,
        user_id=user_id,
        status=status,
        last_counter=last_counter,
        last_seen=_now_iso(),
    )
    _REGISTRY[device_id] = record
    return record


def get_device(device_id: str) -> DeviceRecord | None:
    if _use_postgres():
        _ensure_table()
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT device_id, user_id, status, last_counter, last_seen
                    FROM device_registry
                    WHERE device_id = %s;
                    """,
                    (device_id,),
                )
                row = cur.fetchone()
        return DeviceRecord(*row) if row else None
    return _REGISTRY.get(device_id)


def list_device_ids() -> list[str]:
    if _use_postgres():
        _ensure_table()
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT device_id FROM device_registry;")
                return [row[0] for row in cur.fetchall()]
    return list(_REGISTRY.keys())


def update_device_status(device_id: str, status: str) -> None:
    if _use_postgres():
        _ensure_table()
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE device_registry
                    SET status = %s, last_seen = %s
                    WHERE device_id = %s;
                    """,
                    (status, _now_iso(), device_id),
                )
        return
    record = _REGISTRY.get(device_id)
    if record:
        record.status = status
        record.last_seen = _now_iso()


def update_device_counter(device_id: str, counter: int) -> None:
    if _use_postgres():
        _ensure_table()
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE device_registry
                    SET last_counter = %s, last_seen = %s
                    WHERE device_id = %s;
                    """,
                    (counter, _now_iso(), device_id),
                )
        return
    record = _REGISTRY.get(device_id)
    if record:
        record.last_counter = counter
        record.last_seen = _now_iso()


def clear_registry() -> None:
    if _use_postgres():
        _ensure_table()
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM device_registry;")
        return
    _REGISTRY.clear()
