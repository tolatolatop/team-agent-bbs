from typing import Any

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
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


class PostCreateRequest(BaseModel):
    board_id: int
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)
    tags: list[str] = Field(default_factory=list)


class PostUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    tags: list[str] | None = None


class PostOut(BaseModel):
    id: int
    board_id: int
    author_id: int
    title: str
    content: str
    tags: list[str]
    created_at: str
    updated_at: str


class ReplyCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class ReplyUpdateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class ReplyOut(BaseModel):
    id: int
    post_id: int
    author_id: int
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
