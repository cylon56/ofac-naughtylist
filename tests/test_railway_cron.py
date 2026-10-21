"""Tests for scripts/railway_cron.py: the GitHub token must never be logged."""

import base64
import importlib.util
import logging
import os
import subprocess

import pytest

_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "railway_cron.py")
_spec = importlib.util.spec_from_file_location("railway_cron", _SCRIPT)
railway_cron = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(railway_cron)

TOKEN = "github_pat_TESTSECRET0123456789abcdefXYZ"
BASIC = base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    monkeypatch.setenv("GITHUB_BRANCH", "main")
    for key in list(os.environ):
        if key.startswith("GIT_CONFIG_"):
            monkeypatch.delenv(key)
    railway_cron._secrets.clear()
    yield
    railway_cron._secrets.clear()


class FakeGit:
    """Stand-in for subprocess.run that records calls and echoes secrets back."""

    def __init__(self, fail_push: bool = False):
        self.calls = []
        self.fail_push = fail_push

    def __call__(self, cmd, **kwargs):
        env = kwargs.get("env") or {}
        self.calls.append((list(cmd), env))
        # Echo the auth header to stdout and stderr, as a verbose git or a
        # misbehaving tool might, so the test proves run() masks it.
        leak = " ".join([*env.values(), TOKEN])
        if cmd[:3] == ["git", "diff", "--quiet"]:
            return subprocess.CompletedProcess(cmd, 1, "", "")  # changes present
        if cmd[:2] == ["git", "push"] and self.fail_push:
            return subprocess.CompletedProcess(cmd, 128, leak, f"fatal: auth failed {leak}")
        return subprocess.CompletedProcess(cmd, 0, f"ok {leak}", f"warn {leak}")


def _run_main(monkeypatch, caplog, fake):
    monkeypatch.setattr(railway_cron.subprocess, "run", fake)
    caplog.set_level(logging.INFO)
    return railway_cron.main()


def _assert_no_secret(caplog):
    text = caplog.text
    assert TOKEN not in text
    assert BASIC not in text
    for record in caplog.records:
        assert TOKEN not in record.getMessage()
        assert BASIC not in record.getMessage()


def test_token_not_in_logs_or_argv(monkeypatch, caplog):
    fake = FakeGit()
    assert _run_main(monkeypatch, caplog, fake) == 0
    _assert_no_secret(caplog)
    assert railway_cron.REDACTED in caplog.text
    for cmd, _env in fake.calls:
        joined = " ".join(cmd)
        assert TOKEN not in joined
        assert BASIC not in joined


def test_clone_url_has_no_credentials(monkeypatch, caplog):
    fake = FakeGit()
    _run_main(monkeypatch, caplog, fake)
    clone_cmd, clone_env = fake.calls[0]
    assert clone_cmd[:2] == ["git", "clone"]
    assert "https://github.com/owner/repo.git" in clone_cmd
    assert not any("@" in part for part in clone_cmd)
    assert clone_env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    assert clone_env["GIT_CONFIG_VALUE_0"] == f"AUTHORIZATION: basic {BASIC}"


def test_push_gets_auth_and_pipeline_does_not(monkeypatch, caplog):
    fake = FakeGit()
    _run_main(monkeypatch, caplog, fake)
    push = [env for cmd, env in fake.calls if cmd[:2] == ["git", "push"]]
    assert push and push[0]["GIT_CONFIG_VALUE_0"].endswith(BASIC)
    pipeline = [env for cmd, env in fake.calls if "src.main" in cmd]
    assert pipeline
    assert "GITHUB_TOKEN" not in pipeline[0]
    assert not any(TOKEN in v or BASIC in v for v in pipeline[0].values())


def test_existing_git_config_env_is_kept():
    env = railway_cron.git_auth_env(TOKEN, {"GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "a"})
    assert env["GIT_CONFIG_COUNT"] == "3"
    assert env["GIT_CONFIG_KEY_0"] == "a"
    assert env["GIT_CONFIG_KEY_2"] == "http.https://github.com/.extraheader"
    assert env["GIT_CONFIG_VALUE_2"] == f"AUTHORIZATION: basic {BASIC}"


def test_failed_push_stderr_is_redacted(monkeypatch, caplog):
    fake = FakeGit(fail_push=True)
    assert _run_main(monkeypatch, caplog, fake) == 1
    assert "auth failed" in caplog.text
    _assert_no_secret(caplog)


def test_redact_masks_registered_values():
    railway_cron.register_secret("s3cret")
    assert railway_cron.redact("a s3cret b") == f"a {railway_cron.REDACTED} b"
    railway_cron.register_secret("")
    assert railway_cron.redact("plain") == "plain"
