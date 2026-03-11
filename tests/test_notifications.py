from .helpers import auth_headers, create_board, create_post, login_user, register_user


def test_notifications_sent_to_followers_only(client):
    """验证帖子事件只通知关注者；关键点：关注者收到 post_updated/new_reply，作者与未关注者不收到对应事件。"""
    register_user(client, username="user101", password="pass101")
    register_user(client, username="user102", password="pass102")
    register_user(client, username="user103", password="pass103")
    token1 = login_user(client, username="user101", password="pass101")["token"]
    token2 = login_user(client, username="user102", password="pass102")["token"]
    token3 = login_user(client, username="user103", password="pass103")["token"]

    board = create_board(client, token=token1)
    post = create_post(client, token=token1, board_id=board["id"], title="notify-post", content="v1")

    follow = client.post("/favorites", json={"post_id": post["id"]}, headers=auth_headers(token2))
    assert follow.status_code == 201

    update = client.put(f"/posts/{post['id']}", json={"content": "v2"}, headers=auth_headers(token1))
    assert update.status_code == 200

    n2 = client.get("/notifications", params={"page": 1, "size": 10}, headers=auth_headers(token2))
    assert n2.status_code == 200
    items2 = n2.json()["items"]
    post_updated_items = [item for item in items2 if item["event_type"] == "post_updated"]
    assert len(post_updated_items) == 1
    assert post_updated_items[0]["post_id"] == post["id"]
    assert post_updated_items[0]["post_title"] == "notify-post"

    n1 = client.get("/notifications", params={"page": 1, "size": 10}, headers=auth_headers(token1))
    assert n1.status_code == 200
    assert n1.json()["total"] == 0  # author excluded for post_updated

    n3 = client.get("/notifications", params={"page": 1, "size": 10}, headers=auth_headers(token3))
    assert n3.status_code == 200
    # user103 not favorite post, may still have board_created notification only.
    assert len([item for item in n3.json()["items"] if item["event_type"] == "post_updated"]) == 0

    reply = client.post(
        f"/posts/{post['id']}/replies",
        json={"content": "new reply"},
        headers=auth_headers(token1),
    )
    assert reply.status_code == 201

    n2_after = client.get("/notifications", params={"page": 1, "size": 10}, headers=auth_headers(token2))
    assert n2_after.status_code == 200
    event_types = [item["event_type"] for item in n2_after.json()["items"]]
    assert "new_reply" in event_types
    assert "post_updated" in event_types


def test_notification_read_and_unread_count(client):
    """验证通知已读与未读计数；关键点：单条已读后计数递减，全部已读后计数归零。"""
    register_user(client, username="user201", password="pass201")
    register_user(client, username="user202", password="pass202")
    token1 = login_user(client, username="user201", password="pass201")["token"]
    token2 = login_user(client, username="user202", password="pass202")["token"]

    board = create_board(client, token=token1)
    post = create_post(client, token=token1, board_id=board["id"], title="read-case", content="v1")
    follow = client.post("/favorites", json={"post_id": post["id"]}, headers=auth_headers(token2))
    assert follow.status_code == 201

    update = client.put(f"/posts/{post['id']}", json={"content": "v2"}, headers=auth_headers(token1))
    assert update.status_code == 200
    reply = client.post(f"/posts/{post['id']}/replies", json={"content": "r1"}, headers=auth_headers(token1))
    assert reply.status_code == 201

    unread = client.get("/notifications/unread-count", headers=auth_headers(token2))
    assert unread.status_code == 200
    assert unread.json()["unread"] >= 2

    listed = client.get("/notifications", params={"page": 1, "size": 10}, headers=auth_headers(token2))
    assert listed.status_code == 200
    notification_id = listed.json()["items"][0]["id"]

    mark_one = client.put(f"/notifications/{notification_id}/read", headers=auth_headers(token2))
    assert mark_one.status_code == 200
    assert mark_one.json()["is_read"] is True

    unread_after_one = client.get("/notifications/unread-count", headers=auth_headers(token2))
    assert unread_after_one.status_code == 200
    assert unread_after_one.json()["unread"] >= 1

    mark_all = client.put("/notifications/read-all", headers=auth_headers(token2))
    assert mark_all.status_code == 200

    unread_after_all = client.get("/notifications/unread-count", headers=auth_headers(token2))
    assert unread_after_all.status_code == 200
    assert unread_after_all.json()["unread"] == 0


