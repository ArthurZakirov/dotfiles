"""Reusable personal-profile credential provider (all credentials synthetic)."""

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "home/dot_local/share/dotfiles-secrets/secret_store.py"


@pytest.fixture
def provider():
    spec = importlib.util.spec_from_file_location("dotfiles_secrets", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_can_lookup_different_service_credentials_with_one_backend(monkeypatch, provider):
    commands = []

    def fake_run(argv, **kwargs):
        commands.append((argv, kwargs))
        if argv[0] == "security":
            return subprocess.CompletedProcess(argv, 0, "synthetic-keychain-token\n", "")
        assert kwargs["env"]["BWS_ACCESS_TOKEN"] == "synthetic-keychain-token"
        return subprocess.CompletedProcess(argv, 0, json.dumps([
            {"key": "OPENAI_TUNNEL_API_KEY", "value": "synthetic-tunnel-runtime"},
            {"key": "ANOTHER_SERVICE_API_KEY", "value": "synthetic-other-service"},
            {"key": "UNRELATED_TOKEN", "value": "not requested"},
        ]), "")

    monkeypatch.setattr(provider.subprocess, "run", fake_run)
    first = provider.read_secrets({"OPENAI_TUNNEL_API_KEY"}, "injected-account", {"PATH": "/bin"})
    second = provider.read_secrets({"ANOTHER_SERVICE_API_KEY"}, "injected-account", {"PATH": "/bin"})
    assert first == {"OPENAI_TUNNEL_API_KEY": "synthetic-tunnel-runtime"}
    assert second == {"ANOTHER_SERVICE_API_KEY": "synthetic-other-service"}
    assert all(call[1]["timeout"] in (30, 60) for call in commands)
    assert all("synthetic-" not in str(argv) for argv, _ in commands)


@pytest.mark.parametrize("payload", [
    '{"data":[]}',
    '[{"key":"OPENAI_TUNNEL_API_KEY"}]',
    '[{"key":"OPENAI_TUNNEL_API_KEY","value":"a"},{"key":"OPENAI_TUNNEL_API_KEY","value":"b"}]',
])
def test_malformed_response_is_redacted(monkeypatch, provider, payload):
    def fake_run(argv, **kwargs):
        if argv[0] == "security":
            return subprocess.CompletedProcess(argv, 0, "synthetic-secret\n", "")
        return subprocess.CompletedProcess(argv, 0, payload, "sensitive-backend-output")
    monkeypatch.setattr(provider.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="Shared secrets unavailable or malformed") as error:
        provider.read_secrets({"OPENAI_TUNNEL_API_KEY"}, "injected-account")
    assert "synthetic-secret" not in str(error.value)
    assert "sensitive-backend-output" not in str(error.value)


def test_missing_account_does_not_start_backend(provider):
    with pytest.raises(ValueError, match="account configured"):
        provider.read_secrets({"SOME_API_KEY"}, "")
