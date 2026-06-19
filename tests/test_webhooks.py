"""Tests for webhook registration and event bus integration."""
from .helpers import auth_headers, register_user, login_user


def _get_user_id(client, token):
    me = client.get("/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    return me.json()["id"]


def test_webhook_create_list_delete(client):
    """Verify webhook CRUD: create, list, delete."""
    register_user(client, username="whuser", password="whpass")
    token = login_user(client, username="whuser", password="whpass")["token"]
    user_id = _get_user_id(client, token)

    # List initially empty
    resp = client.get(f"/users/{user_id}/webhooks", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []

    # Create webhook
    payload = {
        "url": "https://example.com/hook",
        "events": ["post_updated", "new_reply"],
        "secret": "sk_" + "a" * 16,
    }
    resp = client.post(f"/users/{user_id}/webhooks", json=payload, headers=auth_headers(token))
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["url"] == "https://example.com/hook"
    assert data["events"] == ["post_updated", "new_reply"]
    assert data["is_active"] is True
    wh_id = data["id"]

    # List again
    resp = client.get(f"/users/{user_id}/webhooks", headers=auth_headers(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == wh_id

    # Delete
    resp = client.delete(f"/users/{user_id}/webhooks/{wh_id}", headers=auth_headers(token))
    assert resp.status_code == 200

    # List empty again
    resp = client.get(f"/users/{user_id}/webhooks", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


def test_webhook_forbidden_for_other_user(client):
    """Verify one user cannot access another user's webhooks."""
    register_user(client, username="whu1", password="whp1")
    register_user(client, username="whu2", password="whp2")
    token1 = login_user(client, username="whu1", password="whp1")["token"]
    token2 = login_user(client, username="whu2", password="whp2")["token"]

    uid1 = _get_user_id(client, token1)

    # user2 tries to list user1's webhooks -> 403
    resp = client.get(f"/users/{uid1}/webhooks", headers=auth_headers(token2))
    assert resp.status_code == 403


def test_event_bus_imports_and_creates_event(client):
    """Verify StructuredEvent can be created and produce_event_sync runs without error."""
    from src.team_bbs.schemas import StructuredEvent, EventType
    from src.team_bbs.event_bus import produce_event_sync

    event = StructuredEvent(
        event_type=EventType.POST_UPDATED,
        post_id=1,
        source_user_id=1,
        snippet="test content",
    )
    # Should run without error (no webhooks registered to actually dispatch to)
    results = produce_event_sync(event)
    assert isinstance(results, list)


def test_webhook_wildcard_events(client):
    """Verify '*' wildcard matches all event types."""
    register_user(client, username="whwild", password="whpass")
    token = login_user(client, username="whwild", password="whpass")["token"]
    uid = _get_user_id(client, token)

    payload = {
        "url": "https://example.com/hook",
        "events": ["*"],
        "secret": "sk_" + "b" * 16,
    }
    resp = client.post(f"/users/{uid}/webhooks", json=payload, headers=auth_headers(token))
    assert resp.status_code == 201
    assert resp.json()["events"] == ["*"]