def test_notification_dedupe_for_same_event_type(client):
    """验证同类型通知去重；关键点：短时间重复更新同一帖子只保留一条 post_updated 未读通知。"""
    register_user(client, username="user301", password="pass301")
    register_user(client, username="user302", password="pass302")
    token1 = login_user(client, username="user301", password="pass301")["token"]
    token2 = login_user(client, username="user302", password="pass302")["token"]

    board = create_board(client, token=token1)
    post = create_post(client, token=token1, board_id=board["id"], title="dedupe-post", content="v1")
    follow = client.post("/favorites", json={"post_id": post["id"]}, headers=auth_headers(token2))
    assert follow.status_code == 201

    update1 = client.put(f"/posts/{post['id']}", json={"content": "v2"}, headers=auth_headers(token1))
    assert update1.status_code == 200
    update2 = client.put(f"/posts/{post['id']}", json={"content": "v3"}, headers=auth_headers(token1))
    assert update2.status_code == 200

    listed = client.get("/notifications", params={"page": 1, "size": 10}, headers=auth_headers(token2))
    assert listed.status_code == 200
    post_updated_items = [item for item in listed.json()["items"] if item["event_type"] == "post_updated"]
    assert len(post_updated_items) == 1


def test_board_created_broadcast_to_all_other_users(client):
    """验证新建板块广播通知；关键点：创建者不接收，其他用户收到 board_created 且包含 board_id/board_name。"""
    register_user(client, username="user401", password="pass401")
    register_user(client, username="user402", password="pass402")
    register_user(client, username="user403", password="pass403")
    token1 = login_user(client, username="user401", password="pass401")["token"]
    token2 = login_user(client, username="user402", password="pass402")["token"]
    token3 = login_user(client, username="user403", password="pass403")["token"]

    board = create_board(client, token=token1, name="board-created-case")

    n1 = client.get("/notifications", params={"page": 1, "size": 20}, headers=auth_headers(token1))
    assert n1.status_code == 200
    assert len([item for item in n1.json()["items"] if item["event_type"] == "board_created"]) == 0

    n2 = client.get("/notifications", params={"page": 1, "size": 20}, headers=auth_headers(token2))
    assert n2.status_code == 200
    board_created2 = [item for item in n2.json()["items"] if item["event_type"] == "board_created"]
    assert len(board_created2) == 1
    assert board_created2[0]["board_id"] == board["id"]
    assert board_created2[0]["board_name"] == "board-created-case"
    assert board_created2[0]["post_id"] is None

    n3 = client.get("/notifications", params={"page": 1, "size": 20}, headers=auth_headers(token3))
    assert n3.status_code == 200
    board_created3 = [item for item in n3.json()["items"] if item["event_type"] == "board_created"]
    assert len(board_created3) == 1
    assert board_created3[0]["board_id"] == board["id"]


def test_new_post_in_board_notifies_board_followers_with_dedupe(client):
    """验证关注板块新帖通知与去重；关键点：关注者收到 new_post_in_board、发帖人不收到、窗口内去重生效。"""
    register_user(client, username="user501", password="pass501")
    register_user(client, username="user502", password="pass502")
    token1 = login_user(client, username="user501", password="pass501")["token"]
    token2 = login_user(client, username="user502", password="pass502")["token"]

    board = create_board(client, token=token1, name="board-follow-case")

    follow_board = client.post("/favorite-boards", json={"board_id": board["id"]}, headers=auth_headers(token2))
    assert follow_board.status_code == 201

    p1 = create_post(client, token=token1, board_id=board["id"], title="p1", content="c1")
    p2 = create_post(client, token=token1, board_id=board["id"], title="p2", content="c2")
    assert p1["id"] != p2["id"]

    n2 = client.get("/notifications", params={"page": 1, "size": 20}, headers=auth_headers(token2))
    assert n2.status_code == 200
    board_post_items = [item for item in n2.json()["items"] if item["event_type"] == "new_post_in_board"]
    # Within dedupe window only one notification remains.
    assert len(board_post_items) == 1
    assert board_post_items[0]["board_id"] == board["id"]
    assert board_post_items[0]["board_name"] == "board-follow-case"
    assert board_post_items[0]["post_title"] in {"p1", "p2"}

    n1 = client.get("/notifications", params={"page": 1, "size": 20}, headers=auth_headers(token1))
    assert n1.status_code == 200
    assert len([item for item in n1.json()["items"] if item["event_type"] == "new_post_in_board"]) == 0
