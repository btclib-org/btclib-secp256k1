# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

r"""Re-check every vendored-vector pin against upstream, weekly.

tests/README.md pins each vendored vector to a commit and a git blob
SHA-1, with a documented manual procedure to re-check one.
This automates that procedure and reports drift, rather than fixing it:
refreshing a vector file is a decision this script does not get to
make, so what it opens is an issue, never a commit. Ported from a
sibling repository's own check_vendored_vectors.py, which this
package's README convention matches by design.

Scope is narrower than the README could need, though nothing in this
project's own entries reaches the narrower part: only
an entry whose `behind` already reads 0 -- what a human last confirmed
was exactly at upstream's tip -- is checked. An entry already
documented as behind would be a decision already made, and
re-reporting the same gap every week would be noise rather than news;
a sibling repository's own README carries that shape and this one
does not.

A path upstream deleted or renamed away reaches this script as ordinary
drift: the "commits touching a path" call answers with the commit that
removed it, which is not the pin. Whether a commit changed the file or
removed it is a reading of that commit this script does not make, so
its report says the latest commit may have done either. The call
answers an empty list only for a path the branch it walks never held,
and that is reported rather than raising, with no tip to name.

An entry pinned to a fork's own pull-request branch rather than to a
repository's default one names that branch in a `ref` field, which
`_latest_commit` passes on as the "commits touching a path" call's own
`sha` parameter -- GitHub's name for it, a branch or a tag as much as a
commit despite the name. Without it the call resolves against the
default branch alone and answers an empty list for a path that lives
only on the named one, which is reported as a path the default branch
never held regardless of whether the pin is current. Nothing in this
project's own README stands on a non-default branch today, so `ref` is
absent from every entry and the call is asked exactly as it always was.

Two more shapes this script does not attempt, for the same reason the
sibling script does not, present or not in this project's own README
today: a path carrying a `<name>` placeholder, where one pin serves several
files at once, and an entry with no `commit` at all. A heading owning no
fenced block of its own is a third, and different in kind from the other
two: there is no block to read a field out of, so it is listed under its
own reason rather than folded into "no commit to check against" --
whether it is a group heading a finer one supersedes, or a pin whose
block an edit broke, is not for this script to tell apart, only to
report by name. Every heading the README carries but this script did not
check is listed in its own report, so nothing silently reads as "checked
and clean" that was not checked at all.

The sibling copy also collapses skip lines that repeat one heading and
one reason, a shape that only a heading owning several fenced blocks
can produce. tests/README.md gives every heading here exactly one
block, so no skip line this script builds ever repeats today -- a
property of this file, not a shape the parsing above forbids, and not
carried here for that reason.

The issue title is the caller's, which is what the copies owe each
other: the sibling repository passes two ledgers through one script --
a pin behind upstream and a verdict read at a revision that has moved
are different news, acted on differently -- so a title fixed in the
module would name one issue for the pair, each run rewriting what the
other wrote. One ledger passes through this copy, so the argument buys
nothing here on its own; it is taken because a caller's argument list
is the half of the two files that is meant to stay identical. What
answers to the sibling's own two-ledger shape is not taken:
`readme_path` keeps its name, this tree calling that file a README
everywhere else it names it.

    python .github/scripts/check_vendored_vectors.py \
        tests/README.md "Vendored vectors behind upstream"
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# resolved once: S607 is what a bare "gh" in a subprocess list would be,
# a partial executable path relying on PATH's own search order rather
# than naming what actually runs
_GH = shutil.which("gh") or "gh"

# a vendored file's own ### heading, so a drift report -- and the
# skipped-entry list -- can name the file rather than only its upstream
# path
_HEADING = re.compile(r"^### (.+)$", re.MULTILINE)

# a fenced block's key/value lines; a value's own continuation onto a
# further, unindented-marker line (the sibling repository's README wraps
# "behind" that way in a couple of entries) is not captured, and is not
# needed -- every check below reads only the first line of a field. The
# separator is `[ \t]+` rather than `\s+`: `\s` also matches the newline
# ending a bare key's own line, so a key written with no value and no
# trailing whitespace, and not last in its block, would let the separator
# cross into the following line and capture that whole line as its own
# value -- leaving the field the next line actually names unmatched.
# The separator and the value after it are optional, so a bare key still
# matches, with an empty value: the trailing-whitespace hook strips a key
# followed by only spaces down to the bare key, and `behind` written that
# way is a line present but empty, not a line missing.
_FIELD = re.compile(
    r"^(repo|path|ref|commit|blob|pulled|behind)(?:[ \t]+(.*))?$", re.MULTILINE
)


@dataclass(frozen=True)
class Entry:
    """One pin this script can re-check: a single blob, a live commit.

    `ref` is the branch (or tag, or sha) GitHub's "commits touching a
    path" API should walk instead of the repository's own default
    branch -- absent for every pin standing on a default branch, which
    is every pin this project's own README carries today, and present
    for one standing on a fork's own pull-request branch, which the API
    cannot otherwise find at all: asking it with no `ref` answers an
    empty list for that path regardless of whether the pin is current,
    which is reported as a path the default branch never held.
    """

    heading: str
    repo: str
    path: str
    commit: str
    ref: str | None = None


@dataclass(frozen=True)
class Drift:
    """A pin whose commit is no longer the tip of its own path."""

    entry: Entry
    latest_commit: str
    latest_date: str

    @property
    def has_no_tip(self) -> bool:
        """True where no commit on the branch walked touches the pinned path.

        The empty `latest_commit` is what says so: there is no tip to
        name, `_latest_commit` having answered None. Reading it through
        a name keeps that encoding in one place.
        """
        return not self.latest_commit


def _entries_at_tip(readme: str) -> tuple[list[Entry], list[str]]:
    """Return the checkable entries, and the headings this skips.

    A heading is skippable for several reasons: no fenced block of its
    own -- a group heading superseded by finer ones, or a pin whose block
    an edit broke, the two indistinguishable from here -- no
    repo/path/commit triple, a path carrying a `<name>` placeholder, no
    `behind` line, a `behind` line with no value, or a `behind` already
    other than 0 -- a gap a human already decided not to close. The two
    before it are named apart from that last one, being blocks nobody
    has assessed rather than a decision somebody made.
    """
    entries: list[Entry] = []
    skipped: list[str] = []
    owned: set[str] = set()
    heading = ""
    pos = 0
    for match in re.finditer(r"```text\n(.*?)\n```", readme, re.DOTALL):
        headings_before = _HEADING.findall(readme[pos : match.start()])
        if headings_before:
            heading = headings_before[-1]
        pos = match.end()
        owned.add(heading)

        fields = dict(_FIELD.findall(match.group(1)))
        repo, path, commit = (
            fields.get("repo"),
            fields.get("path"),
            fields.get("commit"),
        )
        if not (repo and path and commit):
            skipped.append(f"{heading} (no commit to check against)")
            continue
        if "<" in path:
            skipped.append(f"{heading} (one pin serves several files)")
            continue
        behind = fields.get("behind")
        if behind is None:
            skipped.append(f"{heading} (no behind line at all)")
            continue
        if not behind.strip():
            skipped.append(f"{heading} (behind line present but empty)")
            continue
        if not behind.startswith("0"):
            skipped.append(f"{heading} (already documented as behind)")
            continue
        ref = fields.get("ref")
        entries.append(
            Entry(
                heading,
                repo,
                path.strip(),
                commit.split()[0],
                ref.strip() if ref else None,
            )
        )
    skipped.extend(
        f"{h} (no fenced block)" for h in _HEADING.findall(readme) if h not in owned
    )
    return entries, skipped


def _latest_commit(
    repo: str, path: str, ref: str | None = None
) -> tuple[str, str] | None:
    """Return the sha and date of the most recent commit touching path.

    None where no commit on the branch walked touches the path at all,
    which is a path that branch never held: one deleted or renamed away
    answers with the commit that removed it instead, and comes back
    from here as an ordinary tip. Answering None rather than unpacking
    one commit out of an empty list is what lets `report` name the pin
    as drift with no tip, instead of the run going red on a bare
    `ValueError` and no issue ever opening.

    `ref` is GitHub's own `sha` parameter on this endpoint -- a branch,
    a tag or a commit to start walking history from, despite the name --
    left off where an `Entry` carries none, which is every pin standing
    on its repository's default branch: the parameter's own default
    matches it without this function naming the branch.
    """
    args = [
        _GH,
        "api",
        "--method",
        "GET",
        f"repos/{repo}/commits",
        "-f",
        f"path={path}",
        "-f",
        "per_page=1",
    ]
    if ref is not None:
        args.extend(("-f", f"sha={ref}"))
    result = subprocess.run(  # noqa: S603
        args,
        capture_output=True,
        check=True,
        encoding="utf-8",
    )
    commits = json.loads(result.stdout)
    if not commits:
        return None
    commit = commits[0]
    date: str = commit["commit"]["committer"]["date"][:10]
    sha: str = commit["sha"]
    return sha, date


def find_drift(readme_path: Path) -> tuple[list[Drift], list[str]]:
    """Return every pin no longer at upstream's tip, and what was skipped."""
    entries, skipped = _entries_at_tip(readme_path.read_text(encoding="utf-8"))
    drifted = []
    for entry in entries:
        latest = _latest_commit(entry.repo, entry.path, entry.ref)
        if latest is None:
            # a path the branch walked never held: drift with no tip to name
            drifted.append(Drift(entry, "", ""))
        elif latest[0] != entry.commit:
            drifted.append(Drift(entry, *latest))
    return drifted, skipped


