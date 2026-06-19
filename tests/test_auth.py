from .helpers import login_user, register_user


def test_auth_register_login_and_me(client):
    """验证注册-登录-鉴权主链路；关键点：重复注册冲突、带 token 可访问 /auth/me、缺少 token 返回 401。"""
    user = register_user(client)

    duplicate = client.post(
        "/auth/register",
        json={"username": "user001", "password": "pass001", "nickname": "n2", "bio": ""},
    )
    assert duplicate.status_code == 409

    auth = login_user(client)
    token = auth["token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["id"] == user["id"]

    no_token = client.get("/auth/me")
    assert no_token.status_code == 401


def test_level1_auth_and_validation_errors(client):
    """验证认证与参数校验错误分支；关键点：短用户名 422、错误登录 401、错误/无效授权头 401。"""
    short_name = client.post(
        "/auth/register",
        json={"username": "u1", "password": "pass001", "nickname": "nick", "bio": ""},
    )
    assert short_name.status_code == 422

    wrong_login = client.post("/auth/login", json={"username": "nobody", "password": "wrong"})
    assert wrong_login.status_code == 401

    bad_header = client.get("/auth/me", headers={"Authorization": "Token abc"})
    assert bad_header.status_code == 401

    bad_token = client.get("/auth/me", headers={"Authorization": "Bearer invalid-token"})
    assert bad_token.status_code == 401


def test_token_refresh(client):
    """验证 token 刷新流程：刷新后旧 token 失效，新 token 可用。"""
    register_user(client)
    auth = login_user(client)
    old_token = auth["token"]

    # Use old token to refresh
    resp = client.post("/auth/refresh", json={"token": old_token})
    assert resp.status_code == 200
    data = resp.json()
    new_token = data["token"]
    assert isinstance(new_token, str)
    assert len(new_token) > 0
    assert new_token != old_token
    assert data["user"]["username"] == "user001"

    # New token works
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me.status_code == 200

    # Old token no longer works (it was revoked)
    old_me = client.get("/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert old_me.status_code == 401


def test_token_refresh_invalid(client):
    """验证无效 token 刷新返回 401。"""
    resp = client.post("/auth/refresh", json={"token": "nonexistent-token"})
    assert resp.status_code == 401
