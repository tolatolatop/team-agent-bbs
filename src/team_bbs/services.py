import math
import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from .storage import load_db, next_id, write_db


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def paginate(items: list[dict[str, Any]], page: int, size: int) -> dict[str, Any]:
    total = len(items)
    total_pages = math.ceil(total / size) if total > 0 else 0
    start = (page - 1) * size
    end = start + size
    return {
        "items": items[start:end],
        "page": page,
        "size": size,
        "total": total,
        "total_pages": total_pages,
    }


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "username": user["username"],
        "nickname": user.get("nickname", ""),
        "bio": user.get("bio", ""),
        "created_at": user["created_at"],
    }


def _get_by_id(items: list[dict[str, Any]], item_id: int) -> dict[str, Any] | None:
    for item in items:
        if item["id"] == item_id:
            return item
    return None


def _build_post_last_activity_map(db: dict[str, Any]) -> dict[int, str]:
    latest_reply_map: dict[int, str] = {}
    for reply in db["replies"]:
        post_id = reply["post_id"]
        reply_updated_at = reply["updated_at"]
        current_latest = latest_reply_map.get(post_id)
        if current_latest is None or reply_updated_at > current_latest:
            latest_reply_map[post_id] = reply_updated_at

    activity_map: dict[int, str] = {}
    for post in db["posts"]:
        post_updated_at = post["updated_at"]
        latest_reply_at = latest_reply_map.get(post["id"])
        if latest_reply_at is None or post_updated_at >= latest_reply_at:
            activity_map[post["id"]] = post_updated_at
        else:
            activity_map[post["id"]] = latest_reply_at
    return activity_map


def register_user(payload: dict[str, Any]) -> dict[str, Any]:
    def _mutate(db: dict[str, Any]) -> dict[str, Any]:
        for user in db["users"]:
            if user["username"] == payload["username"]:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already exists")

        user = {
            "id": next_id(db, "user"),
            "username": payload["username"],
            "password": payload["password"],
            "nickname": payload["nickname"],
            "bio": payload.get("bio", ""),
            "created_at": now_iso(),
        }
        db["users"].append(user)
        return _public_user(user)

    return write_db(_mutate)


def login(payload: dict[str, Any]) -> dict[str, Any]:
    def _mutate(db: dict[str, Any]) -> dict[str, Any]:
        matched_user = None
        for user in db["users"]:
            if user["username"] == payload["username"] and user["password"] == payload["password"]:
                matched_user = user
                break
        if matched_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")

        token = secrets.token_hex(16)
        db["tokens"].append({"token": token, "user_id": matched_user["id"], "created_at": now_iso()})
        return {"token": token, "user": _public_user(matched_user)}

    return write_db(_mutate)


def get_me_by_token(token: str) -> dict[str, Any]:
    db = load_db()
    user_id = None
    for row in db["tokens"]:
        if row["token"] == token:
            user_id = row["user_id"]
            break
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    user = _get_by_id(db["users"], user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token user not found")
    return _public_user(user)


def get_user(user_id: int) -> dict[str, Any]:
    db = load_db()
    user = _get_by_id(db["users"], user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return _public_user(user)


def list_users(page: int, size: int) -> dict[str, Any]:
    db = load_db()
    users = [_public_user(user) for user in db["users"]]
    users.sort(key=lambda item: item["created_at"], reverse=True)
    return paginate(users, page, size)


def create_board(payload: dict[str, Any]) -> dict[str, Any]:
    def _mutate(db: dict[str, Any]) -> dict[str, Any]:
        board = {
            "id": next_id(db, "board"),
            "name": payload["name"],
            "description": payload.get("description", ""),
            "created_at": now_iso(),
        }
        db["boards"].append(board)
        return board

    return write_db(_mutate)


def list_boards() -> list[dict[str, Any]]:
    db = load_db()
    boards = list(db["boards"])
    post_activity_map = _build_post_last_activity_map(db)
    board_latest_activity: dict[int, str] = {}
    for post in db["posts"]:
        board_id = post["board_id"]
        post_activity = post_activity_map[post["id"]]
        current_latest = board_latest_activity.get(board_id)
        if current_latest is None or post_activity > current_latest:
            board_latest_activity[board_id] = post_activity

    boards.sort(
        key=lambda board: (
            board_latest_activity.get(board["id"]) is not None,
            board_latest_activity.get(board["id"], ""),
            board["created_at"],
        ),
        reverse=True,
    )
    return boards


def get_board(board_id: int) -> dict[str, Any]:
    db = load_db()
    board = _get_by_id(db["boards"], board_id)
    if board is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="board not found")
    return board


def create_post(payload: dict[str, Any], current_user_id: int) -> dict[str, Any]:
    def _mutate(db: dict[str, Any]) -> dict[str, Any]:
        if _get_by_id(db["boards"], payload["board_id"]) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="board not found")
        if _get_by_id(db["users"], current_user_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="author not found")

        now = now_iso()
        post = {
            "id": next_id(db, "post"),
            "board_id": payload["board_id"],
            "author_id": current_user_id,
            "title": payload["title"],
            "content": payload["content"],
            "tags": payload.get("tags", []),
            "created_at": now,
            "updated_at": now,
        }
        db["posts"].append(post)
        return post

    return write_db(_mutate)


