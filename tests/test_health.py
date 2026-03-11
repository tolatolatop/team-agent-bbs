def test_health(client):
    """验证健康检查接口可用；关键点：返回 200 且 status 为 ok。"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
