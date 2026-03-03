from .helpers import create_board, create_post, register_user


def test_boards_sorted_by_latest_post_activity(client):
    user = register_user(client)

    empty_board = create_board(client, name="empty-board")
    old_board = create_board(client, name="old-board")
    new_board = create_board(client, name="new-board")

    old_post = create_post(client, board_id=old_board["id"], author_id=user["id"], title="old-post", content="old")
    _new_post = create_post(client, board_id=new_board["id"], author_id=user["id"], title="new-post", content="new")

    # Update old_board activity through a reply, then it should move to first.
    reply = client.post(
        f"/posts/{old_post['id']}/replies",
        json={"author_id": user["id"], "content": "bump board"},
    )
    assert reply.status_code == 201

    boards = client.get("/boards")
    assert boards.status_code == 200
    ids = [item["id"] for item in boards.json()]
    assert ids[:2] == [old_board["id"], new_board["id"]]
    assert ids[-1] == empty_board["id"]
