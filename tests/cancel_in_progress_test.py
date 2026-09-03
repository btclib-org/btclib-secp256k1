# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""A merged pull request does not cancel the run that measures it.

A `closed` pull request event lands in the concurrency group of the pull
request it closes, so `cancel-in-progress: true` there kills whatever is
still in flight -- including the run measuring the commit that was just
merged (#523). What decides whether that costs anything is the workflow's
own `push` trigger on `main`: with one, the merge commit gets a run of
its own and the cancelled run is superseded rather than lost; without
one, nothing reads what landed until the next schedule (#571).

The rule is therefore a relation between two keys rather than a property
of either, which is why no line of a workflow can carry it and why the
line hooks do not: `yamllint`, `actionlint` and `zizmor` each pass on a
bare `true` whichever trigger sits above it. A workflow written by
copying a neighbour takes the neighbour's value, and this is what turns
that copy red.

What is held is that the value is not a bare `true`, not that some other
value is right. Whether a given expression is false on a merged close is
not decidable by reading it, and a check claiming to decide it would be
one that fails on correct workflows -- which is a check somebody
eventually deletes. `true` is what a copy supplies, and it is the whole
of what #523 names.

Nothing marks a workflow exempt, and the exception that leaves room for
is a real one: what a cancelled run costs is whatever that run was going
to say, so a workflow answering a question about the pull request rather
than measuring the commit loses nothing when the merge cancels it. Such
a workflow edits this module, which is a reviewed diff carrying the
reason, where a marker in the workflow would be one more line a copy
brings along -- this defect one level up.

`cancel-in-progress` is read wherever it appears rather than in the
top-level `concurrency:` block alone: GitHub accepts the key on a job's
own `concurrency:` block too, and nothing here assumes a workflow keeps
its group at one level rather than the other. No workflow in this tree
does that today -- `claude-review.yml` moved its own group from the
review job to the workflow (#593), which is what lets the closed event
reach it before either job's own `if` is read, rather than leave that
reliant on whether a job-level group ever claims anything for a job an
`if` skips, a question #593 leaves open.

Read with a regex rather than parsed, for the reason
`interpreters_test.py` gives: a workflow is yaml, and the `test` group
the suite runs under carries no parser for it.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).parents[1]

# comment lines, dropped before anything is asked of a file: the
# reasoning at these keys quotes the very values read below, and prose
# about a trigger is not a trigger
_COMMENT = re.compile(r"^ *#.*\n", re.MULTILINE)
# the `on:` block, and the first line at column zero after it --
# `permissions:` or `jobs:` -- which is where it ends
_ON = re.compile(r"^on:\n", re.MULTILINE)
_TOP_LEVEL = re.compile(r"^\S", re.MULTILINE)
# a trigger key: two spaces of indent, a name, and nothing after the
# colon. Every deeper line of a trigger's own body carries either more
# indent or a value, so this matches the keys and only them
_TRIGGER = re.compile(r"^  (?P<name>[\w-]+):$", re.MULTILINE)
# the pull request trigger's `types:` list, read for the one type whose
# event is delivered after the head commit stopped being what a run
# measures
_CLOSED = re.compile(r"^ +types: \[[^\]]*\bclosed\b[^\]]*\]$", re.MULTILINE)
# and the push trigger's `branches:` list, read for the branch a merge
# lands on: a push trigger restricted to tags runs on no merge commit,
# so the key alone would exempt a workflow that has no second reading
_MAIN = re.compile(r"^ +branches: \[[^\]]*\bmain\b[^\]]*\]$", re.MULTILINE)
# the value, at whatever indent it is written: GitHub accepts the key on
# a job's own concurrency block as well as on a workflow's, and nothing
# here is to assume which of the two a workflow uses
_CANCEL = re.compile(r"^ *cancel-in-progress: (?P<value>.*)$", re.MULTILINE)
# a value that cancels every event alike, in either spelling GitHub
# accepts for it
_UNCONDITIONAL = re.compile(r"^(?:\$\{\{\s*)?true(?:\s*\}\})?$")
# the triggers whose `closed` type is a pull request being closed. The
# `issues` trigger spells a type of that name too, and it is an issue
# closing rather than a branch merging
_PULL_REQUEST = ("pull_request", "pull_request_target")


def _triggers(text: str) -> dict[str, str]:
    """Return each trigger's own body, keyed by name."""
    start = _ON.search(text)
    assert start, "no on: key in this workflow"
    after = _TOP_LEVEL.search(text, start.end())
    assert after, "nothing at column zero after the on: block"
    region = text[start.end() : after.start()]
    keys = list(_TRIGGER.finditer(region))
    assert keys, "no trigger in this workflow, or not in the expected shape"
    ends = [key.start() for key in keys[1:]] + [len(region)]
    return {
        key["name"]: region[key.end() : end]
        for key, end in zip(keys, ends, strict=True)
    }


_TEXTS = {
    path.name: _COMMENT.sub("", path.read_text(encoding="utf-8"))
    for path in sorted((_ROOT / ".github/workflows").glob("*.yml"))
}
_TRIGGERS = {name: _triggers(text) for name, text in _TEXTS.items()}
_CLOSES = {
    name: any(_CLOSED.search(triggers.get(trigger, "")) for trigger in _PULL_REQUEST)
    for name, triggers in _TRIGGERS.items()
}
_PUSHES_MAIN = {
    name: bool(_MAIN.search(triggers.get("push", "")))
    for name, triggers in _TRIGGERS.items()
}
_CANCELS = {
    name: tuple(found["value"].strip() for found in _CANCEL.finditer(text))
    for name, text in _TEXTS.items()
}
# the workflows a merge leaves without a second reading: what is in
# flight for them when the closed event arrives is the only measurement
# the merged change gets before the schedule comes round
_UNMEASURED_AFTER_MERGE = tuple(
    name for name in _TEXTS if _CLOSES[name] and not _PUSHES_MAIN[name]
)
# and the exception the docstring above leaves room for: a workflow
# asking a question about the pull request rather than measuring the
# commit a merge lands. What the closed event cancels there is a verdict
# on a pull request that has stopped taking changes, so cancelling it
# loses nothing and is what the closed type is taken for (#591)
_ANSWERS_ABOUT_THE_PULL_REQUEST = ("claude-review.yml",)


def test_each_trigger_shape_was_read() -> None:
    """One case per shape the two patterns tell apart is found.

    A trigger reindented, a `types:` list rewritten one entry per line,
    or a `branches:` key spelled another way would each leave every
    workflow reading as neither closing nor pushing, and the check below
    with nothing to ask about. Naming a case on each side of both
    patterns is what turns a pattern that has stopped matching red
    rather than leaving a workflow silently exempt.

    `_CLOSED`'s negative case is a trigger rather than a workflow:
    every `pull_request` trigger here takes the closed type, and the
    `issue_comment` list beside one of them is the list a pattern
    matching any list would match.
    """
    assert _CLOSES["codeql.yml"], "codeql.yml takes the closed type"
    assert _PUSHES_MAIN["codeql.yml"], "codeql.yml pushes on main"
    assert "codeql.yml" not in _UNMEASURED_AFTER_MERGE
    assert "links.yml" in _UNMEASURED_AFTER_MERGE, (
        "links.yml takes the closed type and has no push trigger"
    )
    assert not _CLOSED.search(_TRIGGERS["claude-review.yml"]["issue_comment"]), (
        "claude-review.yml's issue_comment trigger carries a types: list"
        " without the closed type, and reads as taking it: the pattern"
        " matches any list"
    )
    assert not _PUSHES_MAIN["release.yml"], (
        "release.yml pushes on a tag and reads as pushing on main: the"
        " pattern matches any push trigger, so a workflow whose only"
        " push runs on no merge commit would be exempted by it"
    )


def test_a_bare_true_is_still_recognised() -> None:
    """`test.yml` writes the value this reads as unconditional.

    The check below reports nothing when `_CANCEL` stops finding values
    or `_UNCONDITIONAL` stops matching them, and reports nothing when
    every workflow is right. This is what tells the two apart: a
    workflow that carries a bare `true` legitimately, read as carrying
    one.
    """
    assert any(_UNCONDITIONAL.match(value) for value in _CANCELS["test.yml"]), (
        "test.yml's concurrency block sets cancel-in-progress to true and"
        " is not read as unconditional, so nothing here detects one"
    )


def test_each_excepted_workflow_is_one_the_check_would_name() -> None:
    """The exception exempts a workflow the check otherwise reaches.

    An exception covering nothing -- a workflow that has since gained a
    push trigger on main, dropped the closed type, or replaced its bare
    `true` -- still reads as a decision somebody took about a live
    check, and the next reader spends a round rediscovering that it is
    inert. Turning that red is cheaper than leaving it to be read.
    """
    for name in _ANSWERS_ABOUT_THE_PULL_REQUEST:
        assert name in _UNMEASURED_AFTER_MERGE, (
            f"{name} is excepted and is no workflow the check reaches: it"
            " either pushes on main or does not take the closed type"
        )
        assert any(_UNCONDITIONAL.match(value) for value in _CANCELS[name]), (
            f"{name} is excepted and cancels conditionally, so the"
            " exception holds nothing off"
        )


def test_a_merged_pull_request_does_not_cancel_the_run_measuring_it() -> None:
    """No workflow measuring a merged commit cancels unconditionally.

    `_ANSWERS_ABOUT_THE_PULL_REQUEST` is what separates the workflows a
    merge leaves unmeasured from the ones with nothing to measure.
    """
    cancelling = [
        name
        for name in _UNMEASURED_AFTER_MERGE
        if name not in _ANSWERS_ABOUT_THE_PULL_REQUEST
        and any(_UNCONDITIONAL.match(value) for value in _CANCELS[name])
    ]
    assert not cancelling, (
        f"{', '.join(cancelling)} takes the closed pull request event with"
        " no push trigger on main to run it again, and cancels in progress"
        " unconditionally: the closed event's own run then lands in the"
        " group of the run measuring what was merged and cancels it, and"
        " nothing reads the merged commit until the next schedule (#523)"
    )
