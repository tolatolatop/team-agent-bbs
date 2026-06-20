from .helpers import auth_headers, create_board, create_post, login_user, register_user


def test_create_post_with_multimedia(client):
    """验证发帖时附带多媒体数据正确存储并返回。"""
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)

    multimedia = [
        {"type": "image", "url": "https://example.com/photo.png", "description": "截图"},
        {"type": "video", "url": "https://example.com/demo.mp4", "description": "演示视频"},
    ]

    resp = client.post(
        "/posts",
        json={
            "board_id": board["id"],
            "title": "带多媒体的帖子",
            "content": "这是正文",
            "tags": ["test"],
            "multimedia": multimedia,
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["multimedia"] == multimedia
    assert data["content"] == "这是正文"


def test_multimedia_defaults_to_empty_list(client):
    """验证不传 multimedia 时默认为空列表。"""
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)

    resp = client.post(
        "/posts",
        json={
            "board_id": board["id"],
            "title": "无多媒体",
            "content": "纯文本",
            "tags": [],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["multimedia"] == []


def test_display_mode_plaintext_collapses_multimedia(client):
    """验证 display_mode=plaintext 时多媒体被折叠为文本占位符。"""
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)

    multimedia = [
        {"type": "image", "url": "https://example.com/img.png", "description": "截图A"},
        {"type": "video", "url": "https://example.com/vid.mp4", "description": "视频B"},
    ]

    created = client.post(
        "/posts",
        json={
            "board_id": board["id"],
            "title": "测试帖子",
            "content": "正文内容",
            "tags": [],
            "multimedia": multimedia,
        },
        headers=auth_headers(token),
    ).json()

    # plaintext mode
    resp = client.get(f"/posts/{created['id']}/plaintext")
    assert resp.status_code == 200
    data = resp.json()

    # multimedia should be empty in plaintext mode
    assert data["multimedia"] == []

    # content should include textual placeholders appended
    assert "[图片: 截图A]" in data["content"]
    assert "[视频: 视频B]" in data["content"]
    assert "(https://example.com/img.png)" in data["content"]
    assert "(https://example.com/vid.mp4)" in data["content"]

    # multimedia mode (default)
    resp2 = client.get(f"/posts/{created['id']}")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["multimedia"] == multimedia
    assert data2["content"] == "正文内容"


def test_display_mode_plaintext_on_list(client):
    """验证帖子列表中 display_mode=plaintext 同样生效。"""
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)

    multimedia = [{"type": "image", "url": "https://example.com/pic.jpg", "description": "图"}]

    client.post(
        "/posts",
        json={
            "board_id": board["id"],
            "title": "多媒体帖子",
            "content": "正文",
            "tags": [],
            "multimedia": multimedia,
        },
        headers=auth_headers(token),
    )

    # plaintext list
    resp = client.get("/posts/plaintext", params={"page": 1, "size": 10})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert item["multimedia"] == []

    # multimedia list (default)
    resp2 = client.get("/posts", params={"page": 1, "size": 10})
    assert resp2.status_code == 200
    items2 = resp2.json()["items"]
    for item in items2:
        # items with empty multimedia will be [] in both modes
        pass


def test_update_post_multimedia(client):
    """验证更新帖子时可以修改 multimedia。"""
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)

    created = client.post(
        "/posts",
        json={
            "board_id": board["id"],
            "title": "原帖",
            "content": "原内容",
            "tags": [],
        },
        headers=auth_headers(token),
    ).json()

    new_multimedia = [
        {"type": "image", "url": "https://example.com/new.png", "description": "新图"},
    ]
    resp = client.put(
        f"/posts/{created['id']}",
        json={"multimedia": new_multimedia},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["multimedia"] == new_multimedia

    # Verify via GET
    get_resp = client.get(f"/posts/{created['id']}")
    assert get_resp.json()["multimedia"] == new_multimedia


def test_display_mode_on_replies_view(client):
    """验证回复列表接口中也支持 display_mode。"""
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)

    multimedia = [{"type": "image", "url": "https://example.com/pic.jpg", "description": "附圖"}]

    created = client.post(
        "/posts",
        json={
            "board_id": board["id"],
            "title": "含多媒体",
            "content": "正文",
            "tags": [],
            "multimedia": multimedia,
        },
        headers=auth_headers(token),
    ).json()

    # Add a reply
    client.post(
        f"/posts/{created['id']}/replies",
        json={"content": "回复"},
        headers=auth_headers(token),
    )

    # plaintext mode on replies view
    resp = client.get(
        f"/posts/{created['id']}/replies/plaintext",
        params={"page": 1, "size": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["post"]["multimedia"] == []
    assert "[图片: 附圖]" in data["post"]["content"]


def test_multimedia_validation_image_video_only(client):
    """验证 multimedia item type 只允许 image 和 video。"""
    register_user(client)
    token = login_user(client)["token"]
    board = create_board(client, token=token)

    resp = client.post(
        "/posts",
        json={
            "board_id": board["id"],
            "title": "非法类型",
            "content": "test",
            "tags": [],
            "multimedia": [{"type": "audio", "url": "https://example.com/sound.mp3", "description": "声音"}],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 422
