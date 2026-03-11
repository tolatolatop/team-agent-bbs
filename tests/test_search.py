from .helpers import auth_headers, create_board, create_post, login_user, register_user


def test_search_hits_post_title_only(client):
    """验证仅标题命中搜索；关键点：结果只出现在 posts，且名称补全字段完整。"""
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
    assert data["posts"][0]["board_name"] == "tech"
    assert data["posts"][0]["author_username"] == "user001"
    assert data["posts"][0]["author_nickname"] == "nick"
    assert len(data["replies"]) == 0


def test_search_hits_reply_content_only(client):
    """验证仅回复内容命中搜索；关键点：结果只出现在 replies，且包含 post_title 与作者名称字段。"""
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
    assert data["replies"][0]["post_title"] == post["title"]
    assert data["replies"][0]["author_username"] == "user001"
    assert data["replies"][0]["author_nickname"] == "nick"


def test_search_hits_posts_and_replies(client):
    """验证标题与回复同时命中；关键点：posts/replies 两个结果集均返回数据。"""
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
    """验证无命中场景；关键点：接口正常返回 200，posts/replies 均为空数组。"""
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token, name="tech")
    create_post(client, token=token, board_id=board["id"], title="hello", content="world")

    response = client.get("/search", params={"keyword": "no-match-keyword"})
    assert response.status_code == 200
    data = response.json()
    assert data["posts"] == []
    assert data["replies"] == []
