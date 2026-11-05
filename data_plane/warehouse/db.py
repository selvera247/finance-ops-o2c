from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb

from data_plane import config as data_config

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# DuckDB file DBs reject mixed read_only configs across concurrent connections
# ("Can't open a connection to same database file with a different configuration").
# Uvicorn runs sync routes in a threadpool; Copilot openCase fires case + evidence
# + audit in parallel — each ensure_schema (write) then query_dicts (was read_only).
# Serialize every open/use/close and always use read_only=False.
_LOCK = threading.RLock()
# DuckDBPyConnection rejects setattr — track connect()-held locks by id().
_CONNECT_HELD: set[int] = set()
_CONNECT_HELD_GUARD = threading.Lock()


@contextmanager
def connection(*, read_only: bool = False) -> Iterator[duckdb.DuckDBPyConnection]:
    """Serialized warehouse connection. ``read_only`` is ignored (API compat)."""
    del read_only
    data_config.ensure_dirs()
    with _LOCK:
        con = duckdb.connect(str(data_config.DUCKDB_PATH), read_only=False)
        try:
            yield con
        finally:
            con.close()


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the warehouse DB. Prefer ``connection()`` for new code.

    Caller MUST close via ``close_connection(con)`` (not bare ``con.close()``),
    otherwise the process-wide warehouse lock is leaked.
    """
    del read_only
    data_config.ensure_dirs()
    _LOCK.acquire()
    try:
        con = duckdb.connect(str(data_config.DUCKDB_PATH), read_only=False)
    except BaseException:
        _LOCK.release()
        raise
    with _CONNECT_HELD_GUARD:
        _CONNECT_HELD.add(id(con))
    return con


def close_connection(con: duckdb.DuckDBPyConnection | None) -> None:
    """Close a ``connect()`` result and release the warehouse lock."""
    if con is None:
        return
    cid = id(con)
    with _CONNECT_HELD_GUARD:
        held = cid in _CONNECT_HELD
        if held:
            _CONNECT_HELD.discard(cid)
    try:
        con.close()
    finally:
        if held:
            _LOCK.release()


def init_schema(con: duckdb.DuckDBPyConnection | None = None) -> None:
    if con is not None:
        con.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        return
    with connection() as owned:
        owned.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def query_dicts(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    with connection() as con:
        cur = con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def execute(sql: str, params: list[Any] | None = None) -> None:
    with connection() as con:
        con.execute(sql, params or [])
