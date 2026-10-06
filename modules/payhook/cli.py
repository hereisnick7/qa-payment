"""
pay-hook CLI — signed synthetic payment-provider webhooks for DEV-stand testing.
Called from cli/agent.py dispatcher; run_command() returns True if handled.

The command only PRINTS a ready curl (plus a local signature self-check on
stderr). It never sends anything itself: sending is the operator's explicit,
previewed step (qa-payment-agent flow). It also refuses any host outside the
DEV allow-list, so a synthetic hook can never be aimed at production.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

_WORKFLOW_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_WORKFLOW_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKFLOW_ROOT))

KINDS = ("deposit", "withdrawal")

USAGE = (
    "  Использование: pay-hook <provider> deposit|withdrawal --status=<s> --request-id=<id> "
    "--payment-id=<id> --amount=<minor> [--initial=<minor>] [--currency=UZS] [--ref=<branch|sha>] "
    "[--host=<url>] [--ts=<unix>] [--bad-sig]"
)


def _settings() -> dict:
    from shared.config_loader import load_module_env
    env = load_module_env("payhook")
    allowed = env.get("PAYHOOK_ALLOWED_HOSTS") or ""
    if not allowed.strip():
        raise RuntimeError("PAYHOOK_ALLOWED_HOSTS is empty — set your non-prod stand host(s) "
                           "in config/payhook/.env (see config/example/payhook/.env.example).")
    return {
        "host": env.get("PAYHOOK_HOST") or "",
        "allowed": {h.strip().lower() for h in allowed.split(",") if h.strip()},
    }


def check_host(host: str, allowed: set) -> str:
    netloc = urlparse(host).netloc.lower() or host.lower()
    if netloc not in allowed:
        raise ValueError(f"Host '{netloc}' is not in the DEV allow-list ({', '.join(sorted(allowed))}). "
                         f"pay-hook never targets production; extend PAYHOOK_ALLOWED_HOSTS only for a non-prod stand.")
    return host.rstrip("/")


def corrupt_signature(sig: str) -> str:
    tail = "BBBBBB" if sig.endswith("AAAAAA") else "AAAAAA"
    return sig[:-6] + tail


def build_curl(url: str, headers: dict, body: dict) -> str:
    data = json.dumps(body, separators=(",", ":"))
    lines = [f"curl -sS -i -X POST '{url}'", "  -H 'Content-Type: application/json'"]
    lines += [f"  -H '{k}: {v}'" for k, v in headers.items()]
    lines.append(f"  --data '{data}'")
    return " \\\n".join(lines)


def make_hook(adapter, cfg: dict, kind: str, fields: dict, host: str, ts: int, bad_sig: bool = False):
    body = adapter.build_body(kind, cfg, **fields)
    headers = adapter.sign(cfg, body, ts)
    ok = adapter.verify(cfg, body, headers)
    if bad_sig:
        headers["x-access-signature"] = corrupt_signature(headers["x-access-signature"])
    return build_curl(f"{host}{adapter.ENDPOINTS[kind]}", headers, body), ok


def _parse(parts: list):
    flags, positional, switches = {}, [], set()
    for p in parts:
        if p.startswith("--") and "=" in p:
            k, v = p[2:].split("=", 1)
            flags[k] = v
        elif p.startswith("--"):
            switches.add(p[2:])
        else:
            positional.append(p)
    return flags, positional, switches


def cmd_pay_hook(parts: list):
    from modules.payhook.adapters import get_adapter

    flags, positional, switches = _parse(parts[1:])
    required = ("status", "request-id", "payment-id", "amount")
    if len(positional) < 2 or positional[1] not in KINDS or any(r not in flags for r in required):
        print(USAGE)
        return
    adapter = get_adapter(positional[0])
    kind = positional[1]
    settings = _settings()
    host = flags.get("host", settings["host"])
    if not host:
        raise RuntimeError("No stand host: pass --host=<url> or set PAYHOOK_HOST.")
    host = check_host(host, settings["allowed"])
    cfg = adapter.load_config(flags.get("ref", "master"))
    fields = {
        "status": flags["status"],
        "request_id": flags["request-id"],
        "payment_id": flags["payment-id"],
        "amount": int(flags["amount"]),
        "initial_amount": int(flags["initial"]) if "initial" in flags else None,
        "currency": flags.get("currency", "UZS"),
    }
    ts = int(flags.get("ts", time.time()))
    curl, ok = make_hook(adapter, cfg, kind, fields, host, ts, bad_sig="bad-sig" in switches)
    note = " (signature then deliberately corrupted: --bad-sig)" if "bad-sig" in switches else ""
    print(f"# local verify vs our public key: {'OK' if ok else 'FAIL'}{note}", file=sys.stderr)
    print(curl)


def cmd_pay_hook_providers():
    from modules.payhook.adapters import PROVIDERS, get_adapter
    for name in PROVIDERS:
        a = get_adapter(name)
        eps = ", ".join(f"{k}={v}" for k, v in a.ENDPOINTS.items())
        print(f"  {name:<12} repo env={a.REPO_ENV}  {eps}")


PAYHOOK_COMMANDS = {"pay-hook", "pay-hook-providers"}


def run_command(cmd: str, parts: list) -> bool:
    if cmd not in PAYHOOK_COMMANDS:
        return False
    try:
        if cmd == "pay-hook":
            cmd_pay_hook(parts)
        else:
            cmd_pay_hook_providers()
    except Exception as e:
        print(f"  Ошибка: {e}\n")
    return True
