import json
import math
import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, or_, select

from .db import SessionLocal
from .default_behaviors import ensure_board_favorite, ensure_post_favorite
from .models import Board, BoardFavorite, Favorite, Notification, Post, Reply, Token, User, now_utc


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
        "is_admin": user.is_admin,
        "created_at": _to_iso(user.created_at),
    }


def _board_out(board: Board) -> dict[str, Any]:
    return {"id": board.id, "name": board.name, "description": board.description, "created_at": _to_iso(board.created_at)}


def _build_user_info_map(db, user_ids: set[int]) -> dict[int, tuple[str, str]]:
    if not user_ids:
        return {}
    users = db.execute(select(User).where(User.id.in_(user_ids))).scalars().all()
    return {user.id: (user.username, user.nickname) for user in users}


def _build_board_name_map(db, board_ids: set[int | None]) -> dict[int, str]:
    clean_ids = {board_id for board_id in board_ids if board_id is not None}
    if not clean_ids:
        return {}
    boards = db.execute(select(Board).where(Board.id.in_(clean_ids))).scalars().all()
    return {board.id: board.name for board in boards}


def _build_post_title_map(db, post_ids: set[int | None]) -> dict[int, str]:
    clean_ids = {post_id for post_id in post_ids if post_id is not None}
    if not clean_ids:
        return {}
    posts = db.execute(select(Post).where(Post.id.in_(clean_ids))).scalars().all()
    return {post.id: post.title for post in posts}


def _post_out(
    post: Post,
    board_name: str = "",
    author_username: str = "",
    author_nickname: str = "",
) -> dict[str, Any]:
    return {
        "id": post.id,
        "board_id": post.board_id,
        "board_name": board_name,
        "author_id": post.author_id,
        "author_username": author_username,
        "author_nickname": author_nickname,
        "title": post.title,
        "content": post.content,
        "tags": json.loads(post.tags or "[]"),
        "is_pinned": post.is_pinned,
        "created_at": _to_iso(post.created_at),
        "updated_at": _to_iso(post.updated_at),
    }


def _reply_out(
    reply: Reply,
    post_title: str = "",
    author_username: str = "",
    author_nickname: str = "",
) -> dict[str, Any]:
    return {
        "id": reply.id,
        "post_id": reply.post_id,
        "post_title": post_title,
        "author_id": reply.author_id,
        "author_username": author_username,
        "author_nickname": author_nickname,
        "content": reply.content,
        "created_at": _to_iso(reply.created_at),
        "updated_at": _to_iso(reply.updated_at),
    }


def _notification_message(event_type: str) -> str:
    if event_type == "post_updated":
        return "你关注的帖子有更新"
    if event_type == "new_reply":
        return "你关注的帖子有新回复"
    if event_type == "board_created":
        return "有新板块已创建"
    if event_type == "new_post_in_board":
        return "你关注的板块有新帖子"
    return "你关注的帖子有新动态"


