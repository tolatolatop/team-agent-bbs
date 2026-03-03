import os

from fastapi import Depends, FastAPI, Header, Query
from fastapi.exceptions import HTTPException

from . import schemas, services
from .db import init_db


HOST = os.getenv("HOST", "127.0.0.1")
PORT = os.getenv("PORT", "8000")
OPENAPI_SCHEME = os.getenv("OPENAPI_SCHEME", "http")
OPENAPI_SERVER_URL = os.getenv("OPENAPI_SERVER_URL")
OPENAPI_HOST = os.getenv("OPENAPI_HOST", "127.0.0.1" if HOST == "0.0.0.0" else HOST)
OPENAPI_PORT = os.getenv("OPENAPI_PORT", PORT)
SERVER_URL = OPENAPI_SERVER_URL or f"{OPENAPI_SCHEME}://{OPENAPI_HOST}:{OPENAPI_PORT}"

app = FastAPI(
    title="Team BBS",
    version="0.1.0",
    servers=[{"url": SERVER_URL}],
)
init_db()


def parse_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing authorization header")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="invalid authorization header")
    return authorization[len(prefix) :].strip()


def current_user(authorization: str | None = Header(default=None)) -> dict:
    token = parse_bearer_token(authorization)
    return services.get_me_by_token(token)


def current_user_id(user: dict = Depends(current_user)) -> int:
    return user["id"]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=schemas.UserOut, status_code=201)
def register(payload: schemas.RegisterRequest) -> dict:
    return services.register_user(payload.model_dump())


@app.post("/auth/login", response_model=schemas.AuthResponse)
def login(payload: schemas.LoginRequest) -> dict:
    return services.login(payload.model_dump())


@app.get("/auth/me", response_model=schemas.UserOut)
def me(user: dict = Depends(current_user)) -> dict:
    return user


@app.get("/users/{user_id}", response_model=schemas.UserOut)
def get_user(user_id: int) -> dict:
    return services.get_user(user_id)


@app.get("/users", response_model=schemas.PaginatedResponse)
def list_users(page: int = Query(1, ge=1), size: int = Query(10, ge=1, le=100)) -> dict:
    return services.list_users(page=page, size=size)


@app.post("/boards", response_model=schemas.BoardOut, status_code=201)
def create_board(payload: schemas.BoardCreateRequest, user_id: int = Depends(current_user_id)) -> dict:
    data = payload.model_dump()
    data["creator_id"] = user_id
    return services.create_board(data)


@app.get("/boards", response_model=list[schemas.BoardOut])
def list_boards() -> list[dict]:
    return services.list_boards()


@app.get("/boards/{board_id}", response_model=schemas.BoardOut)
def get_board(board_id: int) -> dict:
    return services.get_board(board_id)


@app.post("/posts", response_model=schemas.PostOut, status_code=201)
def create_post(payload: schemas.PostCreateRequest, user_id: int = Depends(current_user_id)) -> dict:
    return services.create_post(payload.model_dump(), current_user_id=user_id)


@app.get("/posts", response_model=schemas.PaginatedResponse)
def list_posts(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    board_id: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
) -> dict:
    return services.list_posts(page=page, size=size, board_id=board_id, keyword=keyword)


@app.get("/posts/{post_id}", response_model=schemas.PostOut)
def get_post(post_id: int) -> dict:
    return services.get_post(post_id)


@app.put("/posts/{post_id}", response_model=schemas.PostOut)
def update_post(post_id: int, payload: schemas.PostUpdateRequest, user_id: int = Depends(current_user_id)) -> dict:
    return services.update_post(post_id, payload.model_dump(exclude_unset=True), current_user_id=user_id)


@app.delete("/posts/{post_id}", response_model=schemas.MessageResponse)
def delete_post(post_id: int, user_id: int = Depends(current_user_id)) -> dict:
    return services.delete_post(post_id, current_user_id=user_id)


@app.post("/posts/{post_id}/replies", response_model=schemas.ReplyOut, status_code=201)
def create_reply(post_id: int, payload: schemas.ReplyCreateRequest, user_id: int = Depends(current_user_id)) -> dict:
    return services.create_reply(post_id, payload.model_dump(), current_user_id=user_id)


@app.get("/posts/{post_id}/replies", response_model=schemas.PostRepliesViewResponse)
def list_replies(post_id: int, page: int = Query(1, ge=1), size: int = Query(10, ge=1, le=100)) -> dict:
    return services.list_replies(post_id=post_id, page=page, size=size)


@app.put("/replies/{reply_id}", response_model=schemas.ReplyOut)
def update_reply(reply_id: int, payload: schemas.ReplyUpdateRequest, user_id: int = Depends(current_user_id)) -> dict:
    return services.update_reply(reply_id, payload.model_dump(), current_user_id=user_id)


@app.delete("/replies/{reply_id}", response_model=schemas.MessageResponse)
def delete_reply(reply_id: int, user_id: int = Depends(current_user_id)) -> dict:
    return services.delete_reply(reply_id, current_user_id=user_id)


@app.post("/favorites", status_code=201)
def add_favorite(payload: schemas.FavoriteRequest, user_id: int = Depends(current_user_id)) -> dict:
    return services.add_favorite(payload.model_dump(), current_user_id=user_id)


@app.delete("/favorites", response_model=schemas.MessageResponse)
def remove_favorite(post_id: int = Query(...), user_id: int = Depends(current_user_id)) -> dict:
    return services.remove_favorite(post_id=post_id, current_user_id=user_id)


@app.get("/favorites", response_model=schemas.PaginatedResponse)
def list_favorites(
    user_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
) -> dict:
    return services.list_favorites(user_id=user_id, page=page, size=size)


@app.post("/favorite-boards", status_code=201)
def add_board_favorite(payload: schemas.BoardFavoriteRequest, user_id: int = Depends(current_user_id)) -> dict:
    return services.add_board_favorite(payload.model_dump(), current_user_id=user_id)


@app.delete("/favorite-boards", response_model=schemas.MessageResponse)
def remove_board_favorite(board_id: int = Query(...), user_id: int = Depends(current_user_id)) -> dict:
    return services.remove_board_favorite(board_id=board_id, current_user_id=user_id)


@app.get("/favorite-boards", response_model=schemas.PaginatedResponse)
def list_board_favorites(
    user_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
) -> dict:
    return services.list_board_favorites(user_id=user_id, page=page, size=size)
