def register_user(client, username: str = "user001", password: str = "pass001"):
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "password": password,
            "nickname": "nick",
            "bio": "bio",
        },
    )
    assert response.status_code == 201
    return response.json()


def login_user(client, username: str = "user001", password: str = "pass001"):
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()


def create_board(client, name: str = "general"):
    response = client.post("/boards", json={"name": name, "description": "desc"})
    assert response.status_code == 201
    return response.json()


def create_post(client, board_id: int, author_id: int, title: str = "hello", content: str = "fastapi forum"):
    response = client.post(
        "/posts",
        json={
            "board_id": board_id,
            "author_id": author_id,
            "title": title,
            "content": content,
            "tags": ["intro"],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_register_login_and_me(client):
    user = register_user(client)

    duplicate = client.post(
        "/auth/register",
        json={"username": "user001", "password": "pass001", "nickname": "n2", "bio": ""},
    )
    assert duplicate.status_code == 409

    auth = login_user(client)
    token = auth["token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["id"] == user["id"]

    no_token = client.get("/auth/me")
    assert no_token.status_code == 401


def test_board_post_search_and_pagination(client):
    user = register_user(client)
    board = create_board(client, name="tech")

    create_post(client, board_id=board["id"], author_id=user["id"], title="FastAPI tips", content="hello world")
    create_post(client, board_id=board["id"], author_id=user["id"], title="Python tricks", content="good practice")

    page1 = client.get("/posts", params={"page": 1, "size": 1})
    assert page1.status_code == 200
    data = page1.json()
    assert data["page"] == 1
    assert data["size"] == 1
    assert data["total"] == 2
    assert len(data["items"]) == 1

    search = client.get("/posts", params={"keyword": "fastapi", "page": 1, "size": 10})
    assert search.status_code == 200
    search_data = search.json()
    assert search_data["total"] == 1
    assert search_data["items"][0]["title"] == "FastAPI tips"

    by_board = client.get("/posts", params={"board_id": board["id"], "page": 1, "size": 10})
    assert by_board.status_code == 200
    assert by_board.json()["total"] == 2


def test_reply_crud_flow(client):
    user = register_user(client)
    board = create_board(client)
    post = create_post(client, board_id=board["id"], author_id=user["id"])

    create_reply = client.post(
        f"/posts/{post['id']}/replies",
        json={"author_id": user["id"], "content": "first reply"},
    )
    assert create_reply.status_code == 201
    reply = create_reply.json()

    list_reply = client.get(f"/posts/{post['id']}/replies", params={"page": 1, "size": 10})
    assert list_reply.status_code == 200
    assert list_reply.json()["total"] == 1
    assert list_reply.json()["items"][0]["id"] == reply["id"]

    update_reply = client.put(f"/replies/{reply['id']}", json={"content": "updated"})
    assert update_reply.status_code == 200
    assert update_reply.json()["content"] == "updated"

    delete_reply = client.delete(f"/replies/{reply['id']}")
    assert delete_reply.status_code == 200

    list_reply_after = client.get(f"/posts/{post['id']}/replies", params={"page": 1, "size": 10})
    assert list_reply_after.status_code == 200
    assert list_reply_after.json()["total"] == 0


def test_favorite_add_list_remove(client):
    user = register_user(client)
    board = create_board(client)
    post = create_post(client, board_id=board["id"], author_id=user["id"])

    add = client.post("/favorites", json={"user_id": user["id"], "post_id": post["id"]})
    assert add.status_code == 201

    dup = client.post("/favorites", json={"user_id": user["id"], "post_id": post["id"]})
    assert dup.status_code == 409

    fav_list = client.get("/favorites", params={"user_id": user["id"], "page": 1, "size": 10})
    assert fav_list.status_code == 200
    assert fav_list.json()["total"] == 1
    assert fav_list.json()["items"][0]["id"] == post["id"]

    remove = client.delete("/favorites", params={"user_id": user["id"], "post_id": post["id"]})
    assert remove.status_code == 200

    fav_list_after = client.get("/favorites", params={"user_id": user["id"], "page": 1, "size": 10})
    assert fav_list_after.status_code == 200
    assert fav_list_after.json()["total"] == 0


def test_delete_post_cascades_reply_and_favorite(client):
    user = register_user(client)
    board = create_board(client)
    post = create_post(client, board_id=board["id"], author_id=user["id"])

    reply_resp = client.post(
        f"/posts/{post['id']}/replies",
        json={"author_id": user["id"], "content": "reply"},
    )
    assert reply_resp.status_code == 201

    fav_resp = client.post("/favorites", json={"user_id": user["id"], "post_id": post["id"]})
    assert fav_resp.status_code == 201

    delete_post = client.delete(f"/posts/{post['id']}")
    assert delete_post.status_code == 200

    reply_list = client.get(f"/posts/{post['id']}/replies", params={"page": 1, "size": 10})
    assert reply_list.status_code == 404

    favorites = client.get("/favorites", params={"user_id": user["id"], "page": 1, "size": 10})
    assert favorites.status_code == 200
    assert favorites.json()["total"] == 0
