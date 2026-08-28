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

The script is loaded by path, `.github/scripts` being no package, and
once: `monkeypatch` undoes what each test does to it.
"""

from __future__ import annotations

import importlib.util
import json
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
        "`tests/no_block.csv` (no fenced block)",
    ]


def test_the_date_beside_a_commit_is_not_part_of_it() -> None:
    """A `commit` field carries a parenthesised date in this README."""
    entries, _skipped = check._entries_at_tip(_README)

    assert entries[0].commit == _PINNED
    assert "(" not in entries[0].commit


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


def test_a_path_upstream_has_no_commit_for_answers_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty list is a renamed or deleted path, not an empty answer.

    Unpacking one commit out of it would raise, the run would go red and
    no issue would open -- for the drift that most needs one.

    Args:
        monkeypatch: the fixture `subprocess.run` is replaced through.
    """
    monkeypatch.setattr(check.subprocess, "run", _Run("[]"))

    assert check._latest_commit("upstream/one", "vectors/gone.csv") is None


def test_a_pin_still_at_the_tip_is_no_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The state the README claims, and the only one that reports nothing.

    Args:
        monkeypatch: the fixture the tip lookup is replaced through.
        tmp_path: where the sample README is written.
    """
    monkeypatch.setattr(
        check, "_latest_commit", lambda _repo, _path: (_PINNED, "2026-01-02")
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
        check, "_latest_commit", lambda _repo, _path: (_TIP, "2026-02-03")
    )

    drifted, _skipped = check.find_drift(_readme(tmp_path))

    assert drifted == [check.Drift(_ENTRY, _TIP, "2026-02-03")]
    assert not drifted[0].path_is_gone


def test_a_path_that_is_gone_is_drift_with_no_tip_to_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The empty tip is what says so, and reading it has one name.

    Args:
        monkeypatch: the fixture the tip lookup is replaced through.
        tmp_path: where the sample README is written.
    """
    monkeypatch.setattr(check, "_latest_commit", lambda _repo, _path: None)

    drifted, _skipped = check.find_drift(_readme(tmp_path))

    assert drifted == [check.Drift(_ENTRY, "", "")]
    assert drifted[0].path_is_gone


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
    assert "renamed, moved or deleted upstream" in body
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

    Args:
        monkeypatch: the fixture `subprocess.run` is replaced through.
    """
    run = _Run('[{"number": 7}]')
    monkeypatch.setattr(check.subprocess, "run", run)

    assert check._open_issue_number() == "7"
    assert f'"{check._ISSUE_TITLE}" in:title' in run.calls[-1]

    monkeypatch.setattr(check.subprocess, "run", _Run("[]"))

    assert check._open_issue_number() is None


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

    check.report(_readme(tmp_path), drifted, [])

    if expected is None:
        assert run.calls == [run.calls[0]], "only the question was asked"
        assert "list" in run.calls[0]
    else:
        assert run.calls[-1][1:3] == ["issue", expected]


@pytest.mark.parametrize("argv", [[], ["one.md", "two.md"]])
def test_a_run_that_names_no_one_readme_says_how_to_call_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    """Two exit codes and one message: a human is the only caller here.

    The workflow passes the path every time, so this is reachable by
    hand alone -- and an IndexError naming a list is not an answer.

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
    monkeypatch.setattr(
        check, "_latest_commit", lambda _repo, _path: (_TIP, "2026-02-03")
    )
    monkeypatch.setattr(check, "report", lambda *args: reported.append(args))
    monkeypatch.setattr(
        check.sys,
        "argv",
        ["check_vendored_vectors.py", str(_readme(tmp_path)), "--dry-run"],
    )

    assert check.main() == 0
    out = capsys.readouterr().out
    assert f"BEHIND: {_AT_THE_TIP}" in out
    assert _TIP[:12] in out
    assert "SKIPPED: `tests/no_block.csv` (no fenced block)" in out
    assert reported == []


def test_a_gone_path_is_printed_as_gone_rather_than_as_behind(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The log says which drift it is, as the issue body does.

    Args:
        monkeypatch: the fixture the argv and the tip lookup are set
            through.
        tmp_path: where the sample README is written.
        capsys: the captured streams.
    """
    monkeypatch.setattr(check, "_latest_commit", lambda _repo, _path: None)
    monkeypatch.setattr(check, "report", lambda *_args: None)
    monkeypatch.setattr(
        check.sys,
        "argv",
        ["check_vendored_vectors.py", str(_readme(tmp_path)), "--dry-run"],
    )

    assert check.main() == 0
    assert f"GONE: {_AT_THE_TIP}" in capsys.readouterr().out


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
    reported: list[object] = []
    monkeypatch.setattr(
        check, "_latest_commit", lambda _repo, _path: (_PINNED, "2026-01-02")
    )
    monkeypatch.setattr(check, "report", lambda *args: reported.append(args))
    monkeypatch.setattr(
        check.sys, "argv", ["check_vendored_vectors.py", str(_readme(tmp_path))]
    )

    assert check.main() == 0
    assert "Every checked pin is still at upstream's tip." in capsys.readouterr().out
    assert len(reported) == 1


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
        ["check_vendored_vectors.py", str(_readme(tmp_path)), "--dry-run"],
    )

    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(_SCRIPT), run_name="__main__")

    assert raised.value.code == 0
    assert "Every checked pin is still at upstream's tip." in capsys.readouterr().out
