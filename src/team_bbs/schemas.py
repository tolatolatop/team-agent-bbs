import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _event_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_event_id() -> str:
    return str(uuid.uuid4())


class EventType(str, Enum):
    POST_CREATED = "post_created"
    POST_UPDATED = "post_updated"
    NEW_REPLY = "new_reply"
    BOARD_CREATED = "board_created"
    NEW_POST_IN_BOARD = "new_post_in_board"


class StructuredEvent(BaseModel):
    """Typed event payload pushed through the event bus and delivered to webhooks."""

    event_id: str = Field(default_factory=_new_event_id)
    event_type: EventType
    post_id: int | None = None
    reply_id: int | None = None
    board_id: int | None = None
    source_user_id: int | None = None
    snippet: str = ""
    timestamp: str = Field(default_factory=_event_timestamp)
    action_url: str = ""


class WebhookCreateRequest(BaseModel):
    url: str = Field(min_length=1, max_length=512)
    events: list[str] = Field(default=["*"], min_length=1)
    secret: str = Field(min_length=16, max_length=128)


class WebhookOut(BaseModel):
    id: int
    user_id: int
    url: str
    events: list[str]
    is_active: bool
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    message: str
    message: str


class PaginatedResponse(BaseModel):
    items: list[Any]
    page: int
    size: int
    total: int
    total_pages: int


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=3, max_length=128)
    nickname: str = Field(min_length=1, max_length=64)
    bio: str = Field(default="", max_length=300)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    token: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    nickname: str
    bio: str
    created_at: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class BoardCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=300)


class BoardOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: str


class DisplayMode(str, Enum):
    PLAINTEXT = "plaintext"
    MULTIMEDIA = "multimedia"


class MultimediaItem(BaseModel):
    type: str = Field(pattern="^(image|video)$")
    url: str = Field(max_length=2048)
    description: str = Field(default="", max_length=200)


class PostCreateRequest(BaseModel):
    board_id: int
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)
    tags: list[str] = Field(default_factory=list)
    multimedia: list[MultimediaItem] = Field(default_factory=list)


class PostUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    tags: list[str] | None = None
    multimedia: list[MultimediaItem] | None = None


class PostOut(BaseModel):
    id: int
    board_id: int
    board_name: str
    author_id: int
    author_username: str
    author_nickname: str
    title: str
    content: str
    tags: list[str]
    multimedia: list[MultimediaItem] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ReplyCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class ReplyUpdateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class ReplyOut(BaseModel):
    id: int
    post_id: int
    post_title: str
    author_id: int
    author_username: str
    author_nickname: str
    content: str
    created_at: str
    updated_at: str


class PostRepliesViewResponse(BaseModel):
    post: PostOut
    items: list[ReplyOut]
    page: int
    size: int
    total: int
    total_pages: int


class FavoriteRequest(BaseModel):
    post_id: int


class BoardFavoriteRequest(BaseModel):
    board_id: int


class SimpleSearchResponse(BaseModel):
    keyword: str
    posts: list[PostOut]
    replies: list[ReplyOut]


class NotificationOut(BaseModel):
    id: int
    user_id: int
    post_id: int | None
    board_id: int | None
    post_title: str
    board_name: str
    event_type: str
    message: str
    is_read: bool
    event_at: str
    created_at: str


class UnreadCountResponse(BaseModel):
    unread: int
