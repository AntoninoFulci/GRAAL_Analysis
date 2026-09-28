from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import subprocess


def test_small_file_fast_fingerprint_uses_sha256(tmp_path):
    from graal_pipeline.state import fingerprint_path

    path = tmp_path / "settings.json"
    path.write_bytes(b"abc")

    fingerprint = fingerprint_path(path, mode="fast", small_file_limit=10)

    assert fingerprint["sha256"] == sha256(b"abc").hexdigest()
    assert fingerprint["size"] == 3
    assert "mtime_ns" in fingerprint


def test_large_file_fast_fingerprint_uses_identity_and_root_metadata(tmp_path):
    from graal_pipeline.state import fingerprint_path

    path = tmp_path / "events.root"
    path.write_bytes(b"large payload")

    fingerprint = fingerprint_path(
        path,
        mode="fast",
        small_file_limit=2,
        root_metadata_reader=lambda _: {"trees": {"h85": {"entries": 12}}},
    )

    assert "sha256" not in fingerprint
    assert fingerprint["size"] == len(b"large payload")
    assert fingerprint["root"] == {"trees": {"h85": {"entries": 12}}}


def test_full_fingerprint_hashes_large_files_and_reuses_cache(tmp_path):
    from graal_pipeline.state import DigestCache, fingerprint_path

    path = tmp_path / "events.root"
    path.write_bytes(b"large payload")
    cache = DigestCache()

    first = fingerprint_path(path, mode="full", small_file_limit=2, cache=cache)
    second = fingerprint_path(path, mode="full", small_file_limit=2, cache=cache)

    assert first == second
    assert first["sha256"] == sha256(b"large payload").hexdigest()
    assert cache.misses == 1
    assert cache.hits == 1


def test_directory_manifest_is_sorted_and_uses_relative_names(tmp_path):
    from graal_pipeline.state import fingerprint_path

    directory = tmp_path / "dataset"
    directory.mkdir()
    (directory / "z.root").write_bytes(b"z")
    (directory / "a.root").write_bytes(b"a")

    first = fingerprint_path(directory)
    second = fingerprint_path(directory)

    assert first == second
    assert [entry["name"] for entry in first["entries"]] == ["a.root", "z.root"]
    assert all(not Path(entry["name"]).is_absolute() for entry in first["entries"])


def test_fingerprint_mismatch_reasons_name_changed_fields():
    from graal_pipeline.state import fingerprint_mismatch_reasons

    reasons = fingerprint_mismatch_reasons(
        {"size": 3, "root": {"entries": 10}},
        {"size": 4, "root": {"entries": 9}},
    )

    assert "root.entries: expected 10, found 9" in reasons
    assert "size: expected 3, found 4" in reasons


def _init_git_repository(path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    source = path / "module.py"
    source.write_text("VALUE = 1\n")
    subprocess.run(["git", "-C", str(path), "add", "module.py"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Pipeline Test",
            "-c",
            "user.email=pipeline@example.invalid",
            "commit",
            "-qm",
            "initial",
        ],
        check=True,
    )
    return source


def test_responsible_code_identity_distinguishes_clean_and_dirty_git(tmp_path):
    from graal_pipeline.state import responsible_code_fingerprint

    root = tmp_path / "repo"
    root.mkdir()
    source = _init_git_repository(root)

    clean = responsible_code_fingerprint([source], root)
    source.write_text("VALUE = 2\n")
    dirty = responsible_code_fingerprint([source], root)

    assert clean["git_commit"] == dirty["git_commit"]
    assert clean["dirty"] is False
    assert clean["files"] == {}
    assert dirty["dirty"] is True
    assert dirty["files"]["module.py"] == sha256(b"VALUE = 2\n").hexdigest()


def test_no_git_and_unavailable_git_remain_deterministic(tmp_path):
    from graal_pipeline.state import responsible_code_fingerprint

    root = tmp_path / "plain"
    root.mkdir()
    source = root / "module.py"
    source.write_text("VALUE = 1\n")

    no_repo_first = responsible_code_fingerprint([source], root)
    no_repo_second = responsible_code_fingerprint([source], root)
    no_binary_first = responsible_code_fingerprint(
        [source], root, git_executable="git-does-not-exist-for-test"
    )
    no_binary_second = responsible_code_fingerprint(
        [source], root, git_executable="git-does-not-exist-for-test"
    )

    assert no_repo_first == no_repo_second
    assert no_binary_first == no_binary_second
    assert no_repo_first["git_commit"] is None
    assert no_binary_first["git_commit"] is None
    assert no_repo_first["files"] == no_binary_first["files"]
