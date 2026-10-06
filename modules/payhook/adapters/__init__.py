"""
Payment-provider webhook adapters for `workflow pay-hook`.

Each adapter mirrors ONE provider's signing code from the product MR, so the
qa-payment-agent flow can send synthetic, correctly signed callbacks to a
DEV stand. An adapter module exposes:

    NAME: str
    GITLAB_REPO: str                       repo token the signing keys live in
    CONFIG_PATH: str                       file at the MR ref holding the keys
    ENDPOINTS: dict[kind -> path]          kind = "deposit" | "withdrawal"
    load_config(ref) -> dict               provider config section at that ref
    build_body(kind, cfg, **fields) -> dict
    sign(cfg, body, ts) -> dict            request headers carrying the signature
    verify(cfg, body, headers) -> bool     self-check against our public key

A new provider = a new module here + a test, written from its MR's signing code.
"""

from __future__ import annotations

import importlib

PROVIDERS = ("highhelp",)


def get_adapter(provider: str):
    name = provider.lower()
    if name not in PROVIDERS:
        known = ", ".join(PROVIDERS)
        raise ValueError(f"Unknown provider '{provider}'. Known: {known}. "
                         f"A new provider needs an adapter in modules/payhook/adapters/.")
    return importlib.import_module(f"modules.payhook.adapters.{name}")
