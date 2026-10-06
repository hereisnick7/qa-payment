"""
HighHelp webhook adapter — mirrors the backend's HighHelp signature utils
(the verify function your integration MR adds).

Signature: RSA SHA256 PKCS1v15 over
    base64url(";".join(sorted(normalize(body)))) + str(timestamp)
sent as headers x-access-signature (base64url) + x-access-timestamp.

Expected backend config (YAML, section `highhelp`): `project_id`,
`private_key_pem`, `public_key_b64url`, and `callback_public_key_b64url` —
the key the backend verifies incoming hooks with (HighHelp's).
Synthetic hooks only pass while a dev has swapped that value on the DEV stand to
our `public_key_b64url`; `verify()` checks against exactly that key. Keys are read
from the MR branch at runtime and never written to disk.
"""

from __future__ import annotations

import base64

NAME = "highhelp"
REPO_ENV = "PAYHOOK_HIGHHELP_REPO"          # backend repo slug / GitLab project id
CONFIG_PATH_ENV = "PAYHOOK_HIGHHELP_CONFIG"  # path of the YAML config inside that repo
DEFAULT_CONFIG_PATH = "config/default.yaml"
ENDPOINTS = {
    "deposit": "/api/webhook/highhelp/deposit",
    "withdrawal": "/api/webhook/highhelp/withdrawal",
}


def normalize(obj, prefix: str = "") -> list:
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += normalize(v, f"{prefix}:{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += normalize(v, f"{prefix}:{i}")
    else:
        if isinstance(obj, bool):
            leaf = "1" if obj else "0"
        elif obj is None:
            leaf = "None"
        else:
            leaf = str(obj)
        out.append(f"{prefix}:{leaf}" if prefix else leaf)
    return out


def _message(body: dict, ts: int) -> bytes:
    norm = ";".join(sorted(normalize(body)))
    return (base64.urlsafe_b64encode(norm.encode()).decode() + str(ts)).encode()


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def load_config(ref: str) -> dict:
    import yaml
    from modules.gitlab.client import GitLabClient
    from modules.vcs.resolve import resolve_repo

    from shared.config_loader import load_module_env

    env = load_module_env("payhook")
    repo_token = env.get(REPO_ENV)
    if not repo_token:
        raise RuntimeError(f"Set {REPO_ENV} (backend repo slug or GitLab project id) in config/payhook/.env")
    _, _, repo = resolve_repo(repo_token)
    raw = GitLabClient().get_file(repo.require_project_id(), env.get(CONFIG_PATH_ENV) or DEFAULT_CONFIG_PATH, ref)
    return yaml.safe_load(raw)["highhelp"]


def build_body(kind: str, cfg: dict, *, status: str, request_id: str, payment_id: str,
               amount: int, initial_amount: int | None = None, currency: str = "UZS") -> dict:
    body = {
        "project_id": cfg["project_id"],
        "general": {"request_id": request_id, "payment_id": payment_id},
        "status": {"status": status},
        "payment_info": {"amount": int(amount), "currency": currency},
    }
    if kind == "deposit":
        body["payment_info"]["initial_amount"] = int(initial_amount if initial_amount is not None else amount)
    return body


def sign(cfg: dict, body: dict, ts: int) -> dict:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    key = serialization.load_pem_private_key(cfg["private_key_pem"].encode(), password=None)
    sig = key.sign(_message(body, ts), padding.PKCS1v15(), hashes.SHA256())
    return {
        "x-access-signature": base64.urlsafe_b64encode(sig).decode(),
        "x-access-timestamp": str(ts),
    }


def verify(cfg: dict, body: dict, headers: dict) -> bool:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    pub = serialization.load_pem_public_key(_b64url_decode(cfg["public_key_b64url"]))
    try:
        pub.verify(_b64url_decode(headers["x-access-signature"]),
                   _message(body, int(headers["x-access-timestamp"])),
                   padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False
