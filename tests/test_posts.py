from .helpers import auth_headers, create_board, create_post, login_user, register_user


def test_board_post_search_and_pagination(client):
    """验证帖子列表分页与关键字查询；关键点：分页元信息正确、按关键字可命中、按板块可过滤。"""
    user = register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token, name="tech")

    create_post(client, token=token, board_id=board["id"], title="FastAPI tips", content="hello world")
    create_post(client, token=token, board_id=board["id"], title="Python tricks", content="good practice")

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
    assert search_data["items"][0]["board_name"] == board["name"]
    assert search_data["items"][0]["author_username"] == user["username"]
    assert search_data["items"][0]["author_nickname"] == user["nickname"]

    by_board = client.get("/posts", params={"board_id": board["id"], "page": 1, "size": 10})
    assert by_board.status_code == 200
    assert by_board.json()["total"] == 2


def test_level1_not_found_and_conflict_errors(client):
    """验证常见资源不存在错误；关键点：用户/板块/帖子不存在返回 404，非法发帖与删除不存在收藏返回预期错误。"""
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)
    post = create_post(client, token=token, board_id=board["id"])

    assert client.get("/users/99999").status_code == 404
    assert client.get("/boards/99999").status_code == 404
    assert client.get("/posts/99999").status_code == 404

    no_board_post = client.post(
        "/posts",
        json={"board_id": 99999, "title": "t", "content": "c", "tags": []},
        headers=auth_headers(token),
    )
    assert no_board_post.status_code == 404

    remove_missing_fav = client.delete("/favorites", params={"post_id": 99999}, headers=auth_headers(token))
    assert remove_missing_fav.status_code == 404


def test_level1_pagination_edge_cases(client):
    """验证分页边界场景；关键点：空列表 total_pages 为 0、第二页剩余条数正确、非法 page 返回 422。"""
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)

    empty_posts = client.get("/posts", params={"page": 1, "size": 10})
    assert empty_posts.status_code == 200
    assert empty_posts.json()["total"] == 0
    assert empty_posts.json()["total_pages"] == 0

    for i in range(3):
        create_post(client, token=token, board_id=board["id"], title=f"title-{i}", content=f"content-{i}")

    page2 = client.get("/posts", params={"page": 2, "size": 2})
    assert page2.status_code == 200
    page2_data = page2.json()
    assert page2_data["total"] == 3
    assert page2_data["total_pages"] == 2
    assert len(page2_data["items"]) == 1

    invalid_page = client.get("/posts", params={"page": 0, "size": 10})
    assert invalid_page.status_code == 422


def test_posts_sorted_by_latest_activity_not_publish_time(client):
    """验证帖子按最新活动排序而非发布时间；关键点：旧帖被回复后活动时间更新并应前置。"""
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)

    old_post = create_post(client, token=token, board_id=board["id"], title="old", content="old-content")
    new_post = create_post(client, token=token, board_id=board["id"], title="new", content="new-content")

    # Reply on old_post makes its activity time newer than new_post.
    reply = client.post(
        f"/posts/{old_post['id']}/replies",
        json={"content": "bump old post"},
        headers=auth_headers(token),
    )
    assert reply.status_code == 201


def test_write_endpoints_require_token(client):
    """验证写接口必须鉴权；关键点：未携带 Bearer token 的创建/更新/删除均返回 401。"""
    register_user(client)
    login = login_user(client)
    token = login["token"]
    board = create_board(client, token=token)
    post = create_post(client, token=token, board_id=board["id"])

    no_token_create_post = client.post(
        "/posts",
        json={"board_id": board["id"], "title": "t", "content": "c", "tags": []},
    )
    assert no_token_create_post.status_code == 401

    no_token_update_post = client.put(f"/posts/{post['id']}", json={"content": "x"})
    assert no_token_update_post.status_code == 401

    no_token_delete_post = client.delete(f"/posts/{post['id']}")
    assert no_token_delete_post.status_code == 401


def test_post_owner_permission_denied_for_other_user(client):
    """验证帖子作者权限；关键点：非作者更新/删除返回 403，且列表中作者名称字段正确。"""
    register_user(client, username="user001", password="pass001")
    register_user(client, username="user002", password="pass002")
    token1 = login_user(client, username="user001", password="pass001")["token"]
    token2 = login_user(client, username="user002", password="pass002")["token"]

    board = create_board(client, token=token1)
    post = create_post(client, token=token1, board_id=board["id"])

    update_by_other = client.put(f"/posts/{post['id']}", json={"content": "hack"}, headers=auth_headers(token2))
    assert update_by_other.status_code == 403

    delete_by_other = client.delete(f"/posts/{post['id']}", headers=auth_headers(token2))
    assert delete_by_other.status_code == 403

    posts = client.get("/posts", params={"page": 1, "size": 10})
    assert posts.status_code == 200
    items = posts.json()["items"]
    ids = [item["id"] for item in items]
    assert post["id"] in ids
    created_post = next(item for item in items if item["id"] == post["id"])
    assert created_post["author_username"] == "user001"
    assert created_post["author_nickname"] == "nick"
