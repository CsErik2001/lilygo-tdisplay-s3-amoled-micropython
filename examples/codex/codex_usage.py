"""Codex usage client for MicroPython (ESP32-S3).

Everything runs on the device after a one-time USB provisioning step:

1. On the Mac: ``python3 tools/push_codex_auth.py`` copies the ChatGPT
   ``refresh_token`` from ``~/.codex/auth.json`` to ``/codex_auth.json``.
   The refresh token is ~211 chars; the access token is ~1844 chars, so
   neither is typed on the touch keyboard.
2. On the ESP: this module refreshes the access token itself via
   ``https://auth.openai.com/oauth/token`` and polls
   ``https://chatgpt.com/backend-api/wham/usage`` for the primary
   (5-hour) and secondary (weekly) windows.

No Mac bridge/server is needed at runtime; only Wi-Fi (entered on the
touch keyboard) is required.
"""

import json
import time

try:
    import urequests as _requests
except ImportError:  # pragma: no cover - host sanity check
    _requests = None

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
TOKEN_URL = "https://auth.openai.com/oauth/token"
USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
AUTH_PATH = "/codex_auth.json"


class UsageError(Exception):
    pass


def load_auth(path=AUTH_PATH):
    try:
        with open(path, "r") as handle:
            data = json.load(handle)
    except OSError:
        return None
    except ValueError:
        return None
    if not isinstance(data, dict) or not data.get("refresh_token"):
        return None
    return data


def save_auth(auth, path=AUTH_PATH):
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        handle.write(json.dumps(auth))
    try:
        import os

        try:
            os.remove(path)
        except OSError:
            pass
        os.rename(tmp, path)
    except OSError:
        # FAT/LittleFS fallback: tmp file is still usable on next boot
        # if rename is unavailable.
        pass
    return True


def _close(response):
    try:
        response.close()
    except Exception:
        pass


def _post_form(url, fields):
    body = "&".join(
        key + "=" + value for key, value in fields.items()
    )
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    try:
        return _requests.post(url, data=body, headers=headers)
    except TypeError:
        # Older urequests without timeout/kwarg tolerance.
        return _requests.post(url, data=body, headers=headers)


def _get(url, access_token):
    headers = {
        "Authorization": "Bearer " + access_token,
        "Accept": "application/json",
    }
    try:
        return _requests.get(url, headers=headers)
    except TypeError:
        return _requests.get(url, headers=headers)


def refresh_access(auth, path=AUTH_PATH):
    """Exchange the stored refresh_token for a new access token."""
    if _requests is None:
        raise UsageError("urequests missing")
    refresh_token = (auth or {}).get("refresh_token") or ""
    if not refresh_token:
        raise UsageError("no refresh_token")
    response = _post_form(
        TOKEN_URL,
        {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": refresh_token,
        },
    )
    try:
        status = getattr(response, "status_code", 200)
        text = response.text
    finally:
        pass
    try:
        data = json.loads(text)
    except ValueError:
        _close(response)
        raise UsageError("refresh HTTP " + str(status))
    _close(response)
    if status != 200:
        detail = ""
        if isinstance(data, dict):
            detail = str(data.get("error_description") or data.get("error") or "")[:60]
        raise UsageError("refresh HTTP " + str(status) + " " + detail)
    access = data.get("access_token") if isinstance(data, dict) else None
    if not access:
        raise UsageError("refresh: no access_token")
    auth["access_token"] = access
    # OpenAI rotates the refresh token; persist whatever comes back.
    if data.get("refresh_token"):
        auth["refresh_token"] = data["refresh_token"]
    if data.get("id_token"):
        auth["id_token"] = data["id_token"]
    auth["last_refresh"] = _now_tuple()
    save_auth(auth, path)
    return access


def _now_tuple():
    now = time.localtime()
    return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(
        now[0], now[1], now[2], now[3], now[4], now[5]
    )


def fetch_usage_once(access_token):
    if _requests is None:
        raise UsageError("urequests missing")
    if not access_token:
        raise UsageError("no access_token")
    response = _get(USAGE_URL, access_token)
    try:
        status = getattr(response, "status_code", 200)
        text = response.text
    finally:
        pass
    if status == 401:
        _close(response)
        raise UsageError("HTTP 401")
    if status == 429:
        _close(response)
        raise UsageError("HTTP 429 rate limited")
    if status != 200:
        _close(response)
        raise UsageError("usage HTTP " + str(status))
    try:
        data = json.loads(text)
    except ValueError:
        _close(response)
        raise UsageError("bad usage JSON")
    _close(response)
    return data


def get_usage(auth, path=AUTH_PATH):
    """Return the /wham/usage payload, refreshing once on 401."""
    access = (auth or {}).get("access_token")
    if not access:
        access = refresh_access(auth, path)
    try:
        return fetch_usage_once(access)
    except UsageError as error:
        if str(error) != "HTTP 401":
            raise
    access = refresh_access(auth, path)
    return fetch_usage_once(access)


def format_duration(seconds):
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days > 0:
        return "{}d {}h".format(days, hours)
    if hours > 0:
        return "{}h {:02d}m".format(hours, minutes)
    return "{}m".format(minutes)


def summarize(payload):
    """Flatten /wham/usage into display-ready numbers."""
    rate = (payload or {}).get("rate_limit") or {}
    primary = rate.get("primary_window") or {}
    secondary = rate.get("secondary_window") or {}

    def window(node):
        used = float(node.get("used_percent", 0) or 0)
        used = max(0.0, min(100.0, used))
        reset_after = int(node.get("reset_after_seconds", 0) or 0)
        return used, 100.0 - used, reset_after

    p_used, p_left, p_reset = window(primary)
    s_used, s_left, s_reset = window(secondary)
    return {
        "plan": str(payload.get("plan_type") or "?"),
        "limited": bool(rate.get("limit_reached", False)),
        "primary_used": p_used,
        "primary_left": p_left,
        "primary_reset_after": p_reset,
        "primary_reset_in": format_duration(p_reset),
        "secondary_used": s_used,
        "secondary_left": s_left,
        "secondary_reset_after": s_reset,
        "secondary_reset_in": format_duration(s_reset),
    }
