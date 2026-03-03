def register_user(client, username: str = "user001", password: str = "pass001"):
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "password": password,
            "nickname": "nick",
            "bio": "bio",
        },
    )
    assert response.status_code == 201
    return response.json()


def login_user(client, username: str = "user001", password: str = "pass001"):
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_board(client, token: str, name: str = "general"):
    response = client.post("/boards", json={"name": name, "description": "desc"}, headers=auth_headers(token))
    assert response.status_code == 201
    return response.json()


def create_post(client, token: str, board_id: int, title: str = "hello", content: str = "fastapi forum"):
    response = client.post(
        "/posts",
        json={
            "board_id": board_id,
            "title": title,
            "content": content,
            "tags": ["intro"],
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()