def _notification_out(notification: Notification, post_title: str = "", board_name: str = "") -> dict[str, Any]:
    return {
        "id": notification.id,
        "user_id": notification.user_id,
        "post_id": notification.post_id,
        "board_id": notification.board_id,
        "post_title": post_title,
        "board_name": board_name,
        "event_type": notification.event_type,
        "message": notification.message,
        "is_read": notification.is_read,
        "event_at": _to_iso(notification.event_at),
        "created_at": _to_iso(notification.created_at),
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
            notify_all_users_board_created(db, board=board, actor_user_id=creator_id, event_at=now_utc())
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
        notify_board_followers_new_post(db, post=post, actor_user_id=current_user_id, event_at=now)
        db.refresh(post)
        return _post_out(
            post,
            board_name=board.name,
            author_username=author.username,
            author_nickname=author.nickname,
        )


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
        # Sort: pinned posts first (by pinned_at desc), then by activity desc
        posts.sort(key=lambda post: (not post.is_pinned, activity_map.get(post.id, post.updated_at) if not post.is_pinned else post.pinned_at or post.updated_at), reverse=False)
        posts.reverse()  # Reverse to get correct order
        board_name_map = _build_board_name_map(db, {post.board_id for post in posts})
        user_info_map = _build_user_info_map(db, {post.author_id for post in posts})
        items = []
        for post in posts:
            username, nickname = user_info_map.get(post.author_id, ("", ""))
            items.append(
                _post_out(
                    post,
                    board_name=board_name_map.get(post.board_id, ""),
                    author_username=username,
                    author_nickname=nickname,
                )
            )
        return paginate(items, page, size)


def pin_post(post_id: int, current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        # Check if user is admin
        user = db.execute(select(User).where(User.id == current_user_id)).scalar_one_or_none()
        if user is None or not user.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only admin can pin post")

        post = db.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")

        if post.is_pinned:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="post already pinned")

        # Check if board already has 3 pinned posts (P1 requirement)
        pinned_count = db.execute(
            select(func.count(Post.id)).where(and_(Post.board_id == post.board_id, Post.is_pinned == True))
        ).scalar_one()
        if pinned_count >= 3:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="board already has maximum 3 pinned posts")

        now = now_utc()
        post.is_pinned = True
        post.pinned_at = now
        post.pinned_by = current_user_id
        post.updated_at = now

        db.flush()
        db.refresh(post)
        board_name_map = _build_board_name_map(db, {post.board_id})
        user_info_map = _build_user_info_map(db, {post.author_id})
        username, nickname = user_info_map.get(post.author_id, ("", ""))
        return _post_out(
            post,
            board_name=board_name_map.get(post.board_id, ""),
            author_username=username,
            author_nickname=nickname,
        )


def unpin_post(post_id: int, current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        # Check if user is admin
        user = db.execute(select(User).where(User.id == current_user_id)).scalar_one_or_none()
        if user is None or not user.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only admin can unpin post")

        post = db.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")

        if not post.is_pinned:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="post is not pinned")

        now = now_utc()
        post.is_pinned = False
        post.pinned_at = None
        post.pinned_by = None
        post.updated_at = now

        db.flush()
        db.refresh(post)
        board_name_map = _build_board_name_map(db, {post.board_id})
        user_info_map = _build_user_info_map(db, {post.author_id})
        username, nickname = user_info_map.get(post.author_id, ("", ""))
        return _post_out(
            post,
            board_name=board_name_map.get(post.board_id, ""),
            author_username=username,
            author_nickname=nickname,
        )


