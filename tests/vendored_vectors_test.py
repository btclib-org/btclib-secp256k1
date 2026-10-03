# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the vendored-vector check of `.github/scripts`.

The workflow of the same name runs that script weekly and lets it open,
edit or close a tracking issue with what it found. Neither end of it is
a suite's to exercise: the reads are `gh` calls against upstream, and
the writes edit an issue of this repository. What is between them is
all of the script's judgement -- which entries of `tests/README.md` it
checks, which it names as skipped and why, what counts as drift, and
which `gh` command each outcome reaches for -- and that is what is here,
with both subprocess boundaries stubbed.

The parsing is the half worth the most. `_entries_at_tip` decides what a
run looks at, and a heading it drops from `entries` and from `skipped`
alike is a pin the report reads as checked and clean when nothing
checked it -- which the module docstring promises cannot happen, and
which was the defect of btclib-org/btclib-secp256k1#415. The README
built here carries one entry of every shape the parser distinguishes, so
a shape that stops being recognised moves a heading from one list to the
other rather than going quiet.

The byte half -- each vendored file hashed against the README, and the
README's blob against upstream's tree -- is exercised at the end, with
files written in a temporary directory and the trees API stubbed, and
over the real README offline.

The script is loaded by path, `.github/scripts` being no package, and
once: `monkeypatch` undoes what each test does to it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

_SCRIPT = (
    Path(__file__).parents[1] / ".github" / "scripts" / "check_vendored_vectors.py"
)


def _load() -> ModuleType:
    """Import the check by path.

    Returns:
        The module.
    """
    spec = importlib.util.spec_from_file_location("check_vendored_vectors", _SCRIPT)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check = _load()

_PINNED = "0f2a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c"
_TIP = "9e8d7c6b5a4938271605f4e3d2c1b0a998877665"

# one entry of every shape the parser tells apart, in the layout
# tests/README.md uses: a `###` heading naming the vendored file, and a
# fenced `text` block of fields under it. The first block is the one the
# "Reading an entry" prose carries, before any heading has been seen --
# the case that has no name to report and is reported all the same
_README = f"""\
# Vendored test vectors

## Reading an entry

```text
repo    <owner>/<repo>
path    <the path in it>
blob    <git blob SHA-1>
```

## upstream/one

### `tests/at_the_tip.csv`

```text
repo    upstream/one
path    vectors/at_the_tip.csv
commit  {_PINNED} (2026-01-02)
blob    5f1d2c3b4a5968778695a4b3c2d1e0f9a8b7c6d5
pulled  2026-01-03
behind  0
```

### `tests/no_commit.csv`

```text
repo    upstream/one
path    vectors/no_commit.csv
blob    5f1d2c3b4a5968778695a4b3c2d1e0f9a8b7c6d5
behind  0
```

### `tests/one_pin_serves_several.csv`

```text
repo    upstream/one
path    vectors/<name>.csv
commit  {_TIP}
behind  0
```

### `tests/already_behind.csv`

```text
repo    upstream/one
path    vectors/already_behind.csv
commit  {_PINNED}
behind  3 (as of 2026-01-04)
```

### `tests/no_behind_line.csv`

```text
repo    upstream/one
path    vectors/no_behind_line.csv
commit  {_PINNED}
```

### `tests/empty_behind_line.csv`

```text
repo    upstream/one
path    vectors/empty_behind_line.csv
commit  {_PINNED}
behind
```

### `tests/no_block.csv`
"""

_AT_THE_TIP = "`tests/at_the_tip.csv`"
_ENTRY = check.Entry(_AT_THE_TIP, "upstream/one", "vectors/at_the_tip.csv", _PINNED)


class _Run:
    """A `subprocess.run` stand-in that records what it was called with.

    One canned stdout serves every call: the only run whose output the
    script reads back is the `gh` query, and a test that stubs this makes
    at most one of those.
    """

    def __init__(self, stdout: str = "") -> None:
        """Record nothing yet, and answer with `stdout` when called.

        Args:
            stdout: what the stubbed process prints.
        """
        self.calls: list[list[str]] = []
        self.stdout = stdout

    def __call__(self, args: list[str], **_kwargs: Any) -> SimpleNamespace:
        """Record one call.

        Args:
            args: the argument list the script built.
            **_kwargs: whatever it passed beside it, unread here.

        Returns:
            A completed process carrying the canned stdout.
        """
        self.calls.append(args)
        return SimpleNamespace(stdout=self.stdout)


def _no_mismatches(_readme_path: Path) -> tuple[list[str], list[str], int, int]:
    """Stand in for `find_mismatches` where a test is about staleness.

    The sample README names files that exist nowhere, so the real
    comparison would report them missing.

    Args:
        _readme_path: the README, unread.

    Returns:
        Nothing mismatched, nothing skipped, nothing hashed or asked.
    """
    return [], [], 0, 0


def _readme(tmp_path: Path) -> Path:
    """Write the sample README and return its path.

    Args:
        tmp_path: the directory to write it in.

    Returns:
        The path the check is then given on argv.
    """
    path = tmp_path / "README.md"
    path.write_text(_README, encoding="utf-8")
    return path


