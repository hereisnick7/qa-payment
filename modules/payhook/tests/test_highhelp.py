import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from modules.payhook import cli
from modules.payhook.adapters import get_adapter, highhelp


@pytest.fixture(scope="module")
def cfg():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    pub_pem = key.public_key().public_bytes(serialization.Encoding.PEM,
                                            serialization.PublicFormat.SubjectPublicKeyInfo)
    return {
        "project_id": "proj-1",
        "private_key_pem": pem,
        "public_key_b64url": base64.urlsafe_b64encode(pub_pem).decode().rstrip("="),
    }


FIELDS = dict(status="success", request_id="req-1", payment_id="pay-1", amount=1349900)


def test_normalize_matches_backend_format():
    body = {"b": {"y": [1, 2]}, "a": True, "c": None}
    assert sorted(highhelp.normalize(body)) == ["a:1", "b:y:0:1", "b:y:1:2", "c:None"]


def test_deposit_body_defaults_initial_amount_to_amount(cfg):
    body = highhelp.build_body("deposit", cfg, **FIELDS)
    assert body["payment_info"] == {"amount": 1349900, "currency": "UZS", "initial_amount": 1349900}
    assert body["general"] == {"request_id": "req-1", "payment_id": "pay-1"}


def test_withdrawal_body_has_no_initial_amount(cfg):
    body = highhelp.build_body("withdrawal", cfg, **FIELDS, initial_amount=5)
    assert "initial_amount" not in body["payment_info"]


def test_sign_verify_roundtrip_and_tamper(cfg):
    body = highhelp.build_body("deposit", cfg, **FIELDS)
    headers = highhelp.sign(cfg, body, 1700000000)
    assert highhelp.verify(cfg, body, headers)
    body["payment_info"]["amount"] = 1
    assert not highhelp.verify(cfg, body, headers)


def test_make_hook_bad_sig_still_reports_self_check_and_corrupts(cfg):
    curl, ok = cli.make_hook(highhelp, cfg, "deposit", FIELDS, "https://dev.example.com", 1700000000, bad_sig=True)
    good = highhelp.sign(cfg, highhelp.build_body("deposit", cfg, **FIELDS), 1700000000)["x-access-signature"]
    assert ok
    assert good not in curl
    assert "https://dev.example.com/api/webhook/highhelp/deposit" in curl
    assert "x-access-timestamp: 1700000000" in curl


def test_check_host_refuses_non_allowlisted():
    with pytest.raises(ValueError):
        cli.check_host("https://prod.example.com", {"dev.example.com"})
    assert cli.check_host("https://dev.example.com/", {"dev.example.com"}) == "https://dev.example.com"


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError):
        get_adapter("nopay")


def test_cli_prints_usage_on_missing_flags(capsys):
    assert cli.run_command("pay-hook", ["pay-hook", "highhelp", "deposit", "--status=success"])
    assert "Использование" in capsys.readouterr().out