def get_post(post_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        post = db.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")
        board_name_map = _build_board_name_map(db, {post.board_id})
        user_info_map = _build_user_info_map(db, {post.author_id})
        username, nickname = user_info_map.get(post.author_id, ("", ""))
        return _post_out(
            post,
            board_name=board_name_map.get(post.board_id, ""),
            author_username=username,
            author_nickname=nickname,
        )


def notify_post_followers(db, post: Post, actor_user_id: int, event_type: str, event_at: datetime) -> None:
    follower_rows = db.execute(select(Favorite.user_id).where(Favorite.post_id == post.id)).all()
    follower_ids = {user_id for user_id, in follower_rows if user_id != actor_user_id}
    if not follower_ids:
        return

    dedupe_window_start = event_at - timedelta(minutes=5)
    for follower_id in follower_ids:
        existing = db.execute(
            select(Notification)
            .where(
                and_(
                    Notification.user_id == follower_id,
                    Notification.post_id == post.id,
                    Notification.event_type == event_type,
                    Notification.is_read.is_(False),
                    Notification.created_at >= dedupe_window_start,
                )
            )
            .order_by(Notification.created_at.desc())
        ).scalar_one_or_none()
        if existing is not None:
            existing.event_at = event_at
            existing.message = _notification_message(event_type)
            continue
        db.add(
            Notification(
                user_id=follower_id,
                post_id=post.id,
                event_type=event_type,
                message=_notification_message(event_type),
                is_read=False,
                event_at=event_at,
            )
        )


def notify_all_users_board_created(db, board: Board, actor_user_id: int, event_at: datetime) -> None:
    user_rows = db.execute(select(User.id)).all()
    user_ids = {user_id for user_id, in user_rows if user_id != actor_user_id}
    if not user_ids:
        return
    for user_id in user_ids:
        db.add(
            Notification(
                user_id=user_id,
                post_id=None,
                board_id=board.id,
                event_type="board_created",
                message=_notification_message("board_created"),
                is_read=False,
                event_at=event_at,
            )
        )


def notify_board_followers_new_post(db, post: Post, actor_user_id: int, event_at: datetime) -> None:
    follower_rows = db.execute(select(BoardFavorite.user_id).where(BoardFavorite.board_id == post.board_id)).all()
    follower_ids = {user_id for user_id, in follower_rows if user_id != actor_user_id}
    if not follower_ids:
        return

    dedupe_window_start = event_at - timedelta(minutes=5)
    for follower_id in follower_ids:
        existing = db.execute(
            select(Notification)
            .where(
                and_(
                    Notification.user_id == follower_id,
                    Notification.board_id == post.board_id,
                    Notification.event_type == "new_post_in_board",
                    Notification.is_read.is_(False),
                    Notification.created_at >= dedupe_window_start,
                )
            )
            .order_by(Notification.created_at.desc())
        ).scalar_one_or_none()
        if existing is not None:
            existing.event_at = event_at
            existing.message = _notification_message("new_post_in_board")
            existing.post_id = post.id
            continue
        db.add(
            Notification(
                user_id=follower_id,
                post_id=post.id,
                board_id=post.board_id,
                event_type="new_post_in_board",
                message=_notification_message("new_post_in_board"),
                is_read=False,
                event_at=event_at,
            )
        )


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
        notify_post_followers(db, post=post, actor_user_id=current_user_id, event_type="post_updated", event_at=post.updated_at)
        db.flush()
        db.refresh(post)
        board_name_map = _build_board_name_map(db, {post.board_id})
        user_info_map = _build_user_info_map(db, {post.author_id})
        username, nickname = user_info_map.get(post.author_id, ("", ""))
        return _post_out(
            post,
            board_name=board_name_map.get(post.board_id, ""),
            author_username=username,
            author_nickname=nickname,
        )


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
        notify_post_followers(db, post=post, actor_user_id=current_user_id, event_type="new_reply", event_at=now)
        db.refresh(reply)
        return _reply_out(
            reply,
            post_title=post.title,
            author_username=author.username,
            author_nickname=author.nickname,
        )


def list_replies(post_id: int, page: int, size: int) -> dict[str, Any]:
    with SessionLocal() as db:
        post = db.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="post not found")

        replies = db.execute(select(Reply).where(Reply.post_id == post_id)).scalars().all()
        replies.sort(key=lambda reply: reply.updated_at, reverse=True)
        user_info_map = _build_user_info_map(db, {reply.author_id for reply in replies} | {post.author_id})
        board_name_map = _build_board_name_map(db, {post.board_id})
        reply_items = []
        for reply in replies:
            username, nickname = user_info_map.get(reply.author_id, ("", ""))
            reply_items.append(
                _reply_out(
                    reply,
                    post_title=post.title,
                    author_username=username,
                    author_nickname=nickname,
                )
            )
        result = paginate(reply_items, page, size)
        post_username, post_nickname = user_info_map.get(post.author_id, ("", ""))
        result["post"] = _post_out(
            post,
            board_name=board_name_map.get(post.board_id, ""),
            author_username=post_username,
            author_nickname=post_nickname,
        )
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
        user_info_map = _build_user_info_map(db, {reply.author_id})
        post_title_map = _build_post_title_map(db, {reply.post_id})
        username, nickname = user_info_map.get(reply.author_id, ("", ""))
        return _reply_out(
            reply,
            post_title=post_title_map.get(reply.post_id, ""),
            author_username=username,
            author_nickname=nickname,
        )


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
        board_name_map = _build_board_name_map(db, {post.board_id for post in posts})
        user_info_map = _build_user_info_map(db, {post.author_id for post in posts})
        items = []
        for post in posts:
            username, nickname = user_info_map.get(post.author_id, ("", ""))
            items.append(
                _post_out(
                    post,
                    board_name=board_name_map.get(post.board_id, ""),
                    author_username=username,
                    author_nickname=nickname,
                )
            )
        return paginate(items, page, size)


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