def test_every_heading_is_either_checked_or_named_as_skipped() -> None:
    """The promise the module docstring makes, over every shape at once.

    A heading in neither list is a pin the report says nothing about,
    and the reason beside each skipped one is what tells a reader whether
    to act: a placeholder path and an entry a human already decided not
    to close are not the same news.
    """
    entries, skipped = check._entries_at_tip(_README)

    assert entries == [_ENTRY]
    assert skipped == [
        # the "Reading an entry" block, above every heading: no name to
        # report, and reported anyway rather than dropped
        " (no commit to check against)",
        "`tests/no_commit.csv` (no commit to check against)",
        "`tests/one_pin_serves_several.csv` (one pin serves several files)",
        "`tests/already_behind.csv` (already documented as behind)",
        "`tests/no_behind_line.csv` (no behind line at all)",
        "`tests/empty_behind_line.csv` (behind line present but empty)",
        "`tests/no_block.csv` (no fenced block)",
    ]


def test_the_date_beside_a_commit_is_not_part_of_it() -> None:
    """A `commit` field carries a parenthesised date in this README."""
    entries, _skipped = check._entries_at_tip(_README)

    assert entries[0].commit == _PINNED
    assert "(" not in entries[0].commit


def test_a_bare_key_not_last_in_its_block_does_not_swallow_the_next_line() -> None:
    r"""The separator is confined to one line, so a bare key's value is empty.

    `\s+` also matches the newline ending a bare key's own line, so a
    `commit` written with no value would let the separator cross into
    `behind`'s own line and capture it whole -- misreading a block that
    is missing its commit as one already documented as behind, a reason
    it never stated (btclib-org/btclib-secp256k1#862). `[ \t]+` cannot
    cross that newline, so the bare key's value is empty and the block
    is read for what it is: no commit to check against.
    """
    readme = (
        "### `tests/bare_commit.csv`\n\n"
        "```text\n"
        "repo    upstream/one\n"
        "path    vectors/bare_commit.csv\n"
        "commit\n"
        "behind  0\n"
        "```\n"
    )

    entries, skipped = check._entries_at_tip(readme)

    assert entries == []
    assert skipped == ["`tests/bare_commit.csv` (no commit to check against)"]


def test_a_block_with_no_behind_line_is_named_apart_from_documented_behind() -> None:
    """No `behind` line is not a decision anybody made.

    So it is not reported as `(already documented as behind)`, which
    names one (btclib-org/btclib-secp256k1#1046).
    """
    readme = (
        "### `tests/no_behind_line.csv`\n\n"
        "```text\n"
        "repo    upstream/one\n"
        "path    vectors/no_behind_line.csv\n"
        f"commit  {_PINNED}\n"
        "```\n"
    )

    entries, skipped = check._entries_at_tip(readme)

    assert entries == []
    assert skipped == ["`tests/no_behind_line.csv` (no behind line at all)"]


@pytest.mark.parametrize("line", ["behind", "behind  ", "behind\t"])
def test_a_behind_line_present_but_empty_is_named_apart_too(line: str) -> None:
    """A `behind` line with no value is neither missing nor a decision.

    The bare key is the shape tests/README.md can actually hold, its
    trailing-whitespace hook stripping the other two down to it.

    Args:
        line: the `behind` line, as written.
    """
    readme = (
        "### `tests/empty_behind_line.csv`\n\n"
        "```text\n"
        "repo    upstream/one\n"
        "path    vectors/empty_behind_line.csv\n"
        f"commit  {_PINNED}\n"
        f"{line}\n"
        "```\n"
    )

    entries, skipped = check._entries_at_tip(readme)

    assert entries == []
    assert skipped == ["`tests/empty_behind_line.csv` (behind line present but empty)"]


def test_a_ref_line_becomes_the_entries_own_ref() -> None:
    """A pin standing on a branch names it; one that does not carries none."""
    readme = (
        "### `tests/on_a_branch.csv`\n\n"
        "```text\n"
        "repo    upstream/one\n"
        "path    vectors/on_a_branch.csv\n"
        "ref     pr-branch\n"
        f"commit  {_PINNED}\n"
        "behind  0\n"
        "```\n"
    )

    entries, _skipped = check._entries_at_tip(readme)

    assert entries == [
        check.Entry(
            "`tests/on_a_branch.csv`",
            "upstream/one",
            "vectors/on_a_branch.csv",
            _PINNED,
            "pr-branch",
        )
    ]
    assert check._entries_at_tip(_README)[0][0].ref is None


def test_the_tip_is_the_one_commit_gh_is_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The query names the path, and the answer's date is the day alone.

    Args:
        monkeypatch: the fixture `subprocess.run` is replaced through.
    """
    run = _Run(
        json.dumps([
            {"sha": _TIP, "commit": {"committer": {"date": "2026-02-03T04:05:06Z"}}}
        ])
    )
    monkeypatch.setattr(check.subprocess, "run", run)

    assert check._latest_commit("upstream/one", "vectors/at_the_tip.csv") == (
        _TIP,
        "2026-02-03",
    )
    args = run.calls[-1]
    assert "repos/upstream/one/commits" in args
    assert "path=vectors/at_the_tip.csv" in args
    assert "per_page=1" in args
    assert not any(arg.startswith("sha=") for arg in args)


def test_a_ref_is_passed_on_as_the_calls_own_sha_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pin standing on a branch asks the API to walk that branch.

    GitHub's "commits touching a path" endpoint resolves against a
    repository's default branch alone unless told otherwise, and `sha`
    is its own name for what to walk instead -- a branch or a tag as
    much as a commit despite the name (btclib-org/btclib-secp256k1#922).

    Args:
        monkeypatch: the fixture `subprocess.run` is replaced through.
    """
    run = _Run(
        json.dumps([
            {"sha": _TIP, "commit": {"committer": {"date": "2026-02-03T04:05:06Z"}}}
        ])
    )
    monkeypatch.setattr(check.subprocess, "run", run)

    check._latest_commit("upstream/one", "vectors/on_a_branch.csv", "pr-branch")

    assert "sha=pr-branch" in run.calls[-1]


