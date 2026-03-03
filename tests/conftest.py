import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from team_bbs.config import DB_PATH, DEFAULT_DB
from team_bbs.main import app


@pytest.fixture(autouse=True)
def reset_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(DEFAULT_DB), encoding="utf-8")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
