from fastapi import Depends, FastAPI, Header, Query
from fastapi.exceptions import HTTPException

from . import schemas, services
from .storage import ensure_db_file


app = FastAPI(title="Team BBS", version="0.1.0")
ensure_db_file()


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
def create_board(payload: schemas.BoardCreateRequest) -> dict:
    return services.create_board(payload.model_dump())


@app.get("/boards", response_model=list[schemas.BoardOut])
def list_boards() -> list[dict]:
    return services.list_boards()


@app.get("/boards/{board_id}", response_model=schemas.BoardOut)
def get_board(board_id: int) -> dict:
    return services.get_board(board_id)


@app.post("/posts", response_model=schemas.PostOut, status_code=201)
def create_post(payload: schemas.PostCreateRequest) -> dict:
    return services.create_post(payload.model_dump())


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
def update_post(post_id: int, payload: schemas.PostUpdateRequest) -> dict:
    return services.update_post(post_id, payload.model_dump(exclude_unset=True))


@app.delete("/posts/{post_id}", response_model=schemas.MessageResponse)
def delete_post(post_id: int) -> dict:
    return services.delete_post(post_id)


@app.post("/posts/{post_id}/replies", response_model=schemas.ReplyOut, status_code=201)
def create_reply(post_id: int, payload: schemas.ReplyCreateRequest) -> dict:
    return services.create_reply(post_id, payload.model_dump())


@app.get("/posts/{post_id}/replies", response_model=schemas.PostRepliesViewResponse)
def list_replies(post_id: int, page: int = Query(1, ge=1), size: int = Query(10, ge=1, le=100)) -> dict:
    return services.list_replies(post_id=post_id, page=page, size=size)


@app.put("/replies/{reply_id}", response_model=schemas.ReplyOut)
def update_reply(reply_id: int, payload: schemas.ReplyUpdateRequest) -> dict:
    return services.update_reply(reply_id, payload.model_dump())


@app.delete("/replies/{reply_id}", response_model=schemas.MessageResponse)
def delete_reply(reply_id: int) -> dict:
    return services.delete_reply(reply_id)


@app.post("/favorites", status_code=201)
def add_favorite(payload: schemas.FavoriteRequest) -> dict:
    return services.add_favorite(payload.model_dump())


@app.delete("/favorites", response_model=schemas.MessageResponse)
def remove_favorite(user_id: int = Query(...), post_id: int = Query(...)) -> dict:
    return services.remove_favorite(user_id=user_id, post_id=post_id)


@app.get("/favorites", response_model=schemas.PaginatedResponse)
def list_favorites(
    user_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
) -> dict:
    return services.list_favorites(user_id=user_id, page=page, size=size)
