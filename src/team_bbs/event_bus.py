import asyncio
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from .models import Webhook, now_utc
from .schemas import StructuredEvent

logger = logging.getLogger(__name__)

# Configuration
WEBHOOK_DISPATCH_TIMEOUT = float(os.getenv("WEBHOOK_DISPATCH_TIMEOUT", "5"))
WEBHOOK_RETRY_MAX = int(os.getenv("WEBHOOK_RETRY_MAX", "3"))
WEBHOOK_RETRY_BACKOFF = float(os.getenv("WEBHOOK_RETRY_BACKOFF", "1.0"))
# Maximum event_id age in seconds for idempotency dedup
EVENT_IDEMPOTENCY_WINDOW = int(os.getenv("EVENT_IDEMPOTENCY_WINDOW", "3600"))


def _build_action_url(event: StructuredEvent, base_url: str = "") -> str:
    """Build a human-readable action URL for the event."""
    if event.action_url:
        return event.action_url
    if event.post_id:
        return f"{base_url}/posts/{event.post_id}"
    if event.board_id:
        return f"{base_url}/boards/{event.board_id}"
    return ""


def _sign_payload(payload: bytes, secret: str) -> str:
    """HMAC-SHA256 sign a payload with the webhook secret."""
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _event_matches_webhook(event_type: str, webhook_events: list[str]) -> bool:
    """Check if an event type matches a webhook's subscribed events."""
    if "*" in webhook_events:
        return True
    return event_type in webhook_events


async def _dispatch_single(
    webhook: Webhook,
    event: StructuredEvent,
    session: httpx.AsyncClient,
) -> bool:
    """Dispatch a single event to one webhook with HMAC signature. Returns True on success."""
    payload_dict = event.model_dump()
    payload_bytes = json.dumps(payload_dict, ensure_ascii=False).encode("utf-8")
    signature = _sign_payload(payload_bytes, webhook.secret)

    last_error: Exception | None = None
    for attempt in range(WEBHOOK_RETRY_MAX):
        try:
            resp = await session.post(
                webhook.url,
                content=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": signature,
                    "X-Event-ID": event.event_id,
                    "X-Event-Type": event.event_type.value,
                    "User-Agent": "TeamBBS-EventBus/1.0",
                },
                timeout=WEBHOOK_DISPATCH_TIMEOUT,
            )
            if resp.is_success:
                return True
            # Non-retryable client errors
            if 400 <= resp.status_code < 500 and resp.status_code not in (408, 429):
                logger.warning(
                    "Webhook %s returned %d, not retrying", webhook.url[:60], resp.status_code
                )
                return False
            last_error = Exception(f"HTTP {resp.status_code}")
        except Exception as exc:
            last_error = exc
            logger.debug("Webhook dispatch attempt %d failed: %s", attempt + 1, exc)

        if attempt < WEBHOOK_RETRY_MAX - 1:
            await asyncio.sleep(WEBHOOK_RETRY_BACKOFF * (2**attempt))

    logger.error(
        "Webhook %s failed after %d attempts: %s",
        webhook.url[:60],
        WEBHOOK_RETRY_MAX,
        last_error,
    )
    return False


def _build_snippet(post_id: int | None, reply_id: int | None) -> str:
    """Extract a short text snippet for the event."""
    import json as _json

    from .db import SessionLocal
    from .models import Post, Reply
    from sqlalchemy import select

    if reply_id is not None:
        with SessionLocal() as db:
            reply = db.execute(select(Reply).where(Reply.id == reply_id)).scalar_one_or_none()
            if reply:
                return reply.content[:200]
    if post_id is not None:
        with SessionLocal() as db:
            post = db.execute(select(Post).where(Post.id == post_id)).scalar_one_or_none()
            if post:
                return post.content[:200]
    return ""


async def produce_event(event: StructuredEvent) -> list[dict[str, Any]]:
    """Produce a structured event: find matching webhooks and dispatch to each.

    Returns a list of dispatch results, one per matched webhook.
    Backward compatible -- does not alter the existing notification flow.
    """
    # Auto-fill snippet if empty
    if not event.snippet:
        event.snippet = _build_snippet(event.post_id, event.reply_id)

    # Auto-fill action_url if empty
    if not event.action_url:
        event.action_url = _build_action_url(event)

    # Find all active webhooks that match this event type
    # Lazy import to avoid circular dependency with services.py
    from . import services
    webhooks = services.list_active_webhooks_for_event(event.event_type.value)

    if not webhooks:
        return []

    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as session:
        tasks = []
        for wh in webhooks:
            tasks.append(_dispatch_single(wh, event, session))
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    for wh, outcome in zip(webhooks, outcomes):
        results.append({
            "webhook_id": wh.id,
            "url": wh.url,
            "success": outcome is True,
            "error": str(outcome) if outcome is not True and outcome is not False else None,
        })

    return results


def produce_event_sync(event: StructuredEvent) -> list[dict[str, Any]]:
    """Synchronous wrapper for produce_event. Used from sync FastAPI endpoints."""
    return asyncio.run(produce_event(event))
