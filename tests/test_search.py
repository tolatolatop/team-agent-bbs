from .helpers import auth_headers, create_board, create_post, login_user, register_user


def test_search_hits_post_title_only(client):
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token, name="tech")
    create_post(client, token=token, board_id=board["id"], title="FastAPI Title", content="plain content")

    response = client.get("/search", params={"keyword": "fastapi"})
    assert response.status_code == 200
    data = response.json()
    assert data["keyword"] == "fastapi"
    assert len(data["posts"]) == 1
    assert data["posts"][0]["title"] == "FastAPI Title"
    assert len(data["replies"]) == 0


def test_search_hits_reply_content_only(client):
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token, name="tech")
    post = create_post(client, token=token, board_id=board["id"], title="No hit title", content="No hit content")

    reply = client.post(
        f"/posts/{post['id']}/replies",
        json={"content": "This reply includes python keyword"},
        headers=auth_headers(token),
    )
    assert reply.status_code == 201

    response = client.get("/search", params={"keyword": "python"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["posts"]) == 0
    assert len(data["replies"]) == 1
    assert "python" in data["replies"][0]["content"].lower()


def test_search_hits_posts_and_replies(client):
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token, name="tech")
    post = create_post(client, token=token, board_id=board["id"], title="SQLAlchemy Tips", content="ORM usage")

    reply = client.post(
        f"/posts/{post['id']}/replies",
        json={"content": "I like sqlalchemy too"},
        headers=auth_headers(token),
    )
    assert reply.status_code == 201

    response = client.get("/search", params={"keyword": "sqlalchemy"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["posts"]) == 1
    assert len(data["replies"]) == 1


def test_search_no_results(client):
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token, name="tech")
    create_post(client, token=token, board_id=board["id"], title="hello", content="world")

    response = client.get("/search", params={"keyword": "no-match-keyword"})
    assert response.status_code == 200
    data = response.json()
    assert data["posts"] == []
    assert data["replies"] == []
