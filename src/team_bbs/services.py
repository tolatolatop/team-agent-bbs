import json
import math
import secrets
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, or_, select

from .db import SessionLocal
from .default_behaviors import ensure_board_favorite, ensure_post_favorite
from .models import Board, BoardFavorite, Favorite, Post, Reply, Token, User, now_utc


def _to_iso(dt: datetime) -> str:
    return dt.isoformat()


def paginate(items: list[dict[str, Any]], page: int, size: int) -> dict[str, Any]:
    total = len(items)
    total_pages = math.ceil(total / size) if total > 0 else 0
    start = (page - 1) * size
    end = start + size
    return {"items": items[start:end], "page": page, "size": size, "total": total, "total_pages": total_pages}


def _user_out(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "bio": user.bio,
        "created_at": _to_iso(user.created_at),
    }


def _board_out(board: Board) -> dict[str, Any]:
    return {"id": board.id, "name": board.name, "description": board.description, "created_at": _to_iso(board.created_at)}


def _post_out(post: Post) -> dict[str, Any]:
    return {
        "id": post.id,
        "board_id": post.board_id,
        "author_id": post.author_id,
        "title": post.title,
        "content": post.content,
        "tags": json.loads(post.tags or "[]"),
        "created_at": _to_iso(post.created_at),
        "updated_at": _to_iso(post.updated_at),
    }


def _reply_out(reply: Reply) -> dict[str, Any]:
    return {
        "id": reply.id,
        "post_id": reply.post_id,
        "author_id": reply.author_id,
        "content": reply.content,
        "created_at": _to_iso(reply.created_at),
        "updated_at": _to_iso(reply.updated_at),
    }


def _build_post_last_activity_map(db, posts: list[Post]) -> dict[int, datetime]:
    post_ids = [post.id for post in posts]
    if not post_ids:
        return {}

    reply_rows = db.execute(
        select(Reply.post_id, func.max(Reply.updated_at)).where(Reply.post_id.in_(post_ids)).group_by(Reply.post_id)
    ).all()
    reply_max_map = {post_id: max_updated for post_id, max_updated in reply_rows}

    activity_map: dict[int, datetime] = {}
    for post in posts:
        reply_time = reply_max_map.get(post.id)
        activity_map[post.id] = max(post.updated_at, reply_time) if reply_time else post.updated_at
    return activity_map


def _build_board_last_activity_map(posts: list[Post], post_activity_map: dict[int, datetime]) -> dict[int, datetime]:
    board_map: dict[int, datetime] = {}
    for post in posts:
        activity = post_activity_map[post.id]
        current = board_map.get(post.board_id)
        board_map[post.board_id] = activity if current is None or activity > current else current
    return board_map


