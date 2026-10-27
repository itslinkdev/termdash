import os
from pathlib import Path
import subprocess

import pytest

from termdash.providers.git import GitProvider
from termdash.providers import git as git_module


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                            text=True, encoding="utf-8")
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    # Keep tests independent of the machine's signing, hooks and Git identity.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "core.autocrlf", "false")
    return tmp_path


def commit(repo, subject="Initial [commit]"):
    git(repo, "add", ".")
    git(repo, "commit", "--allow-empty", "-m", subject)


def test_clean_repo_and_default_cwd(repo, monkeypatch):
    commit(repo)
    monkeypatch.chdir(repo)
    sample = GitProvider().fetch()
    assert sample.is_repo
    assert sample.branch == "main"
    assert (sample.staged, sample.unstaged, sample.untracked) == (0, 0, 0)
    assert (sample.ahead, sample.behind) == (0, 0)
    assert sample.files == ()
    assert sample.last_commit_subject == "Initial [commit]"
    assert sample.last_commit_relative_time


def test_dirty_repo_counts_each_status_and_nested_untracked_files(repo):
    tracked = repo / "tracked file.txt"
    tracked.write_text("before\n")
    commit(repo)
    tracked.write_text("staged\n")
    git(repo, "add", ".")
    tracked.write_text("unstaged too\n")
    (repo / "new folder").mkdir()
    (repo / "new folder" / "one.txt").write_text("one")
    (repo / "new folder" / "two.txt").write_text("two")
    sample = GitProvider(repo).fetch()
    assert (sample.staged, sample.unstaged, sample.untracked) == (1, 1, 2)
    assert ("MM", "tracked file.txt") in sample.files
    assert ("?", "new folder/one.txt") in sample.files


def test_ahead_and_behind_use_local_upstream(repo):
    commit(repo)
    git(repo, "branch", "upstream")
    git(repo, "branch", "--set-upstream-to=upstream")
    commit(repo, "Local change")
    sample = GitProvider(repo).fetch()
    assert (sample.ahead, sample.behind) == (1, 0)
    git(repo, "checkout", "upstream")
    commit(repo, "Upstream change")
    git(repo, "checkout", "main")
    sample = GitProvider(repo).fetch()
    assert (sample.ahead, sample.behind) == (1, 1)


def test_detached_head(repo):
    commit(repo)
    oid = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "--detach")
    sample = GitProvider(repo).fetch()
    assert sample.branch == f"Detached HEAD ({oid[:7]})"
    assert sample.last_commit_subject == "Initial [commit]"


def test_unborn_repo(repo):
    sample = GitProvider(repo).fetch()
    assert sample.is_repo
    assert sample.branch == "main"
    assert sample.last_commit_subject == sample.last_commit_relative_time == ""


def test_not_a_repo_or_missing_directory(tmp_path):
    assert not GitProvider(tmp_path).fetch().is_repo
    assert not GitProvider(tmp_path / "missing").fetch().is_repo


def test_rename_original_path_is_not_counted_as_another_record(repo):
    (repo / "old name.txt").write_text("keep this content\n")
    commit(repo)
    git(repo, "mv", "old name.txt", "renamed ü.txt")
    sample = GitProvider(repo).fetch()
    assert sample.files == (("R.", "renamed ü.txt"),)
    assert (sample.staged, sample.unstaged, sample.untracked) == (1, 0, 0)


def test_unmerged_file(repo):
    tracked = repo / "conflict.txt"
    tracked.write_text("base\n")
    commit(repo)
    git(repo, "checkout", "-b", "other")
    tracked.write_text("other\n")
    commit(repo, "Other")
    git(repo, "checkout", "main")
    tracked.write_text("main\n")
    commit(repo, "Main")
    with pytest.raises(subprocess.CalledProcessError):
        git(repo, "merge", "other")
    sample = GitProvider(repo).fetch()
    assert sample.files == (("UU", "conflict.txt"),)
    assert (sample.staged, sample.unstaged) == (1, 1)


def test_subprocess_timeout_and_errors_are_not_hidden(repo, monkeypatch):
    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 5
        raise subprocess.TimeoutExpired(args[0], 5)

    monkeypatch.setattr(git_module.subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        GitProvider(repo).fetch()

    monkeypatch.setattr(git_module.subprocess, "run", lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 128, "", "permission denied"))
    with pytest.raises(RuntimeError, match="permission denied"):
        GitProvider(repo).fetch()