def test_a_path_the_branch_walked_never_held_answers_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty list is a path the branch walked never held, not a raise.

    Unpacking one commit out of it would raise, the run would go red and
    no issue would open. A path upstream deleted or renamed away is not
    this case: the listing answers with the commit that removed it, an
    ordinary tip (btclib-org/bitcoin-node-tests#150).

    Args:
        monkeypatch: the fixture `subprocess.run` is replaced through.
    """
    monkeypatch.setattr(check.subprocess, "run", _Run("[]"))

    assert check._latest_commit("upstream/one", "vectors/gone.csv") is None


def test_find_drift_threads_the_entries_ref_into_the_lookup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The pin's own `ref` decides which branch is asked, not the caller.

    Args:
        monkeypatch: the fixture the tip lookup is replaced through.
        tmp_path: where the sample README is written.
    """
    readme = tmp_path / "README.md"
    readme.write_text(
        "### `tests/on_a_branch.csv`\n\n"
        "```text\n"
        "repo    upstream/one\n"
        "path    vectors/on_a_branch.csv\n"
        "ref     pr-branch\n"
        f"commit  {_PINNED}\n"
        "behind  0\n"
        "```\n",
        encoding="utf-8",
    )
    seen: list[tuple[str, str, str | None]] = []

    def _stub(repo: str, path: str, ref: str | None = None) -> tuple[str, str]:
        seen.append((repo, path, ref))
        return _PINNED, "2026-01-02"

    monkeypatch.setattr(check, "_latest_commit", _stub)

    check.find_drift(readme)

    assert seen == [("upstream/one", "vectors/on_a_branch.csv", "pr-branch")]


def test_a_pin_still_at_the_tip_is_no_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The state the README claims, and the only one that reports nothing.

    Args:
        monkeypatch: the fixture the tip lookup is replaced through.
        tmp_path: where the sample README is written.
    """
    monkeypatch.setattr(
        check, "_latest_commit", lambda _repo, _path, _ref=None: (_PINNED, "2026-01-02")
    )

    drifted, skipped = check.find_drift(_readme(tmp_path))

    assert drifted == []
    assert len(skipped) == len(check._entries_at_tip(_README)[1])


def test_a_pin_behind_the_tip_is_drift_naming_the_tip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Upstream moved, and the report says what it moved to.

    Args:
        monkeypatch: the fixture the tip lookup is replaced through.
        tmp_path: where the sample README is written.
    """
    monkeypatch.setattr(
        check, "_latest_commit", lambda _repo, _path, _ref=None: (_TIP, "2026-02-03")
    )

    drifted, _skipped = check.find_drift(_readme(tmp_path))

    assert drifted == [check.Drift(_ENTRY, _TIP, "2026-02-03")]
    assert not drifted[0].has_no_tip


def test_a_path_with_no_tip_is_drift_with_no_tip_to_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The empty tip is what says so, and reading it has one name.

    Args:
        monkeypatch: the fixture the tip lookup is replaced through.
        tmp_path: where the sample README is written.
    """
    monkeypatch.setattr(check, "_latest_commit", lambda _repo, _path, _ref=None: None)

    drifted, _skipped = check.find_drift(_readme(tmp_path))

    assert drifted == [check.Drift(_ENTRY, "", "")]
    assert drifted[0].has_no_tip


def test_a_removing_commit_is_drift_that_may_be_a_removal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A deleted or renamed path's tip is the commit that removed it.

    GitHub's "commits touching a path" listing answers a path deleted
    or renamed away with the commit that removed it, which is not the
    pin: ordinary drift, reported as a change that may in fact be a
    removal rather than as `has_no_tip`
    (btclib-org/bitcoin-node-tests#150).

    Args:
        monkeypatch: the fixture the tip lookup is replaced through.
        tmp_path: where the sample README is written.
    """
    monkeypatch.setattr(
        check, "_latest_commit", lambda _repo, _path, _ref=None: (_TIP, "2026-02-03")
    )

    drifted, _skipped = check.find_drift(_readme(tmp_path))

    assert drifted == [check.Drift(_ENTRY, _TIP, "2026-02-03")]
    assert not drifted[0].has_no_tip
    body = check._issue_body(_readme(tmp_path), drifted, [])
    assert (
        f"the latest commit touching `{_ENTRY.path}` is now `{_TIP}`"
        f" (2026-02-03), `{_ENTRY.repo}` -- which may have deleted or"
        " renamed the file rather than changed it"
    ) in body


def test_the_branch_named_in_a_no_tip_report_is_the_entries_own_ref(
    tmp_path: Path,
) -> None:
    """No `ref` names the default branch; a `ref` names itself.

    Args:
        tmp_path: where the sample README is written, for the path the
            body opens with.
    """
    on_a_branch = check.Entry(
        "`tests/on_a_branch.csv`",
        "upstream/one",
        "vectors/on_a_branch.csv",
        _PINNED,
        "pr-branch",
    )
    body = check._issue_body(
        _readme(tmp_path),
        [check.Drift(_ENTRY, "", ""), check.Drift(on_a_branch, "", "")],
        [],
    )

    assert "no commit on the default branch of" in body
    assert "no commit on `pr-branch` of" in body


def test_the_issue_body_tells_the_two_kinds_of_drift_apart(tmp_path: Path) -> None:
    """A pin behind its path reads differently from a path that is gone.

    Args:
        tmp_path: where the sample README is written, for the path the
            body opens with.
    """
    body = check._issue_body(
        _readme(tmp_path),
        [check.Drift(_ENTRY, _TIP, "2026-02-03"), check.Drift(_ENTRY, "", "")],
        ["`tests/no_block.csv` (no fenced block)"],
    )

    assert _TIP[:12] in body
    assert "2026-02-03" in body
    assert "may have deleted or renamed the file rather than changed it" in body
    assert "a path that branch never held" in body
    assert "Not checked by this run" in body
    assert "`tests/no_block.csv` (no fenced block)" in body


def test_a_body_with_nothing_skipped_opens_no_empty_list(tmp_path: Path) -> None:
    """The heading appears with the list it introduces, or not at all.

    Args:
        tmp_path: where the sample README is written.
    """
    body = check._issue_body(_readme(tmp_path), [check.Drift(_ENTRY, _TIP, "x")], [])

    assert "Not checked by this run" not in body


def test_the_tracking_issue_is_looked_for_by_its_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One open issue is reused; none means there is one to open.

    The title asked for is a title no caller in this tree passes, which
    is what tells a search built from the argument apart from one built
    from a constant that happens to match.

    Args:
        monkeypatch: the fixture `subprocess.run` is replaced through.
    """
    run = _Run('[{"number": 7}]')
    monkeypatch.setattr(check.subprocess, "run", run)

    assert check._open_issue_number("A title of the caller's own") == "7"
    assert '"A title of the caller\'s own" in:title' in run.calls[-1]

    monkeypatch.setattr(check.subprocess, "run", _Run("[]"))

    assert check._open_issue_number("A title of the caller's own") is None


@pytest.mark.parametrize(
    "open_issues, drifted, expected",
    [
        ("[]", [], None),
        ('[{"number": 7}]', [], "close"),
        ("[]", [check.Drift(_ENTRY, _TIP, "2026-02-03")], "create"),
        ('[{"number": 7}]', [check.Drift(_ENTRY, _TIP, "2026-02-03")], "edit"),
    ],
)
def test_the_report_is_one_gh_command_per_outcome(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    open_issues: str,
    drifted: list[Any],
    expected: str | None,
) -> None:
    """Drift and an open issue are two questions, so there are four answers.

    Closing a clean run's issue is the one that would go unnoticed if it
    stopped happening: the report would then be permanent, and a stale
    issue is read as drift nobody has got to.

    Args:
        monkeypatch: the fixture `subprocess.run` is replaced through.
        tmp_path: where the sample README is written.
        open_issues: what `gh issue list` answers.
        drifted: what the run found.
        expected: the `gh issue` subcommand that has to follow, or None
            where the run has nothing to say.
    """
    run = _Run(open_issues)
    monkeypatch.setattr(check.subprocess, "run", run)

    check.report(_readme(tmp_path), "Vendored vectors behind upstream", drifted, [])

    if expected is None:
        assert run.calls == [run.calls[0]], "only the question was asked"
        assert "list" in run.calls[0]
    else:
        assert run.calls[-1][1:3] == ["issue", expected]


@pytest.mark.parametrize("argv", [[], ["one.md"], ["one.md", "a title", "extra"]])
def test_a_run_that_names_no_one_readme_says_how_to_call_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    """Two exit codes and one message: a human is the only caller here.

    The workflow passes both every time, so this is reachable by hand
    alone -- and an IndexError naming a list is not an answer.

    Args:
        monkeypatch: the fixture `sys.argv` is set through.
        capsys: the captured streams.
        argv: what a mistaken call passes.
    """
    monkeypatch.setattr(check.sys, "argv", ["check_vendored_vectors.py", *argv])

    assert check.main() == 2
    assert "usage:" in capsys.readouterr().err


def test_a_dry_run_prints_the_finding_and_touches_no_issue(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """What the pull_request trigger passes, and what it buys.

    A change to this script is exercised by the workflow that runs it,
    and whatever tracking issue is open at the time is not edited as a
    side effect of that test.

    Args:
        monkeypatch: the fixture the argv and the tip lookup are set
            through.
        tmp_path: where the sample README is written.
        capsys: the captured streams.
    """
    reported: list[object] = []
    monkeypatch.setattr(check, "find_mismatches", _no_mismatches)
    monkeypatch.setattr(
        check, "_latest_commit", lambda _repo, _path, _ref=None: (_TIP, "2026-02-03")
    )
    monkeypatch.setattr(check, "report", lambda *args: reported.append(args))
    monkeypatch.setattr(
        check.sys,
        "argv",
        [
            "check_vendored_vectors.py",
            str(_readme(tmp_path)),
            "Vendored vectors behind upstream",
            "--dry-run",
        ],
    )

    assert check.main() == 0
    out = capsys.readouterr().out
    assert f"BEHIND: {_AT_THE_TIP}" in out
    assert _TIP[:12] in out
    assert "SKIPPED: `tests/no_block.csv` (no fenced block)" in out
    assert reported == []


def test_a_path_with_no_tip_is_printed_as_no_commit_rather_than_as_behind(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The log says which drift it is, as the issue body does.

    Args:
        monkeypatch: the fixture the argv and the tip lookup are set
            through.
        tmp_path: where the sample README is written.
        capsys: the captured streams.
    """
    monkeypatch.setattr(check, "find_mismatches", _no_mismatches)
    monkeypatch.setattr(check, "_latest_commit", lambda _repo, _path, _ref=None: None)
    monkeypatch.setattr(check, "report", lambda *_args: None)
    monkeypatch.setattr(
        check.sys,
        "argv",
        [
            "check_vendored_vectors.py",
            str(_readme(tmp_path)),
            "Vendored vectors behind upstream",
            "--dry-run",
        ],
    )

    assert check.main() == 0
    assert f"NO COMMIT: {_AT_THE_TIP}" in capsys.readouterr().out


# a pin and a tip alike in a short prefix and apart past it, the pair
# btclib-org/.github#1343 was filed on
_PINNED_ALIKE = "9b37d42b23be07ee3a37eae4bcbd52c8ba36ee40"
_TIP_ALIKE = "9b37d42b23be096cc4cfb457f1022e443102b650"


def test_a_pin_and_a_tip_alike_in_a_prefix_print_as_two_shas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The drift line and the body name both commits whole, never a tie.

    Args:
        monkeypatch: the fixture the argv and the tip lookup are set
            through.
        tmp_path: where the sample README is written.
        capsys: the captured streams.
    """
    assert _PINNED_ALIKE[:12] == _TIP_ALIKE[:12]
    readme = tmp_path / "README.md"
    readme.write_text(_README.replace(_PINNED, _PINNED_ALIKE), encoding="utf-8")
    monkeypatch.setattr(check, "find_mismatches", _no_mismatches)
    monkeypatch.setattr(
        check,
        "_latest_commit",
        lambda _repo, _path, _ref=None: (_TIP_ALIKE, "2026-09-11"),
    )
    monkeypatch.setattr(check, "report", lambda *_args: None)
    monkeypatch.setattr(
        check.sys,
        "argv",
        [
            "check_vendored_vectors.py",
            str(readme),
            "Vendored vectors behind upstream",
            "--dry-run",
        ],
    )

    assert check.main() == 0
    out = capsys.readouterr().out
    assert (
        f"pinned to {_PINNED_ALIKE}, latest commit touching it is"
        f" {_TIP_ALIKE} (2026-09-11)" in out
    )

    drifted, skipped = check.find_drift(readme)
    body = check._issue_body(readme, drifted, skipped)
    assert f"`{_PINNED_ALIKE}`" in body
    assert f"`{_TIP_ALIKE}` (2026-09-11)" in body


def test_a_clean_run_says_so_and_still_reports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing found is the run that closes an issue, so it reports too.

    Args:
        monkeypatch: the fixture the argv and the tip lookup are set
            through.
        tmp_path: where the sample README is written.
        capsys: the captured streams.
    """
    reported: list[tuple[object, ...]] = []
    monkeypatch.setattr(check, "find_mismatches", _no_mismatches)
    monkeypatch.setattr(
        check, "_latest_commit", lambda _repo, _path, _ref=None: (_PINNED, "2026-01-02")
    )
    monkeypatch.setattr(check, "report", lambda *args: reported.append(args))
    readme = _readme(tmp_path)
    monkeypatch.setattr(
        check.sys,
        "argv",
        [
            "check_vendored_vectors.py",
            str(readme),
            "Vendored vectors behind upstream",
        ],
    )

    assert check.main() == 0
    assert "Every checked pin is still at upstream's tip." in capsys.readouterr().out
    assert len(reported) == 1
    # the ledger and the title, in that order: `main` builds this call
    # from two positionals a caller can hand over the wrong way round,
    # and every other assertion here would pass if it did
    assert reported[0][:2] == (readme, "Vendored vectors behind upstream")


def test_the_entry_point_guard_runs_the_check_as___main__(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The guard itself, and not only the function it calls.

    `runpy.run_path` executes the file again in this interpreter with
    `__name__` bound to `"__main__"`, which is what puts the last two
    lines of the script under test; a subprocess would run them in an
    interpreter this suite measures nothing in. The module the second
    execution builds is its own, so what is stubbed here is
    `subprocess.run` on the standard library module both of them import.

    Args:
        monkeypatch: the fixture the stub and the argv are set through.
        tmp_path: where the sample README is written.
        capsys: the captured streams.
    """
    # no blob line, so the byte comparison has nothing to hash and asks
    # upstream nothing: the one canned answer below is the commit list
    readme = tmp_path / "README.md"
    readme.write_text(re.sub(r"(?m)^blob .*\n", "", _README), encoding="utf-8")
    monkeypatch.setattr(
        check.subprocess,
        "run",
        _Run(
            json.dumps([
                {
                    "sha": _PINNED,
                    "commit": {"committer": {"date": "2026-01-02T00:00:00Z"}},
                }
            ])
        ),
    )
    monkeypatch.setattr(
        check.sys,
        "argv",
        [
            "check_vendored_vectors.py",
            str(readme),
            "Vendored vectors behind upstream",
            "--dry-run",
        ],
    )

    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(_SCRIPT), run_name="__main__")

    assert raised.value.code == 0
    assert "Every checked pin is still at upstream's tip." in capsys.readouterr().out


_ROOT = Path(__file__).parents[1]
_COMMIT = "c0ffee0"
_UPSTREAM_BLOB = "1" * 40


def _blob_of(data: bytes) -> str:
    """Return a git blob SHA-1, computed apart from the script's own.

    Args:
        data: the file's bytes.

    Returns:
        The SHA-1 of `blob <length>`, a NUL and the bytes.
    """
    header = b"blob %d\0" % len(data)
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


class _Gh:
    """A `subprocess.run` stand-in answering the `gh` calls of the byte half.

    The trees API answers from `trees`, keyed on the repository and the
    `<commit>:<directory>` the script asks for; the commits API from
    `commits`; `gh issue list` finds the issue `open_issue` names, and
    every other `gh issue` call answers nothing.
    """

    def __init__(self) -> None:
        """Start with no tree, no commit and no open issue."""
        self.trees: dict[tuple[str, str], dict[str, str]] = {}
        self.commits: dict[tuple[str, str], tuple[str, str]] = {}
        self.open_issue: int | None = None
        self.fail_trees = False
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], **_kwargs: Any) -> SimpleNamespace:
        """Record the call and answer it as the `gh` sub-command would.

        Args:
            argv: the argument list the script built.
            **_kwargs: whatever it passed beside it, unread here.

        Returns:
            A completed process carrying the canned stdout.

        Raises:
            CalledProcessError: for a trees call, once `fail_trees` is set.
        """
        self.calls.append(list(argv))
        if argv[1] == "api":
            url = argv[4].removeprefix("repos/")
            if "/git/trees/" in url:
                if self.fail_trees:
                    raise check.subprocess.CalledProcessError(
                        1, argv, stderr="HTTP 404\n"
                    )
                repo, _, tree = url.partition("/git/trees/")
                items = [
                    {"path": name, "sha": sha}
                    for name, sha in self.trees[repo, tree].items()
                ]
                return SimpleNamespace(stdout=json.dumps({"tree": items}))
            sha, date = self.commits[url.removesuffix("/commits"), argv[6][5:]]
            commit = {"sha": sha, "commit": {"committer": {"date": date}}}
            return SimpleNamespace(stdout=json.dumps([commit]))
        if argv[2] == "list":
            issues = [{"number": self.open_issue}] if self.open_issue else []
            return SimpleNamespace(stdout=json.dumps(issues))
        return SimpleNamespace(stdout="")


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> _Gh:
    """Replace `subprocess.run` with a `_Gh`.

    Args:
        monkeypatch: the fixture `subprocess.run` is replaced through.

    Returns:
        The stand-in, for the test to load and to read back.
    """
    fake = _Gh()
    monkeypatch.setattr(check.subprocess, "run", fake)
    return fake


def _block(heading: str, **fields: str) -> str:
    """Return one README entry: a heading and its fenced block.

    Args:
        heading: the `###` heading.
        **fields: the block's fields, in order.

    Returns:
        The entry, laid out as `tests/README.md` lays one out.
    """
    lines = "\n".join(f"{key}  {value}" for key, value in fields.items())
    return f"### {heading}\n\n```text\n{lines}\n```\n"


def _vendored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gh: _Gh,
    *,
    data: bytes = b"[1]\n",
    **fields: str,
) -> Path:
    """Write `tests/f.json` and a README entry for it, and return the README.

    The entry records the blob of `data`, as `blob` unless a field says
    otherwise, and upstream's tree at the commit holds the same blob.

    Args:
        tmp_path: where the file and the README are written, and the
            working directory the script's relative path is read from.
        monkeypatch: the fixture the working directory is set through.
        gh: the stand-in whose tree is loaded.
        data: the file's bytes.
        **fields: fields of the entry, overriding the defaults.

    Returns:
        The README's path.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "f.json").write_bytes(data)
    recorded = {
        "repo": "r",
        "path": "up/f.json",
        "commit": f"{_COMMIT}  2026-01-01",
        "blob": _blob_of(data),
        "behind": "0",
    } | fields
    gh.trees["r", f"{_COMMIT}:up"] = {"f.json": recorded.get("blob", "")}
    readme = tmp_path / "README.md"
    readme.write_text(_block("`tests/f.json`", **recorded), encoding="utf-8")
    return readme


def test_git_blob_is_what_git_hash_object_prints(tmp_path: Path) -> None:
    r"""The empty blob and `hello\n` are the two every git user has seen.

    Args:
        tmp_path: where the two files are written.
    """
    empty = tmp_path / "empty"
    empty.write_bytes(b"")
    hello = tmp_path / "hello"
    hello.write_bytes(b"hello\n")

    assert check._git_blob(empty) == (
        "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"  # pragma: allowlist secret
    )
    assert check._git_blob(hello) == (
        "ce013625030ba8dba906f756967f9e9ca394464a"  # pragma: allowlist secret
    )


def test_a_file_matching_its_blob_and_upstream_s_is_clean(
    gh: _Gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both comparisons pass, and both ran.

    Args:
        gh: the `gh` stand-in.
        tmp_path: where the file and the README are written.
        monkeypatch: the fixture the working directory is set through.
    """
    readme = _vendored(tmp_path, monkeypatch, gh)

    assert check.find_mismatches(readme) == ([], [], 1, 1)
    assert [call[4] for call in gh.calls] == [f"repos/r/git/trees/{_COMMIT}:up"]


def test_a_tampered_file_is_a_mismatch_naming_it(
    gh: _Gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A byte changed here, with the README and upstream untouched, fails.

    Args:
        gh: the `gh` stand-in.
        tmp_path: where the file and the README are written.
        monkeypatch: the fixture the working directory is set through.
    """
    readme = _vendored(tmp_path, monkeypatch, gh)
    (tmp_path / "tests" / "f.json").write_bytes(b"[2]\n")

    (mismatch,) = check.find_mismatches(readme)[0]

    assert mismatch.startswith("tests/f.json: its bytes hash to blob")
    assert _blob_of(b"[2]\n") in mismatch
    assert _blob_of(b"[1]\n") in mismatch


def test_a_file_missing_from_the_tree_is_a_mismatch(
    gh: _Gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A README naming a file that is not there fails, rather than skipping.

    Args:
        gh: the `gh` stand-in.
        tmp_path: where the file and the README are written.
        monkeypatch: the fixture the working directory is set through.
    """
    readme = _vendored(tmp_path, monkeypatch, gh)
    (tmp_path / "tests" / "f.json").unlink()

    mismatches, _skipped, hashed, _asked = check.find_mismatches(readme)

    assert mismatches == ["tests/f.json: the README names it and it is not here"]
    assert hashed == 0


def test_a_blob_that_is_not_upstream_s_at_the_commit_is_a_mismatch(
    gh: _Gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The file matches the README and the README is not what upstream holds.

    Args:
        gh: the `gh` stand-in.
        tmp_path: where the file and the README are written.
        monkeypatch: the fixture the working directory is set through.
    """
    readme = _vendored(tmp_path, monkeypatch, gh)
    gh.trees["r", f"{_COMMIT}:up"] = {"f.json": _UPSTREAM_BLOB}

    (mismatch,) = check.find_mismatches(readme)[0]

    assert mismatch.startswith("tests/f.json: r at c0ffee0 holds up/f.json as blob")
    assert _UPSTREAM_BLOB in mismatch


def test_a_path_absent_at_the_commit_is_a_mismatch(
    gh: _Gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Upstream's tree holding no such name, only another, is a mismatch.

    The blob it names is `None`.

    Args:
        gh: the `gh` stand-in.
        tmp_path: where the file and the README are written.
        monkeypatch: the fixture the working directory is set through.
    """
    readme = _vendored(tmp_path, monkeypatch, gh)
    gh.trees["r", f"{_COMMIT}:up"] = {"other.json": _UPSTREAM_BLOB}

    (mismatch,) = check.find_mismatches(readme)[0]

    assert "as blob None" in mismatch


def test_a_path_at_the_root_asks_for_the_commit_itself(
    gh: _Gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no directory in the path the tree asked for is `<commit>`.

    Args:
        gh: the `gh` stand-in.
        tmp_path: where the file and the README are written.
        monkeypatch: the fixture the working directory is set through.
    """
    readme = _vendored(tmp_path, monkeypatch, gh, path="f.json")
    gh.trees["r", _COMMIT] = {"f.json": _blob_of(b"[1]\n")}

    assert check.find_mismatches(readme)[0] == []
    assert gh.calls[-1][4] == f"repos/r/git/trees/{_COMMIT}"


def test_ours_is_what_the_file_is_held_to_and_blob_what_upstream_is(
    gh: _Gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file differing from upstream in whitespace is clean given `ours`.

    Args:
        gh: the `gh` stand-in.
        tmp_path: where the file and the README are written.
        monkeypatch: the fixture the working directory is set through.
    """
    readme = _vendored(
        tmp_path, monkeypatch, gh, blob=_UPSTREAM_BLOB, ours=_blob_of(b"[1]\n")
    )

    assert check.find_mismatches(readme)[0] == []

    (tmp_path / "tests" / "f.json").write_bytes(b"[2]\n")
    (mismatch,) = check.find_mismatches(readme)[0]

    assert _blob_of(b"[1]\n") in mismatch


def test_an_entry_with_ours_and_no_blob_asks_upstream_nothing(
    gh: _Gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file with no upstream blob to name is hashed alone.

    Args:
        gh: the `gh` stand-in.
        tmp_path: where the file and the README are written.
        monkeypatch: the fixture the working directory is set through.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "f.txt").write_bytes(b"x\n")
    readme = tmp_path / "README.md"
    readme.write_text(
        _block(
            "`f.txt`",
            repo="r",
            path="src",
            commit="c0ffee0  2026-01-01",
            ours=_blob_of(b"x\n"),
        ),
        encoding="utf-8",
    )

    assert check.find_mismatches(readme) == ([], [], 1, 0)
    assert not gh.calls


def test_an_entry_naming_a_file_with_no_blob_is_named_as_skipped(
    gh: _Gh, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither `blob` nor `ours` leaves nothing to compare, and says so.

    A heading that is no one file's path, or an entry with no commit, is
    not this comparison's to name: the staleness check lists those.

    Args:
        gh: the `gh` stand-in.
        tmp_path: where the README is written.
        monkeypatch: the fixture the working directory is set through.
    """
    monkeypatch.chdir(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        _block("`f.json`", repo="r", path="f.json", commit="c0ffee0  2026-01-01")
        + _block("`dir/*.bin`", repo="r", path="d", commit="c0ffee0", blob="a")
        + _block("not a path", repo="r", path="f.json", commit="c0ffee0", blob="a")
        + _block("`g.json`", pulled="2026-01-01", blob="a"),
        encoding="utf-8",
    )

    assert check.find_mismatches(readme) == (
        [],
        ["`f.json` (no blob or ours line)"],
        0,
        0,
    )
    assert not gh.calls


def test_a_failed_upstream_call_is_a_mismatch_and_the_issue_is_still_dealt_with(
    gh: _Gh,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A trees-API error names the file and does not skip `report`.

    Args:
        gh: the `gh` stand-in.
        tmp_path: where the file and the README are written.
        monkeypatch: the fixture the working directory and argv are set
            through.
        capsys: the captured streams.
    """
    readme = _vendored(tmp_path, monkeypatch, gh)
    gh.commits["r", "up/f.json"] = ("new0000", "2026-01-01T00:00:00Z")
    gh.fail_trees = True
    monkeypatch.setattr(check.sys, "argv", ["prog", str(readme), "A title"])

    assert check.main() == 1

    out = capsys.readouterr().out
    assert "MISMATCH: tests/f.json: asking r for up/f.json at c0ffee0 failed" in out
    assert "HTTP 404" in out
    assert [c[2] for c in gh.calls if c[1] == "issue"] == ["list", "create"]


def test_main_exits_1_on_a_mismatch_and_still_reports_drift(
    gh: _Gh,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A tampered file fails the run, after the issue has been dealt with.

    Args:
        gh: the `gh` stand-in.
        tmp_path: where the file and the README are written.
        monkeypatch: the fixture the working directory and argv are set
            through.
        capsys: the captured streams.
    """
    readme = _vendored(tmp_path, monkeypatch, gh)
    (tmp_path / "tests" / "f.json").write_bytes(b"[2]\n")
    gh.commits["r", "up/f.json"] = (_COMMIT, "2026-01-01T00:00:00Z")
    gh.open_issue = 5
    monkeypatch.setattr(check.sys, "argv", ["prog", str(readme), "A title"])

    assert check.main() == 1

    out = capsys.readouterr().out
    assert "MISMATCH: tests/f.json: its bytes hash to blob" in out
    assert "Hashed 1 files and asked upstream for 1 blobs: 1 mismatches." in out
    assert [c[2] for c in gh.calls if c[1] == "issue"] == ["list", "close"]


def test_main_exits_0_and_counts_what_it_compared(
    gh: _Gh,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A clean run says how many files and blobs it read.

    Args:
        gh: the `gh` stand-in.
        tmp_path: where the file and the README are written.
        monkeypatch: the fixture the working directory and argv are set
            through.
        capsys: the captured streams.
    """
    readme = _vendored(tmp_path, monkeypatch, gh)
    gh.commits["r", "up/f.json"] = (_COMMIT, "2026-01-01T00:00:00Z")
    monkeypatch.setattr(
        check.sys, "argv", ["prog", str(readme), "A title", "--dry-run"]
    )

    assert check.main() == 0

    out = capsys.readouterr().out
    assert "Hashed 1 files and asked upstream for 1 blobs: 0 mismatches." in out
    assert "MISMATCH" not in out


def test_every_vendored_file_the_readme_names_is_the_blob_it_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The local half of the weekly comparison, over the real README, offline.

    The first assertion is what says the parse still finds the pins at
    all, a parser that matched nothing passing every line after it.

    Args:
        monkeypatch: the fixture the working directory is set through.
    """
    monkeypatch.chdir(_ROOT)
    pins, skipped = check._pins((_ROOT / "tests" / "README.md").read_text("utf-8"))

    assert len(pins) > 5
    assert skipped == []
    wrong = [
        pin.local for pin in pins if check._git_blob(Path(pin.local)) != pin.expected
    ]
    assert wrong == []


def test_every_file_the_readme_names_is_marked_minus_text() -> None:
    """A file the README hashes is checked out byte for byte.

    Without `-text`, a checkout with `core.autocrlf=true` converts the
    file and the hash above no longer holds. The lines are read from
    `.gitattributes` rather than asked of git, which a copy of the tree
    without a `.git` cannot answer.
    """
    pins, _skipped = check._pins((_ROOT / "tests" / "README.md").read_text("utf-8"))
    marked = (_ROOT / ".gitattributes").read_text("utf-8").splitlines()

    assert pins
    assert [pin.local for pin in pins if f"{pin.local} -text" not in marked] == []
