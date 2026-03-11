import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
TEST_DB_PATH = ROOT_DIR / "data" / "test.db"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["NOTIFY_TASK_ENABLED"] = "false"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from team_bbs.db import engine
from team_bbs.main import app
from team_bbs.models import Base


@pytest.fixture(autouse=True)
def reset_db() -> None:
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
