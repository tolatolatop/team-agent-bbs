from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "db.json"

DEFAULT_DB = {
    "users": [],
    "boards": [],
    "posts": [],
    "replies": [],
    "favorites": [],
    "tokens": [],
    "counters": {
        "user_id_seq": 0,
        "board_id_seq": 0,
        "post_id_seq": 0,
        "reply_id_seq": 0,
        "favorite_id_seq": 0,
    },
}
