from .helpers import create_board, create_post, register_user


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


def test_favorites_sorted_by_post_latest_activity(client):
    user = register_user(client)
    board = create_board(client)

    old_post = create_post(client, board_id=board["id"], author_id=user["id"], title="old", content="old-content")
    new_post = create_post(client, board_id=board["id"], author_id=user["id"], title="new", content="new-content")

    add_old = client.post("/favorites", json={"user_id": user["id"], "post_id": old_post["id"]})
    assert add_old.status_code == 201
    add_new = client.post("/favorites", json={"user_id": user["id"], "post_id": new_post["id"]})
    assert add_new.status_code == 201

    # Reply on old_post updates its activity, so favorites should return old_post first.
    reply = client.post(
        f"/posts/{old_post['id']}/replies",
        json={"author_id": user["id"], "content": "bump old post"},
    )
    assert reply.status_code == 201

    fav_list = client.get("/favorites", params={"user_id": user["id"], "page": 1, "size": 10})
    assert fav_list.status_code == 200
    ids = [item["id"] for item in fav_list.json()["items"]]
    assert ids[:2] == [old_post["id"], new_post["id"]]
