import asyncio
import os
import urllib.request

from . import services


def _is_enabled() -> bool:
    return os.getenv("NOTIFY_TASK_ENABLED", "true").lower() in {"1", "true", "yes", "on"}


def is_notification_task_enabled() -> bool:
    return _is_enabled()


def _interval_seconds() -> int:
    raw = os.getenv("NOTIFY_TASK_INTERVAL_SECONDS", "30")
    try:
        value = int(raw)
        return value if value > 0 else 30
    except ValueError:
        return 30


def _request_timeout_seconds() -> float:
    raw = os.getenv("NOTIFY_TASK_REQUEST_TIMEOUT_SECONDS", "2")
    try:
        value = float(raw)
        return value if value > 0 else 2.0
    except ValueError:
        return 2.0


async def _notify_user(username: str) -> None:
    url = f"http://{username}:8000/notify"

    def _send() -> None:
        request = urllib.request.Request(url=url, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=_request_timeout_seconds()):
                pass
        except Exception:
            # Best-effort notify, ignore request failures by requirement.
            return

    await asyncio.to_thread(_send)


async def run_notification_dispatch_once() -> None:
    usernames = services.list_usernames_with_unread_notifications()
    if not usernames:
        return
    await asyncio.gather(*[_notify_user(username) for username in usernames], return_exceptions=True)


async def notification_dispatch_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await run_notification_dispatch_once()
        except Exception:
            # Keep scheduler alive even if one round fails.
            pass

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_interval_seconds())
        except asyncio.TimeoutError:
            continue
