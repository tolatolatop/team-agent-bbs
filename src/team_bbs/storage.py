import json
from copy import deepcopy
from threading import Lock
from typing import Any, Callable, TypeVar

from .config import DB_PATH, DEFAULT_DB


T = TypeVar("T")
DB_LOCK = Lock()


def _normalize_db(db: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(DEFAULT_DB)
    normalized.update(db or {})
    normalized["counters"] = deepcopy(DEFAULT_DB["counters"]) | (db.get("counters", {}) if db else {})
    return normalized


def ensure_db_file() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        with DB_PATH.open("w", encoding="utf-8") as file:
            json.dump(DEFAULT_DB, file, indent=2)


def _read_db_unlocked() -> dict[str, Any]:
    ensure_db_file()
    with DB_PATH.open("r", encoding="utf-8") as file:
        raw = json.load(file)
    return _normalize_db(raw)


def _write_db_unlocked(db: dict[str, Any]) -> None:
    ensure_db_file()
    with DB_PATH.open("w", encoding="utf-8") as file:
        json.dump(db, file, indent=2)


def load_db() -> dict[str, Any]:
    with DB_LOCK:
        return _read_db_unlocked()


def save_db(db: dict[str, Any]) -> None:
    with DB_LOCK:
        _write_db_unlocked(_normalize_db(db))


def next_id(db: dict[str, Any], entity: str) -> int:
    key = f"{entity}_id_seq"
    counters = db.setdefault("counters", {})
    counters[key] = int(counters.get(key, 0)) + 1
    return counters[key]


def write_db(mutator: Callable[[dict[str, Any]], T]) -> T:
    with DB_LOCK:
        db = _read_db_unlocked()
        result = mutator(db)
        _write_db_unlocked(db)
    return result
