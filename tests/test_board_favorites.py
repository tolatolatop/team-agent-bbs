from .helpers import auth_headers, create_board, create_post, login_user, register_user


def test_board_favorite_add_list_remove(client):
    """验证板块收藏增删查流程；关键点：自建板块自动收藏导致重复添加 409，删除后列表归零。"""
    user = register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token, name="fav-board")

    # Own board is auto-favorited by default behavior.
    add = client.post("/favorite-boards", json={"board_id": board["id"]}, headers=auth_headers(token))
    assert add.status_code == 409

    duplicate = client.post("/favorite-boards", json={"board_id": board["id"]}, headers=auth_headers(token))
    assert duplicate.status_code == 409

    fav_list = client.get("/favorite-boards", params={"user_id": user["id"], "page": 1, "size": 10})
    assert fav_list.status_code == 200
    assert fav_list.json()["total"] == 1
    assert fav_list.json()["items"][0]["id"] == board["id"]

    remove = client.delete("/favorite-boards", params={"board_id": board["id"]}, headers=auth_headers(token))
    assert remove.status_code == 200

    fav_list_after = client.get("/favorite-boards", params={"user_id": user["id"], "page": 1, "size": 10})
    assert fav_list_after.status_code == 200
    assert fav_list_after.json()["total"] == 0


def test_board_favorite_list_sorted_by_latest_board_activity(client):
    """验证收藏板块按最新活动排序；关键点：旧板块有新回复后应排在新板块前。"""
    user = register_user(client)
    token = login_user(client)["token"]

    old_board = create_board(client, token=token, name="old-board")
    new_board = create_board(client, token=token, name="new-board")

    old_post = create_post(client, token=token, board_id=old_board["id"], title="old", content="old-content")
    _new_post = create_post(client, token=token, board_id=new_board["id"], title="new", content="new-content")

    # Reply on old_board post makes old_board activity newer.
    bump = client.post(
        f"/posts/{old_post['id']}/replies",
        json={"content": "bump"},
        headers=auth_headers(token),
    )
    assert bump.status_code == 201

    fav_list = client.get("/favorite-boards", params={"user_id": user["id"], "page": 1, "size": 10})
    assert fav_list.status_code == 200
    ids = [item["id"] for item in fav_list.json()["items"]]
    assert ids[:2] == [old_board["id"], new_board["id"]]
