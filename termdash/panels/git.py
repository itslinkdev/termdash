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

    def watch_data(self, data: GitData) -> None:
        if not self.is_mounted:
            return
        self.query_one("#git-branch", Static).update(data.branch)
        self.query_one("#git-sync", Static).update(
            f"ahead {data.ahead} / behind {data.behind}"
        )
        self.query_one("#git-files", Static).update(
            "\n".join(f"{status}  {name}" for status, name in data.files) or "Working tree clean"
        )
        self.query_one("#git-summary", Static).update(
            f"{len(data.files)} changed / +{data.additions} -{data.deletions}"
        )
