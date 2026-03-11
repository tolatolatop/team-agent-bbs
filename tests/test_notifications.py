from .helpers import auth_headers, create_board, create_post, login_user, register_user


def test_notifications_sent_to_followers_only(client):
    user1 = register_user(client, username="user101", password="pass101")
    user2 = register_user(client, username="user102", password="pass102")
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
    assert n2.json()["total"] == 1
    assert n2.json()["items"][0]["event_type"] == "post_updated"
    assert n2.json()["items"][0]["post_id"] == post["id"]
    assert n2.json()["items"][0]["post_title"] == "notify-post"

    n1 = client.get("/notifications", params={"page": 1, "size": 10}, headers=auth_headers(token1))
    assert n1.status_code == 200
    assert n1.json()["total"] == 0

    n3 = client.get("/notifications", params={"page": 1, "size": 10}, headers=auth_headers(token3))
    assert n3.status_code == 200
    assert n3.json()["total"] == 0

    reply = client.post(
        f"/posts/{post['id']}/replies",
        json={"content": "new reply"},
        headers=auth_headers(token1),
    )
    assert reply.status_code == 201

    n2_after = client.get("/notifications", params={"page": 1, "size": 10}, headers=auth_headers(token2))
    assert n2_after.status_code == 200
    assert n2_after.json()["total"] == 2
    assert n2_after.json()["items"][0]["event_type"] == "new_reply"
    assert n2_after.json()["items"][1]["event_type"] == "post_updated"


def test_notification_read_and_unread_count(client):
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
    assert unread.json()["unread"] == 2

    listed = client.get("/notifications", params={"page": 1, "size": 10}, headers=auth_headers(token2))
    assert listed.status_code == 200
    notification_id = listed.json()["items"][0]["id"]

    mark_one = client.put(f"/notifications/{notification_id}/read", headers=auth_headers(token2))
    assert mark_one.status_code == 200
    assert mark_one.json()["is_read"] is True

    unread_after_one = client.get("/notifications/unread-count", headers=auth_headers(token2))
    assert unread_after_one.status_code == 200
    assert unread_after_one.json()["unread"] == 1

    mark_all = client.put("/notifications/read-all", headers=auth_headers(token2))
    assert mark_all.status_code == 200

    unread_after_all = client.get("/notifications/unread-count", headers=auth_headers(token2))
    assert unread_after_all.status_code == 200
    assert unread_after_all.json()["unread"] == 0


def test_notification_dedupe_for_same_event_type(client):
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
