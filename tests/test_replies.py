from .helpers import auth_headers, create_board, create_post, login_user, register_user


def test_reply_crud_flow(client):
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)
    post = create_post(client, token=token, board_id=board["id"])

    create_reply = client.post(
        f"/posts/{post['id']}/replies",
        json={"content": "first reply"},
        headers=auth_headers(token),
    )
    assert create_reply.status_code == 201
    reply = create_reply.json()

    list_reply = client.get(f"/posts/{post['id']}/replies", params={"page": 1, "size": 10})
    assert list_reply.status_code == 200
    assert list_reply.json()["post"]["id"] == post["id"]
    assert list_reply.json()["post"]["content"] == post["content"]
    assert list_reply.json()["post"]["board_name"] == board["name"]
    assert list_reply.json()["total"] == 1
    assert list_reply.json()["items"][0]["id"] == reply["id"]
    assert list_reply.json()["items"][0]["author_username"] == "user001"
    assert list_reply.json()["items"][0]["author_nickname"] == "nick"
    assert list_reply.json()["items"][0]["post_title"] == post["title"]

    update_reply = client.put(f"/replies/{reply['id']}", json={"content": "updated"}, headers=auth_headers(token))
    assert update_reply.status_code == 200
    assert update_reply.json()["content"] == "updated"

    delete_reply = client.delete(f"/replies/{reply['id']}", headers=auth_headers(token))
    assert delete_reply.status_code == 200

    list_reply_after = client.get(f"/posts/{post['id']}/replies", params={"page": 1, "size": 10})
    assert list_reply_after.status_code == 200
    assert list_reply_after.json()["total"] == 0


def test_delete_post_cascades_reply_and_favorite(client):
    user = register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)
    post = create_post(client, token=token, board_id=board["id"])

    reply_resp = client.post(
        f"/posts/{post['id']}/replies",
        json={"content": "reply"},
        headers=auth_headers(token),
    )
    assert reply_resp.status_code == 201

    fav_resp = client.post("/favorites", json={"post_id": post["id"]}, headers=auth_headers(token))
    assert fav_resp.status_code == 409

    delete_post = client.delete(f"/posts/{post['id']}", headers=auth_headers(token))
    assert delete_post.status_code == 200

    reply_list = client.get(f"/posts/{post['id']}/replies", params={"page": 1, "size": 10})
    assert reply_list.status_code == 404

    favorites = client.get("/favorites", params={"user_id": user["id"], "page": 1, "size": 10})
    assert favorites.status_code == 200
    assert favorites.json()["total"] == 0


def test_reply_owner_permission_denied_for_other_user(client):
    register_user(client, username="user001", password="pass001")
    register_user(client, username="user002", password="pass002")
    token1 = login_user(client, username="user001", password="pass001")["token"]
    token2 = login_user(client, username="user002", password="pass002")["token"]

    board = create_board(client, token=token1)
    post = create_post(client, token=token1, board_id=board["id"])
    reply_resp = client.post(
        f"/posts/{post['id']}/replies",
        json={"content": "reply"},
        headers=auth_headers(token1),
    )
    assert reply_resp.status_code == 201
    reply_id = reply_resp.json()["id"]

    update_by_other = client.put(f"/replies/{reply_id}", json={"content": "hack"}, headers=auth_headers(token2))
    assert update_by_other.status_code == 403

    delete_by_other = client.delete(f"/replies/{reply_id}", headers=auth_headers(token2))
    assert delete_by_other.status_code == 403


def test_reply_auto_favorites_post_for_replier(client):
    user1 = register_user(client, username="user001", password="pass001")
    user2 = register_user(client, username="user002", password="pass002")
    token1 = login_user(client, username="user001", password="pass001")["token"]
    token2 = login_user(client, username="user002", password="pass002")["token"]

    board = create_board(client, token=token1)
    post = create_post(client, token=token1, board_id=board["id"])

    reply = client.post(
        f"/posts/{post['id']}/replies",
        json={"content": "reply and auto favorite"},
        headers=auth_headers(token2),
    )
    assert reply.status_code == 201

    user2_favs = client.get("/favorites", params={"user_id": user2["id"], "page": 1, "size": 10})
    assert user2_favs.status_code == 200
    assert user2_favs.json()["total"] == 1
    assert user2_favs.json()["items"][0]["id"] == post["id"]

    user1_favs = client.get("/favorites", params={"user_id": user1["id"], "page": 1, "size": 10})
    assert user1_favs.status_code == 200
    assert user1_favs.json()["total"] == 1
