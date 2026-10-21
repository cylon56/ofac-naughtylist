#!/usr/bin/env python3
"""
Railway cron job script.

Runs the OFAC pipeline, then commits and pushes any data changes to GitHub.

Required environment variables:
    GITHUB_TOKEN    - Fine-grained PAT for this repo only, Contents: read and write.
                      Passed to git through its environment, never in a URL or log.
    GITHUB_REPO     - Repository in "owner/repo" format (e.g. "cylon56/ofac-naughtylist")
    GITHUB_BRANCH   - Branch to push to (default: "main")
"""

import base64
import json
import logging
import os
import subprocess
import sys
import tempfile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

REDACTED = "***"

# Values that must never appear in a log line. git_auth_env() registers the
# token and its encoded form here; run() masks them in commands, stdout and stderr.
_secrets: set[str] = set()


def register_secret(value: str) -> None:
    """Mark a value as secret so run() masks it in every log line."""
    if value:
        _secrets.add(value)


def redact(text: str) -> str:
    """Replace every registered secret in text with a placeholder."""
    # Longest first, so a secret that contains another is masked whole.
    for secret in sorted(_secrets, key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    return text


def git_auth_env(token: str, env: dict[str, str]) -> dict[str, str]:
    """Return a copy of env that gives git an HTTPS auth header for github.com.

    The header goes through GIT_CONFIG_COUNT/KEY_n/VALUE_n, so the token is
    never in a URL, in argv, in .git/config or in a log line. Entries that env
    already sets through GIT_CONFIG_COUNT are kept.
    """
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    register_secret(token)
    register_secret(basic)
    try:
        n = int(env.get("GIT_CONFIG_COUNT", "0"))
    except ValueError:
        n = 0
    return {
        **env,
        "GIT_CONFIG_COUNT": str(n + 1),
        f"GIT_CONFIG_KEY_{n}": "http.https://github.com/.extraheader",
        f"GIT_CONFIG_VALUE_{n}": f"AUTHORIZATION: basic {basic}",
        "GIT_TERMINAL_PROMPT": "0",
    }


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command and log it, with registered secrets masked."""
    logger.info("$ %s", redact(" ".join(cmd)))
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.stdout:
        logger.info(redact(result.stdout.rstrip()))
    if result.returncode != 0 and result.stderr:
        logger.error(redact(result.stderr.rstrip()))
    return result


def main() -> int:
    github_token = os.environ.get("GITHUB_TOKEN")
    github_repo = os.environ.get("GITHUB_REPO")
    github_branch = os.environ.get("GITHUB_BRANCH", "main")

    if not github_token or not github_repo:
        logger.error("GITHUB_TOKEN and GITHUB_REPO environment variables are required")
        return 1

    # git gets the token only through its environment. The pipeline gets an
    # environment without the token, because it does not need it.
    base_env = {k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"}
    git_env = git_auth_env(github_token, base_env)

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_url = f"https://github.com/{github_repo}.git"

        # Clone repo
        result = run(
            ["git", "clone", "--depth=1", f"--branch={github_branch}", repo_url, tmpdir],
            env=git_env,
        )
        if result.returncode != 0:
            logger.error("Failed to clone repository")
            return 1

        # Run pipeline inside the cloned repo
        logger.info("Running OFAC pipeline...")
        result = run(
            [sys.executable, "-m", "src.main", "--output-dir", os.path.join(tmpdir, "data")],
            cwd=tmpdir,
            env={**base_env, "PYTHONPATH": tmpdir},
        )
        if result.returncode != 0:
            logger.error("Pipeline failed")
            return 1

        # The pipeline (src.main) refreshes the README snapshot itself, so the
        # commit below just needs to stage data/ and README.md.

        # Check for changes
        result = run(["git", "diff", "--quiet", "data/", "README.md"], cwd=tmpdir)
        if result.returncode == 0:
            logger.info("No changes detected — data is up to date")
            return 0

        # Read metadata for commit message
        try:
            with open(os.path.join(tmpdir, "data", "metadata.json")) as f:
                meta = json.load(f)
            addr_count = meta["total_addresses"]
        except Exception:
            addr_count = "unknown"

        # Commit and push
        run(["git", "config", "user.name", "Naughtylist Bot"], cwd=tmpdir)
        run(["git", "config", "user.email", "naughtylist-bot@users.noreply.github.com"], cwd=tmpdir)
        run(["git", "add", "data/", "README.md"], cwd=tmpdir)

        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        commit_msg = f"naughtylist updated — {timestamp} — {addr_count} addresses checked twice"

        result = run(["git", "commit", "-m", commit_msg], cwd=tmpdir)
        if result.returncode != 0:
            logger.error("Commit failed")
            return 1

        result = run(["git", "push", "origin", github_branch], cwd=tmpdir, env=git_env)
        if result.returncode != 0:
            logger.error("Push failed")
            return 1

        logger.info("Successfully pushed updated data")
        return 0


if __name__ == "__main__":
    sys.exit(main())