def register_user(payload: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        exists = db.execute(select(User).where(User.username == payload["username"])).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already exists")

        user = User(
            username=payload["username"],
            password=payload["password"],
            nickname=payload["nickname"],
            bio=payload.get("bio", ""),
        )
        db.add(user)
        db.flush()
        db.refresh(user)
        return _user_out(user)


def login(payload: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        user = db.execute(
            select(User).where(and_(User.username == payload["username"], User.password == payload["password"]))
        ).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")

        token_value = secrets.token_hex(16)
        token = Token(token=token_value, user_id=user.id)
        db.add(token)
        return {"token": token_value, "user": _user_out(user)}


def get_me_by_token(token: str) -> dict[str, Any]:
    with SessionLocal() as db:
        token_row = db.execute(select(Token).where(Token.token == token)).scalar_one_or_none()
        if token_row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
        user = db.execute(select(User).where(User.id == token_row.user_id)).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token user not found")
        return _user_out(user)


def get_user(user_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
        return _user_out(user)


def list_users(page: int, size: int) -> dict[str, Any]:
    with SessionLocal() as db:
        users = db.execute(select(User).order_by(User.created_at.desc())).scalars().all()
        return paginate([_user_out(user) for user in users], page, size)


def create_board(payload: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        board = Board(name=payload["name"], description=payload.get("description", ""))
        db.add(board)
        db.flush()
        # Default behavior: auto-favorite user's own board.
        creator_id = payload.get("creator_id")
        if creator_id is not None:
            ensure_board_favorite(db, user_id=creator_id, board_id=board.id)
        db.refresh(board)
        return _board_out(board)


def list_boards() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        boards = db.execute(select(Board)).scalars().all()
        posts = db.execute(select(Post)).scalars().all()
        post_activity_map = _build_post_last_activity_map(db, posts)
        board_activity_map = _build_board_last_activity_map(posts, post_activity_map)

        boards.sort(
            key=lambda board: (
                board_activity_map.get(board.id) is not None,
                board_activity_map.get(board.id, now_utc().replace(year=1970)),
                board.created_at,
            ),
            reverse=True,
        )
        return [_board_out(board) for board in boards]


def get_board(board_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        board = db.execute(select(Board).where(Board.id == board_id)).scalar_one_or_none()
        if board is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="board not found")
        return _board_out(board)


def create_post(payload: dict[str, Any], current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        board = db.execute(select(Board).where(Board.id == payload["board_id"])).scalar_one_or_none()
        if board is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="board not found")
        author = db.execute(select(User).where(User.id == current_user_id)).scalar_one_or_none()
        if author is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="author not found")

        now = now_utc()
        post = Post(
            board_id=payload["board_id"],
            author_id=current_user_id,
            title=payload["title"],
            content=payload["content"],
            tags=json.dumps(payload.get("tags", [])),
            created_at=now,
            updated_at=now,
        )
        db.add(post)
        db.flush()
        # Default behavior: auto-favorite user's own post.
        ensure_post_favorite(db, user_id=current_user_id, post_id=post.id)
        db.refresh(post)
        return _post_out(post)


def list_posts(page: int, size: int, board_id: int | None = None, keyword: str | None = None) -> dict[str, Any]:
    with SessionLocal() as db:
        stmt = select(Post)
        if board_id is not None:
            stmt = stmt.where(Post.board_id == board_id)
        if keyword:
            query = f"%{keyword.lower()}%"
            stmt = stmt.where(or_(func.lower(Post.title).like(query), func.lower(Post.content).like(query), func.lower(Post.tags).like(query)))

        posts = db.execute(stmt).scalars().all()
        activity_map = _build_post_last_activity_map(db, posts)
        posts.sort(key=lambda post: activity_map.get(post.id, post.updated_at), reverse=True)
        return paginate([_post_out(post) for post in posts], page, size)


def get_post(post_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        post = db.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")
        return _post_out(post)


def update_post(post_id: int, payload: dict[str, Any], current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        post = db.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")
        if post.author_id != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

        if payload.get("title") is not None:
            post.title = payload["title"]
        if payload.get("content") is not None:
            post.content = payload["content"]
        if payload.get("tags") is not None:
            post.tags = json.dumps(payload["tags"])
        post.updated_at = now_utc()
        db.flush()
        db.refresh(post)
        return _post_out(post)


def delete_post(post_id: int, current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        post = db.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")
        if post.author_id != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

        db.execute(delete(Reply).where(Reply.post_id == post_id))
        db.execute(delete(Favorite).where(Favorite.post_id == post_id))
        db.execute(delete(Post).where(Post.id == post_id))
        return {"message": "post deleted"}


def create_reply(post_id: int, payload: dict[str, Any], current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        post = db.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")
        author = db.execute(select(User).where(User.id == current_user_id)).scalar_one_or_none()
        if author is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="author not found")

        now = now_utc()
        reply = Reply(post_id=post_id, author_id=current_user_id, content=payload["content"], created_at=now, updated_at=now)
        db.add(reply)
        db.flush()
        # Default behavior: replying a post auto-favorites that post for the replier.
        ensure_post_favorite(db, user_id=current_user_id, post_id=post_id)
        db.refresh(reply)
        return _reply_out(reply)


def list_replies(post_id: int, page: int, size: int) -> dict[str, Any]:
    with SessionLocal() as db:
        post = db.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")

        replies = db.execute(select(Reply).where(Reply.post_id == post_id)).scalars().all()
        replies.sort(key=lambda reply: reply.updated_at, reverse=True)
        result = paginate([_reply_out(reply) for reply in replies], page, size)
        result["post"] = _post_out(post)
        return result


def update_reply(reply_id: int, payload: dict[str, Any], current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        reply = db.execute(select(Reply).where(Reply.id == reply_id)).scalar_one_or_none()
        if reply is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reply not found")
        if reply.author_id != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        reply.content = payload["content"]
        reply.updated_at = now_utc()
        db.flush()
        db.refresh(reply)
        return _reply_out(reply)


def delete_reply(reply_id: int, current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        reply = db.execute(select(Reply).where(Reply.id == reply_id)).scalar_one_or_none()
        if reply is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reply not found")
        if reply.author_id != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        db.execute(delete(Reply).where(Reply.id == reply_id))
        return {"message": "reply deleted"}


def add_favorite(payload: dict[str, Any], current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        user = db.execute(select(User).where(User.id == current_user_id)).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
        post = db.execute(select(Post).where(Post.id == payload["post_id"])).scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")

        exists = db.execute(
            select(Favorite).where(and_(Favorite.user_id == current_user_id, Favorite.post_id == payload["post_id"]))
        ).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="favorite already exists")

        favorite = Favorite(user_id=current_user_id, post_id=payload["post_id"])
        db.add(favorite)
        db.flush()
        db.refresh(favorite)
        return {"id": favorite.id, "user_id": favorite.user_id, "post_id": favorite.post_id, "created_at": _to_iso(favorite.created_at)}


def remove_favorite(post_id: int, current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        favorite = db.execute(
            select(Favorite).where(and_(Favorite.user_id == current_user_id, Favorite.post_id == post_id))
        ).scalar_one_or_none()
        if favorite is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="favorite not found")
        db.execute(delete(Favorite).where(Favorite.id == favorite.id))
        return {"message": "favorite removed"}


def list_favorites(user_id: int, page: int, size: int) -> dict[str, Any]:
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

        favorite_rows = db.execute(select(Favorite).where(Favorite.user_id == user_id)).scalars().all()
        post_ids = [fav.post_id for fav in favorite_rows]
        posts = db.execute(select(Post).where(Post.id.in_(post_ids))).scalars().all() if post_ids else []
        post_map = {post.id: post for post in posts}
        activity_map = _build_post_last_activity_map(db, posts)
        posts = [post_map[fav.post_id] for fav in favorite_rows if fav.post_id in post_map]
        posts.sort(key=lambda post: activity_map.get(post.id, post.updated_at), reverse=True)
        return paginate([_post_out(post) for post in posts], page, size)


def add_board_favorite(payload: dict[str, Any], current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        user = db.execute(select(User).where(User.id == current_user_id)).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
        board = db.execute(select(Board).where(Board.id == payload["board_id"])).scalar_one_or_none()
        if board is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="board not found")

        exists = db.execute(
            select(BoardFavorite).where(
                and_(BoardFavorite.user_id == current_user_id, BoardFavorite.board_id == payload["board_id"])
            )
        ).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="board favorite already exists")

        board_favorite = BoardFavorite(user_id=current_user_id, board_id=payload["board_id"])
        db.add(board_favorite)
        db.flush()
        db.refresh(board_favorite)
        return {
            "id": board_favorite.id,
            "user_id": board_favorite.user_id,
            "board_id": board_favorite.board_id,
            "created_at": _to_iso(board_favorite.created_at),
        }


def remove_board_favorite(board_id: int, current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        row = db.execute(
            select(BoardFavorite).where(and_(BoardFavorite.user_id == current_user_id, BoardFavorite.board_id == board_id))
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="board favorite not found")
        db.execute(delete(BoardFavorite).where(BoardFavorite.id == row.id))
        return {"message": "board favorite removed"}


def list_board_favorites(user_id: int, page: int, size: int) -> dict[str, Any]:
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

        favorite_rows = db.execute(select(BoardFavorite).where(BoardFavorite.user_id == user_id)).scalars().all()
        board_ids = [fav.board_id for fav in favorite_rows]
        boards = db.execute(select(Board).where(Board.id.in_(board_ids))).scalars().all() if board_ids else []
        board_map = {board.id: board for board in boards}

        posts = db.execute(select(Post).where(Post.board_id.in_(board_ids))).scalars().all() if board_ids else []
        post_activity_map = _build_post_last_activity_map(db, posts)
        board_activity_map = _build_board_last_activity_map(posts, post_activity_map)

        boards = [board_map[fav.board_id] for fav in favorite_rows if fav.board_id in board_map]
        boards.sort(
            key=lambda board: (
                board_activity_map.get(board.id) is not None,
                board_activity_map.get(board.id, now_utc().replace(year=1970)),
                board.created_at,
            ),
            reverse=True,
        )
        return paginate([_board_out(board) for board in boards], page, size)


def simple_search(keyword: str) -> dict[str, Any]:
    search_keyword = keyword.strip()
    if not search_keyword:
        return {"keyword": keyword, "posts": [], "replies": []}

    with SessionLocal() as db:
        query = f"%{search_keyword.lower()}%"

        posts = db.execute(select(Post).where(func.lower(Post.title).like(query))).scalars().all()
        replies = db.execute(select(Reply).where(func.lower(Reply.content).like(query))).scalars().all()

        return {
            "keyword": keyword,
            "posts": [_post_out(post) for post in posts],
            "replies": [_reply_out(reply) for reply in replies],
        }
