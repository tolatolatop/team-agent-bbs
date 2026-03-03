from .helpers import create_board, create_post, register_user


def test_board_post_search_and_pagination(client):
    user = register_user(client)
    board = create_board(client, name="tech")

    create_post(client, board_id=board["id"], author_id=user["id"], title="FastAPI tips", content="hello world")
    create_post(client, board_id=board["id"], author_id=user["id"], title="Python tricks", content="good practice")

    page1 = client.get("/posts", params={"page": 1, "size": 1})
    assert page1.status_code == 200
    data = page1.json()
    assert data["page"] == 1
    assert data["size"] == 1
    assert data["total"] == 2
    assert len(data["items"]) == 1

    search = client.get("/posts", params={"keyword": "fastapi", "page": 1, "size": 10})
    assert search.status_code == 200
    search_data = search.json()
    assert search_data["total"] == 1
    assert search_data["items"][0]["title"] == "FastAPI tips"

    by_board = client.get("/posts", params={"board_id": board["id"], "page": 1, "size": 10})
    assert by_board.status_code == 200
    assert by_board.json()["total"] == 2


def test_level1_not_found_and_conflict_errors(client):
    user = register_user(client)
    board = create_board(client)
    post = create_post(client, board_id=board["id"], author_id=user["id"])

    assert client.get("/users/99999").status_code == 404
    assert client.get("/boards/99999").status_code == 404
    assert client.get("/posts/99999").status_code == 404

    no_board_post = client.post(
        "/posts",
        json={"board_id": 99999, "author_id": user["id"], "title": "t", "content": "c", "tags": []},
    )
    assert no_board_post.status_code == 404

    no_author_post = client.post(
        "/posts",
        json={"board_id": board["id"], "author_id": 99999, "title": "t", "content": "c", "tags": []},
    )
    assert no_author_post.status_code == 404

    remove_missing_fav = client.delete("/favorites", params={"user_id": user["id"], "post_id": post["id"]})
    assert remove_missing_fav.status_code == 404


def test_level1_pagination_edge_cases(client):
    user = register_user(client)
    board = create_board(client)

    empty_posts = client.get("/posts", params={"page": 1, "size": 10})
    assert empty_posts.status_code == 200
    assert empty_posts.json()["total"] == 0
    assert empty_posts.json()["total_pages"] == 0

    for i in range(3):
        create_post(client, board_id=board["id"], author_id=user["id"], title=f"title-{i}", content=f"content-{i}")

    page2 = client.get("/posts", params={"page": 2, "size": 2})
    assert page2.status_code == 200
    page2_data = page2.json()
    assert page2_data["total"] == 3
    assert page2_data["total_pages"] == 2
    assert len(page2_data["items"]) == 1

    invalid_page = client.get("/posts", params={"page": 0, "size": 10})
    assert invalid_page.status_code == 422


def test_posts_sorted_by_latest_activity_not_publish_time(client):
    user = register_user(client)
    board = create_board(client)

    old_post = create_post(client, board_id=board["id"], author_id=user["id"], title="old", content="old-content")
    new_post = create_post(client, board_id=board["id"], author_id=user["id"], title="new", content="new-content")

    # Reply on old_post makes its activity time newer than new_post.
    reply = client.post(
        f"/posts/{old_post['id']}/replies",
        json={"author_id": user["id"], "content": "bump old post"},
    )
    assert reply.status_code == 201

    posts = client.get("/posts", params={"page": 1, "size": 10})
    assert posts.status_code == 200
    ids = [item["id"] for item in posts.json()["items"]]
    assert ids[:2] == [old_post["id"], new_post["id"]]