def list_notifications(current_user_id: int, page: int, size: int) -> dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(
            select(Notification)
            .where(Notification.user_id == current_user_id)
            .order_by(Notification.created_at.desc())
        ).scalars().all()
        post_title_map = _build_post_title_map(db, {row.post_id for row in rows})
        board_name_map = _build_board_name_map(db, {row.board_id for row in rows})
        items = [
            _notification_out(
                row,
                post_title=post_title_map.get(row.post_id, ""),
                board_name=board_name_map.get(row.board_id, ""),
            )
            for row in rows
        ]
        return paginate(items, page, size)


def get_unread_notification_count(current_user_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        unread = db.execute(
            select(func.count(Notification.id)).where(
                and_(Notification.user_id == current_user_id, Notification.is_read.is_(False))
            )
        ).scalar_one()
        return {"unread": unread}


def mark_notification_read(notification_id: int, current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        row = db.execute(select(Notification).where(Notification.id == notification_id)).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification not found")
        if row.user_id != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        row.is_read = True
        db.flush()
        db.refresh(row)
        post_title_map = _build_post_title_map(db, {row.post_id})
        board_name_map = _build_board_name_map(db, {row.board_id})
        return _notification_out(
            row,
            post_title=post_title_map.get(row.post_id, ""),
            board_name=board_name_map.get(row.board_id, ""),
        )


def mark_all_notifications_read(current_user_id: int) -> dict[str, Any]:
    with SessionLocal.begin() as db:
        rows = db.execute(
            select(Notification).where(
                and_(Notification.user_id == current_user_id, Notification.is_read.is_(False))
            )
        ).scalars().all()
        for row in rows:
            row.is_read = True
        return {"message": "all notifications marked as read"}


def list_unread_notification_targets() -> list[tuple[str, int]]:
    with SessionLocal() as db:
        rows = db.execute(
            select(User.username, func.count(Notification.id))
            .join(Notification, Notification.user_id == User.id)
            .where(Notification.is_read.is_(False))
            .group_by(User.id, User.username)
        ).all()
        return [(username, int(unread_count)) for username, unread_count in rows]


def simple_search(keyword: str) -> dict[str, Any]:
    search_keyword = keyword.strip()
    if not search_keyword:
        return {"keyword": keyword, "posts": [], "replies": []}

    with SessionLocal() as db:
        query = f"%{search_keyword.lower()}%"

        posts = db.execute(select(Post).where(func.lower(Post.title).like(query))).scalars().all()
        replies = db.execute(select(Reply).where(func.lower(Reply.content).like(query))).scalars().all()
        board_name_map = _build_board_name_map(db, {post.board_id for post in posts})
        post_user_map = _build_user_info_map(db, {post.author_id for post in posts})
        reply_user_map = _build_user_info_map(db, {reply.author_id for reply in replies})
        post_title_map = _build_post_title_map(db, {reply.post_id for reply in replies})

        return {
            "keyword": keyword,
            "posts": [
                _post_out(
                    post,
                    board_name=board_name_map.get(post.board_id, ""),
                    author_username=post_user_map.get(post.author_id, ("", ""))[0],
                    author_nickname=post_user_map.get(post.author_id, ("", ""))[1],
                )
                for post in posts
            ],
            "replies": [
                _reply_out(
                    reply,
                    post_title=post_title_map.get(reply.post_id, ""),
                    author_username=reply_user_map.get(reply.author_id, ("", ""))[0],
                    author_nickname=reply_user_map.get(reply.author_id, ("", ""))[1],
                )
                for reply in replies
            ],
        }
