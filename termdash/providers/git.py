"""Read local Git metadata without a shell or network requests."""

import os
from pathlib import Path
import subprocess

from termdash.data import GitData


class GitProvider:
    def __init__(self, repo: str | Path | None = None) -> None:
        self.repo = Path(repo).resolve() if repo is not None else Path.cwd()

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=5,
            env={**os.environ, "LC_ALL": "C", "LANGUAGE": "C", "GIT_OPTIONAL_LOCKS": "0"},
        )

    def fetch(self) -> GitData:
        if not self.repo.is_dir():
            return GitData(is_repo=False)
        status = self._run("status", "--porcelain=v2", "--branch", "-z",
                           "--untracked-files=all")
        if status.returncode:
            if "not a git repository" in status.stderr.lower():
                return GitData(is_repo=False)
            raise RuntimeError(status.stderr.strip() or "Git status failed")

        branch = oid = ""
        ahead = behind = staged = unstaged = untracked = 0
        files: list[tuple[str, str]] = []
        records = iter(status.stdout.split("\0"))
        for record in records:
            if record.startswith("# branch.head "):
                branch = record.removeprefix("# branch.head ")
            elif record.startswith("# branch.oid "):
                oid = record.removeprefix("# branch.oid ")
            elif record.startswith("# branch.ab "):
                plus, minus = record.removeprefix("# branch.ab ").split()
                ahead, behind = int(plus), -int(minus)
            elif record.startswith("? "):
                untracked += 1
                files.append(("?", record[2:]))
            elif record.startswith(("1 ", "2 ", "u ")):
                field_count = {"1": 8, "2": 9, "u": 10}[record[0]]
                fields = record.split(" ", field_count)
                xy, path = fields[1], fields[-1]
                staged += xy[0] != "."
                unstaged += xy[1] != "."
                files.append((xy, path))
                if record.startswith("2 "):
                    # Renames carry a second NUL-delimited path, even if it looks like a record.
                    next(records, None)

        if branch == "(detached)":
            branch = f"Detached HEAD ({oid[:7]})"
        subject = relative_time = ""
        if oid and oid != "(initial)":
            log = self._run("log", "-1", "--no-show-signature", "--format=%s%x00%cr")
            if log.returncode:
                raise RuntimeError(log.stderr.strip() or "Git log failed")
            subject, _, relative_time = log.stdout.rstrip("\n").partition("\0")

        return GitData(
            branch=branch, ahead=ahead, behind=behind, files=tuple(files),
            staged=staged, unstaged=unstaged, untracked=untracked,
            last_commit_subject=subject, last_commit_relative_time=relative_time,
        )
