from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from termdash.data import GitData


class GitPanel(Widget):
    data = reactive(GitData)
    BORDER_TITLE = "03 / Git status"

    def compose(self) -> ComposeResult:
        yield Static(id="git-branch", classes="metric")
        yield Static(id="git-sync", classes="muted")
        yield Static(id="git-files")
        yield Static(id="git-summary", classes="muted")
        yield Static(id="git-commit")
        yield Static(id="git-time", classes="muted")

    def watch_data(self, data: GitData) -> None:
        if not self.is_mounted:
            return
        self.query_one("#git-branch", Static).update(Text(
            data.branch if data.is_repo else "Not a Git repository",
            no_wrap=True, overflow="ellipsis",
        ))
        self.query_one("#git-sync", Static).update(
            f"ahead {data.ahead} / behind {data.behind}" if data.is_repo else "Choose a repo with --repo PATH"
        )
        self.query_one("#git-files", Static).update(Text(
            ("\n".join(f"{status}  {name}" for status, name in data.files[:3])
             or "Working tree clean") if data.is_repo else "No repository data to display.",
            no_wrap=True, overflow="ellipsis",
        ))
        self.query_one("#git-summary", Static).update(
            f"Staged {data.staged} / unstaged {data.unstaged} / new {data.untracked}"
            if data.is_repo else ""
        )
        self.query_one("#git-commit", Static).update(Text(
            (data.last_commit_subject or "No commits yet") if data.is_repo else "",
            no_wrap=True, overflow="ellipsis",
        ))
        self.query_one("#git-commit", Static).tooltip = Text(data.last_commit_subject)
        self.query_one("#git-time", Static).update(Text(data.last_commit_relative_time))