def _branch(entry: Entry) -> str:
    """Name the branch, tag or commit `_latest_commit` walked for an entry."""
    return f"`{entry.ref}`" if entry.ref else "the default branch"


def _issue_body(readme_path: Path, drifted: list[Drift], skipped: list[str]) -> str:
    lines = [
        f"`{readme_path}` pins below are no longer at upstream's tip.",
        "Refreshing is a decision, not a chore -- this issue only reports it.",
        "",
    ]
    for drift in drifted:
        if drift.has_no_tip:
            lines.append(
                f"- **{drift.entry.heading}**: pinned to"
                f" `{drift.entry.commit}`, and no commit on {_branch(drift.entry)}"
                f" of `{drift.entry.repo}` touches `{drift.entry.path}` --"
                " a path that branch never held"
            )
            continue
        lines.append(
            f"- **{drift.entry.heading}**: pinned to `{drift.entry.commit}`,"
            f" the latest commit touching `{drift.entry.path}` is now"
            f" `{drift.latest_commit}` ({drift.latest_date}),"
            f" `{drift.entry.repo}` -- which may have deleted or renamed"
            " the file rather than changed it"
        )
    if skipped:
        lines.append("")
        lines.append("Not checked by this run, for the reason named:")
        lines.extend(f"- {heading}" for heading in skipped)
    return "\n".join(lines)


