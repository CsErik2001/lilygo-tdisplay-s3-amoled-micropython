#!/usr/bin/env python3
"""Provision the LilyGo Codex monitor with ChatGPT OAuth tokens (one-time USB step).

The ESP refreshes its own access token afterwards, so no Mac server is
needed at runtime. Only Wi-Fi is entered on the touch keyboard.

Usage::

    python3 tools/push_codex_auth.py --port /dev/cu.usbmodem101
    python3 tools/push_codex_auth.py --port /dev/cu.usbmodem101 --check
    python3 tools/push_codex_auth.py --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

CODEX_AUTH = os.path.expanduser("~/.codex/auth.json")
DEVICE_PATH = ":codex_auth.json"


def load_mac_auth(path):
    with open(path, "r") as handle:
        data = json.load(handle)
    if data.get("auth_mode") != "chatgpt":
        raise SystemExit("auth_mode is not 'chatgpt' in " + path)
    tokens = data.get("tokens") or {}
    refresh = tokens.get("refresh_token") or ""
    if not refresh:
        raise SystemExit("no refresh_token in " + path)
    return {
        "refresh_token": refresh,
        "access_token": tokens.get("access_token") or "",
        "id_token": tokens.get("id_token") or "",
        "account_id": tokens.get("account_id") or "",
    }


def run_mpremote(port, *args):
    cmd = ["mpremote", "connect", port] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit("mpremote failed: " + (proc.stderr or proc.stdout).strip())
    return proc.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/cu.usbmodem101")
    parser.add_argument("--auth", default=CODEX_AUTH)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        out = run_mpremote(args.port, "exec",
                           "import json;print(json.load(open('/codex_auth.json')).keys())")
        print("device /codex_auth.json:", out)
        return

    payload = load_mac_auth(args.auth)
    print("refresh_token len:", len(payload["refresh_token"]))
    print("access_token len:", len(payload["access_token"]))
    if args.dry_run:
        print("dry-run: not copying")
        return

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        json.dump(payload, tmp)
        tmp_path = tmp.name
    try:
        run_mpremote(args.port, "cp", tmp_path, DEVICE_PATH)
    finally:
        os.unlink(tmp_path)
    print("copied to", args.port, DEVICE_PATH)
    print("next: copy app files, then reset:")
    print("  mpremote connect {} cp examples/codex/codex_usage.py :codex_usage.py".format(args.port))
    print("  mpremote connect {} cp examples/codex/connect_wifi.py :connect_wifi.py".format(args.port))
    print("  mpremote connect {} cp examples/codex/main.py :main.py".format(args.port))
    print("  mpremote connect {} reset".format(args.port))


if __name__ == "__main__":
    sys.exit(main())
