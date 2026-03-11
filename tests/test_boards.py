from .helpers import auth_headers, create_board, create_post, login_user, register_user


def test_boards_sorted_by_latest_post_activity(client):
    """验证板块按最新帖子活动排序；关键点：回复会提升板块活跃度，空板块排在最后。"""
    register_user(client)
    token = login_user(client)["token"]

    empty_board = create_board(client, token=token, name="empty-board")
    old_board = create_board(client, token=token, name="old-board")
    new_board = create_board(client, token=token, name="new-board")

    old_post = create_post(client, token=token, board_id=old_board["id"], title="old-post", content="old")
    _new_post = create_post(client, token=token, board_id=new_board["id"], title="new-post", content="new")

    # Update old_board activity through a reply, then it should move to first.
    reply = client.post(
        f"/posts/{old_post['id']}/replies",
        json={"content": "bump board"},
        headers=auth_headers(token),
    )
    assert reply.status_code == 201

    boards = client.get("/boards")
    assert boards.status_code == 200
    ids = [item["id"] for item in boards.json()]
    assert ids[:2] == [old_board["id"], new_board["id"]]
    assert ids[-1] == empty_board["id"]
