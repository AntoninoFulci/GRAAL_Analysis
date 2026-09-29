from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/sync-wiki.sh"


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, check=True
    )


def test_sync_script_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)], text=True, capture_output=True
    )
    assert result.returncode == 0, result.stderr


def test_sync_rejects_empty_wiki_source_before_remote_changes(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "wiki").mkdir()
    shutil.copy2(SCRIPT, repo / "scripts/sync-wiki.sh")
    remote = tmp_path / "wiki.git"
    _git("init", "--bare", str(remote), cwd=tmp_path)
    env = os.environ.copy()
    env["WIKI_REMOTE"] = str(remote)
    result = subprocess.run(
        ["bash", str(repo / "scripts/sync-wiki.sh")],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "no Markdown pages" in result.stderr
    assert not (remote / "refs/heads/master").exists()


def test_sync_publishes_exact_page_set_to_empty_local_remote(tmp_path: Path):
    remote = tmp_path / "wiki.git"
    _git("-c", "init.defaultBranch=main", "init", "--bare", str(remote), cwd=tmp_path)
    env = os.environ.copy()
    env.update(
        WIKI_REMOTE=str(remote),
        GIT_AUTHOR_NAME="Wiki Test",
        GIT_AUTHOR_EMAIL="wiki@example.invalid",
        GIT_COMMITTER_NAME="Wiki Test",
        GIT_COMMITTER_EMAIL="wiki@example.invalid",
    )
    subprocess.run(
        ["bash", str(SCRIPT)], cwd=ROOT, env=env, check=True,
        text=True, capture_output=True,
    )

    stale_checkout = tmp_path / "stale-checkout"
    _git(
        "clone", "--branch", "master", str(remote), str(stale_checkout),
        cwd=tmp_path,
    )
    (stale_checkout / "Stale.md").write_text("obsolete\n")
    _git("add", "Stale.md", cwd=stale_checkout)
    _git(
        "-c", "user.name=Wiki Test", "-c", "user.email=wiki@example.invalid",
        "commit", "-m", "add stale page", cwd=stale_checkout,
    )
    _git("push", "origin", "master", cwd=stale_checkout)

    subprocess.run(
        ["bash", str(SCRIPT)], cwd=ROOT, env=env, check=True,
        text=True, capture_output=True,
    )
    head_after_update = _git(
        "rev-parse", "refs/heads/master", cwd=remote
    ).stdout.strip()
    no_op = subprocess.run(
        ["bash", str(SCRIPT)], cwd=ROOT, env=env, check=True,
        text=True, capture_output=True,
    )
    assert "Wiki already up to date." in no_op.stdout
    assert _git("rev-parse", "refs/heads/master", cwd=remote).stdout.strip() == (
        head_after_update
    )

    checkout = tmp_path / "checkout"
    _git("clone", "--branch", "master", str(remote), str(checkout), cwd=tmp_path)
    expected = {path.name for path in (ROOT / "wiki").glob("*.md")}
    actual = {path.name for path in checkout.glob("*.md")}
    assert actual == expected
