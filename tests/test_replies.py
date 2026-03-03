from .helpers import create_board, create_post, register_user


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
    assert list_reply.json()["post"]["id"] == post["id"]
    assert list_reply.json()["post"]["content"] == post["content"]
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
