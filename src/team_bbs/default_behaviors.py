from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .models import BoardFavorite, Favorite


def ensure_post_favorite(db: Session, user_id: int, post_id: int) -> None:
    existing = db.execute(
        select(Favorite).where(and_(Favorite.user_id == user_id, Favorite.post_id == post_id))
    ).scalar_one_or_none()
    if existing is None:
        db.add(Favorite(user_id=user_id, post_id=post_id))


def ensure_board_favorite(db: Session, user_id: int, board_id: int) -> None:
    existing = db.execute(
        select(BoardFavorite).where(and_(BoardFavorite.user_id == user_id, BoardFavorite.board_id == board_id))
    ).scalar_one_or_none()
    if existing is None:
        db.add(BoardFavorite(user_id=user_id, board_id=board_id))
