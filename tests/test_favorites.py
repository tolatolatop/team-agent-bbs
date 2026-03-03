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