def _open_issue_number(title: str) -> str | None:
    result = subprocess.run(  # noqa: S603
        [
            _GH,
            "issue",
            "list",
            "--state",
            "open",
            "--search",
            f'"{title}" in:title',
            "--json",
            "number",
        ],
        capture_output=True,
        check=True,
        encoding="utf-8",
    )
    issues = json.loads(result.stdout)
    return str(issues[0]["number"]) if issues else None


def report(
    readme_path: Path, title: str, drifted: list[Drift], skipped: list[str]
) -> None:
    """Open, update, or close this ledger's tracking issue, whichever applies.

    The title is what tells one ledger's issue from another's: it is the
    search term that finds an issue already open as well as the title a
    new one is created under, so a caller passing a title of its own
    gets an issue of its own.
    """
    number = _open_issue_number(title)
    if not drifted:
        if number is not None:
            subprocess.run(  # noqa: S603
                [
                    _GH,
                    "issue",
                    "close",
                    number,
                    "--comment",
                    "Re-checked: every pin with behind: 0 is still at upstream's tip.",
                ],
                check=True,
            )
        return
    body = _issue_body(readme_path, drifted, skipped)
    if number is None:
        subprocess.run(  # noqa: S603
            [_GH, "issue", "create", "--title", title, "--body", body],
            check=True,
        )
    else:
        subprocess.run(  # noqa: S603
            [_GH, "issue", "edit", number, "--body", body], check=True
        )


def main() -> int:
    """Check the README named on argv, report drift, and say so on stdout.

    The title names the issue this run opens, updates or closes. It is
    required, which is what makes it a positional beside the path: a
    default would be this file's own opinion about an issue the caller
    owns, and the caller is the one thing this script shares with its
    sibling copy. The one option here is a boolean, so what reads it is
    the filter below rather than a parser.

    --dry-run skips opening, updating or closing the issue: what
    btclib-org/.github's reusable-vendored-vectors.yml passes on every
    trigger but the schedule, so a change to this script or to the
    README, or a dispatch, is exercised without the run editing whatever
    tracking issue happens to be open at the time.
    """
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = len(args) != len(sys.argv) - 1
    if len(args) != 2:
        # a human running this by hand is the only way here, the workflow
        # passing both every time: without this check, the indexing below
        # would answer with an IndexError naming a list instead
        print(
            f"usage: {Path(sys.argv[0]).name} <README path> <issue title> [--dry-run]",
            file=sys.stderr,
        )
        return 2
    readme_path, title = Path(args[0]), args[1]
    drifted, skipped = find_drift(readme_path)
    for drift in drifted:
        if drift.has_no_tip:
            print(
                f"NO COMMIT: {drift.entry.heading} pinned to"
                f" {drift.entry.commit}, and no commit on"
                f" {_branch(drift.entry)} of {drift.entry.repo} touches"
                f" {drift.entry.path}"
            )
            continue
        print(
            f"BEHIND: {drift.entry.heading} pinned to {drift.entry.commit},"
            f" latest commit touching it is {drift.latest_commit}"
            f" ({drift.latest_date}), which may have deleted or renamed it"
        )
    for heading in skipped:
        print(f"SKIPPED: {heading}")
    if not drifted:
        print("Every checked pin is still at upstream's tip.")
    if not dry_run:
        report(readme_path, title, drifted, skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
