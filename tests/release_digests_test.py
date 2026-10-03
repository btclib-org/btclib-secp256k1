# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Every job that handles the sdist in a release checks it against the digests.

`reusable-build.yml` outputs the sha256 of each file it built. The jobs
below refuse an sdist that differs from it before they publish, attach
or install it (issue #1088). The wheels are built by `test.yml`'s own
jobs, which print no digest, and are not covered.

A workflow is read with a regex rather than parsed, being yaml, for
which no group here carries a parser; `interpreters_test.py` does the same.
"""

import re
from pathlib import Path

_WORKFLOWS = Path(__file__).parents[1] / ".github" / "workflows"

# `-b` prints `<hash> *<file>` on GNU and on Git Bash alike, and the build
# job's lines have two spaces: the sed makes the two comparable
_HASH = "sha256sum -b dist/*.tar.gz | sed 's/ \\*dist\\//  dist\\//'"
_DIFF = "diff - <(printf '%s\\n' \"$DIGESTS\" | grep -F '  dist/')"
_JOB = re.compile(r"^  (?P<name>[\w-]+):\n(?P<body>(?:(?:    .*)?\n)+)", re.MULTILINE)
_STEP = "- name: Check the sdist is the one the build job built"


def _jobs(name: str) -> dict[str, str]:
    """Return each job's body of a workflow, by name.

    Args:
        name: the workflow's file name.

    Returns:
        The text under each job key.
    """
    text = (_WORKFLOWS / name).read_text(encoding="utf-8")
    return {m["name"]: m["body"] for m in _JOB.finditer(text)}


def _check_step(body: str) -> str:
    """Return the step that checks the digests, up to the next step.

    Args:
        body: a job's text.

    Returns:
        The step's text.
    """
    start = body.index(_STEP)
    end = re.search(r"\n      (?:- name:|#)", body[start:])
    return body[start : start + end.start()] if end else body[start:]


def test_the_jobs_that_publish_check_the_digest_first() -> None:
    """The publish jobs compare the sdist with the build's digests."""
    jobs = _jobs("release.yml")
    for name in ("publish-pypi", "publish-testpypi"):
        body = jobs[name]
        assert re.search(r"needs:\s*\[\s*build,", body), name
        step = _check_step(body)
        assert "shell: bash\n" in step, name
        assert "DIGESTS: ${{ needs.build.outputs.digests }}" in step, name
        assert _HASH in step, name
        assert _DIFF in step, name
        assert body.index(step) < body.index("gh-action-pypi-publish"), name


def test_the_github_release_and_the_test_workflow_get_the_digests() -> None:
    """`release.yml` hands the output to the callees that check it."""
    jobs = _jobs("release.yml")
    for name in ("github-release", "test"):
        assert "digests: ${{ needs.build.outputs.digests }}\n" in jobs[name], name
    assert re.search(r"needs:\s*\[[^\]]*\bbuild\b", jobs["github-release"])


def test_the_jobs_of_the_test_workflow_check_what_they_download() -> None:
    """Both jobs reading the `sdist` artifact check it on a release."""
    jobs = _jobs("test.yml")
    for name in ("suite-sdist", "check-dist"):
        body = jobs[name]
        step = _check_step(body)
        assert "if: inputs.use-signed-dist\n" in step, name
        assert "shell: bash\n" in step, name
        assert "DIGESTS: ${{ inputs.digests }}" in step, name
        assert _HASH in step, name
        assert _DIFF in step, name
        assert body.index("name: sdist\n") < body.index(step), name


def test_the_patterns_read_a_job_and_a_step() -> None:
    """The controls the tests above need: a job is split, a step is cut."""
    text = "jobs:\n  a:\n    steps:\n      - run: x\n  b:\n    steps:\n      - run: y\n"
    assert [m["name"] for m in _JOB.finditer(text)] == ["a", "b"]
    step = f"      {_STEP}\n"
    assert _check_step(step + "        if: x\n      - name: next\n") == (
        step.strip() + "\n        if: x"
    )
