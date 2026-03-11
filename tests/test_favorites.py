from .helpers import auth_headers, create_board, create_post, login_user, register_user


def test_favorite_add_list_remove(client):
    user = register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)
    post = create_post(client, token=token, board_id=board["id"])

    # Own post is auto-favorited by default behavior.
    add = client.post("/favorites", json={"post_id": post["id"]}, headers=auth_headers(token))
    assert add.status_code == 409

    dup = client.post("/favorites", json={"post_id": post["id"]}, headers=auth_headers(token))
    assert dup.status_code == 409

    fav_list = client.get("/favorites", params={"user_id": user["id"], "page": 1, "size": 10})
    assert fav_list.status_code == 200
    assert fav_list.json()["total"] == 1
    assert fav_list.json()["items"][0]["id"] == post["id"]
    assert fav_list.json()["items"][0]["board_name"] == board["name"]
    assert fav_list.json()["items"][0]["author_username"] == user["username"]
    assert fav_list.json()["items"][0]["author_nickname"] == user["nickname"]

    remove = client.delete("/favorites", params={"post_id": post["id"]}, headers=auth_headers(token))
    assert remove.status_code == 200

    fav_list_after = client.get("/favorites", params={"user_id": user["id"], "page": 1, "size": 10})
    assert fav_list_after.status_code == 200
    assert fav_list_after.json()["total"] == 0


def test_favorites_sorted_by_post_latest_activity(client):
    user = register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)

    old_post = create_post(client, token=token, board_id=board["id"], title="old", content="old-content")
    new_post = create_post(client, token=token, board_id=board["id"], title="new", content="new-content")

    # Reply on old_post updates its activity, so favorites should return old_post first.
    reply = client.post(
        f"/posts/{old_post['id']}/replies",
        json={"content": "bump old post"},
        headers=auth_headers(token),
    )
    assert reply.status_code == 201

    fav_list = client.get("/favorites", params={"user_id": user["id"], "page": 1, "size": 10})
    assert fav_list.status_code == 200
    ids = [item["id"] for item in fav_list.json()["items"]]
    assert ids[:2] == [old_post["id"], new_post["id"]]


def test_favorite_remove_only_affects_current_user(client):
    user1 = register_user(client, username="user001", password="pass001")
    register_user(client, username="user002", password="pass002")
    token1 = login_user(client, username="user001", password="pass001")["token"]
    token2 = login_user(client, username="user002", password="pass002")["token"]

    board = create_board(client, token=token1)
    post = create_post(client, token=token1, board_id=board["id"])

    remove_user2 = client.delete("/favorites", params={"post_id": post["id"]}, headers=auth_headers(token2))
    assert remove_user2.status_code == 404

    user1_list = client.get("/favorites", params={"user_id": user1["id"], "page": 1, "size": 10})
    assert user1_list.status_code == 200
    assert user1_list.json()["total"] == 1