def list_posts(page: int, size: int, board_id: int | None = None, keyword: str | None = None) -> dict[str, Any]:
    db = load_db()
    posts = list(db["posts"])
    post_activity_map = _build_post_last_activity_map(db)

    if board_id is not None:
        posts = [post for post in posts if post["board_id"] == board_id]

    if keyword:
        query = keyword.lower()
        posts = [
            post
            for post in posts
            if query in post["title"].lower()
            or query in post["content"].lower()
            or any(query in tag.lower() for tag in post.get("tags", []))
        ]

    posts.sort(key=lambda item: post_activity_map.get(item["id"], item["updated_at"]), reverse=True)
    return paginate(posts, page, size)


def get_post(post_id: int) -> dict[str, Any]:
    db = load_db()
    post = _get_by_id(db["posts"], post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")
    return post


def update_post(post_id: int, payload: dict[str, Any], current_user_id: int) -> dict[str, Any]:
    def _mutate(db: dict[str, Any]) -> dict[str, Any]:
        post = _get_by_id(db["posts"], post_id)
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")
        if post["author_id"] != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

        if payload.get("title") is not None:
            post["title"] = payload["title"]
        if payload.get("content") is not None:
            post["content"] = payload["content"]
        if payload.get("tags") is not None:
            post["tags"] = payload["tags"]
        post["updated_at"] = now_iso()
        return post

    return write_db(_mutate)


def delete_post(post_id: int, current_user_id: int) -> dict[str, Any]:
    def _mutate(db: dict[str, Any]) -> dict[str, Any]:
        post = _get_by_id(db["posts"], post_id)
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")
        if post["author_id"] != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

        db["posts"] = [item for item in db["posts"] if item["id"] != post_id]
        db["replies"] = [item for item in db["replies"] if item["post_id"] != post_id]
        db["favorites"] = [item for item in db["favorites"] if item["post_id"] != post_id]
        return {"message": "post deleted"}

    return write_db(_mutate)


def create_reply(post_id: int, payload: dict[str, Any], current_user_id: int) -> dict[str, Any]:
    def _mutate(db: dict[str, Any]) -> dict[str, Any]:
        if _get_by_id(db["posts"], post_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")
        if _get_by_id(db["users"], current_user_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="author not found")

        now = now_iso()
        reply = {
            "id": next_id(db, "reply"),
            "post_id": post_id,
            "author_id": current_user_id,
            "content": payload["content"],
            "created_at": now,
            "updated_at": now,
        }
        db["replies"].append(reply)
        return reply

    return write_db(_mutate)


def list_replies(post_id: int, page: int, size: int) -> dict[str, Any]:
    db = load_db()
    post = _get_by_id(db["posts"], post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")

    replies = [item for item in db["replies"] if item["post_id"] == post_id]
    replies.sort(key=lambda item: item["updated_at"], reverse=True)
    result = paginate(replies, page, size)
    result["post"] = post
    return result


def update_reply(reply_id: int, payload: dict[str, Any], current_user_id: int) -> dict[str, Any]:
    def _mutate(db: dict[str, Any]) -> dict[str, Any]:
        reply = _get_by_id(db["replies"], reply_id)
        if reply is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reply not found")
        if reply["author_id"] != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        reply["content"] = payload["content"]
        reply["updated_at"] = now_iso()
        return reply

    return write_db(_mutate)


def delete_reply(reply_id: int, current_user_id: int) -> dict[str, Any]:
    def _mutate(db: dict[str, Any]) -> dict[str, Any]:
        reply = _get_by_id(db["replies"], reply_id)
        if reply is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reply not found")
        if reply["author_id"] != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        db["replies"] = [item for item in db["replies"] if item["id"] != reply_id]
        return {"message": "reply deleted"}

    return write_db(_mutate)


def add_favorite(payload: dict[str, Any], current_user_id: int) -> dict[str, Any]:
    def _mutate(db: dict[str, Any]) -> dict[str, Any]:
        if _get_by_id(db["users"], current_user_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
        if _get_by_id(db["posts"], payload["post_id"]) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")

        for item in db["favorites"]:
            if item["user_id"] == current_user_id and item["post_id"] == payload["post_id"]:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="favorite already exists")

        favorite = {
            "id": next_id(db, "favorite"),
            "user_id": current_user_id,
            "post_id": payload["post_id"],
            "created_at": now_iso(),
        }
        db["favorites"].append(favorite)
        return favorite

    return write_db(_mutate)


def remove_favorite(post_id: int, current_user_id: int) -> dict[str, Any]:
    def _mutate(db: dict[str, Any]) -> dict[str, Any]:
        before = len(db["favorites"])
        db["favorites"] = [
            item
            for item in db["favorites"]
            if not (item["user_id"] == current_user_id and item["post_id"] == post_id)
        ]
        if len(db["favorites"]) == before:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="favorite not found")
        return {"message": "favorite removed"}

    return write_db(_mutate)


def list_favorites(user_id: int, page: int, size: int) -> dict[str, Any]:
    db = load_db()
    if _get_by_id(db["users"], user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    post_activity_map = _build_post_last_activity_map(db)

    post_map = {post["id"]: post for post in db["posts"]}
    favorite_posts = []
    for favorite in db["favorites"]:
        if favorite["user_id"] == user_id and favorite["post_id"] in post_map:
            favorite_posts.append(post_map[favorite["post_id"]])

    favorite_posts.sort(key=lambda item: post_activity_map.get(item["id"], item["updated_at"]), reverse=True)
    return paginate(favorite_posts, page, size)
