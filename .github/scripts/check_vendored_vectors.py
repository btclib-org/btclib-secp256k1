# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

r"""Re-check every vendored-vector pin against upstream, weekly: pins and bytes.

tests/README.md pins each vendored vector to a commit and a git blob
SHA-1, with a documented manual procedure to re-check one.
This automates that procedure and reports drift, rather than fixing it:
refreshing a vector file is a decision this script does not get to
make, so what it opens is an issue, never a commit. Ported from a
sibling repository's own check_vendored_vectors.py, which this
package's README convention matches by design.

Two byte comparisons run over every entry that names a file in its
heading and records a `blob` or an `ours` line, whatever its `behind`.
The file's own git blob SHA-1 over its bytes on disk must equal `ours`,
or `blob` where there is no `ours`: `ours` is the blob of the file kept
here, written where it is not upstream's (a reformatting, a trailing
newline). And `blob` must be the one upstream's tree holds for the path
at the pinned commit, which the trees API answers without downloading
the file. A mismatch names the file and makes the run exit 1: a vendored
file edited here, or a pin whose recorded blob is not the one at its
commit, is not drift to be decided about and is not an issue. A file an
entry derives with a `pattern`, where its `behind` reads 0, can also be
drift: edited here, it is reported where it differs from what the
pattern derives at upstream's tip, as below.

The staleness check's scope is narrower than the README could need,
though nothing in this project's own entries reaches the narrower part:
only an entry whose `behind` already reads 0 -- what a human last
confirmed was exactly at upstream's tip -- is checked. An entry already
documented as behind would be a decision already made, and
re-reporting the same gap every week would be noise rather than news;
a sibling repository's own README carries that shape and this one
does not.

An entry whose file upstream does not publish, and which is derived from
upstream's `path` instead, says how in a `pattern` line: the file is
what the README's `git grep -aohP` of that pattern over `path` prints,
piped to `LC_ALL=C sort -u`, and the README's paragraph on `pattern`
says which files that reads. This script reads each of them as text, as
the README says `-a` has git read it. The matches are found line by line
as `_line_matches` says, following git's own loop, and the pattern is
read by Python's `re` where git reads it with PCRE. Such an entry is
judged by that derivation at the tip of its path, on every run, and the
value of its `commit` decides nothing: it is drift where the derived
bytes are not the file's, the report naming the lines only the
derivation holds and those only the file holds. A file that is not here
is drift whatever the pattern derives, an empty derivation included. The
files come from one tarball, held to the tree of the same commit as
`_derived` says. The reading of a `pattern` line is part of what the
copies owe each other: a sibling repository's README carries an entry
with one, and this one does not.

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

import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

# resolved once: S607 is what a bare "gh" in a subprocess list would be,
# a partial executable path relying on PATH's own search order rather
# than naming what actually runs
_GH = shutil.which("gh") or "gh"

# gh's stderr for a server error. A secondary rate limit is not
# retried: GitHub asks to wait as long as its retry-after header says,
# which gh's stderr does not carry, or at least a minute.
_TRANSIENT = re.compile(r"HTTP 5\d\d")
_ATTEMPTS = 3


def _gh_bytes(*args: str) -> bytes:
    """Return the stdout of a `gh` call, printing gh's stderr where it fails.

    A call failing with a server error is made `_ATTEMPTS` times at
    most, waiting longer before each retry; the last error, or any
    other, is raised, carrying gh's stderr as text.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return subprocess.run(  # noqa: S603
                [_GH, *args], capture_output=True, check=True
            ).stdout
        except subprocess.CalledProcessError as error:
            stderr = error.stderr.decode("utf-8", "replace")
            print(f"gh {' '.join(args)} failed: {stderr.strip()}", file=sys.stderr)
            if attempt == _ATTEMPTS or not _TRANSIENT.search(stderr):
                raise subprocess.CalledProcessError(
                    error.returncode, error.cmd, error.output, stderr
                ) from error
            time.sleep(5 * attempt)


def _gh_output(*args: str) -> str:
    """Return the stdout of a `gh` call as text, as `_gh_bytes` makes it."""
    return _gh_bytes(*args).decode("utf-8")


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
    r"^(repo|path|ref|pattern|commit|blob|ours|pulled|behind)(?:[ \t]+(.*))?$",
    re.MULTILINE,
)

# a heading that is one file's own path, in backticks: the file the
# entry's blob is compared with. A glob or a placeholder names no file
_LOCAL = re.compile(r"^`([^`*<>]+)`$")


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

    `pattern` is the entry's own `pattern` line, or None. Where it is
    set, the entry's file is judged by what the pattern derives at the
    tip of `path`, and not by `commit`.
    """

    heading: str
    repo: str
    path: str
    commit: str
    ref: str | None = None
    pattern: str | None = None


@dataclass(frozen=True)
class Pin:
    """One vendored file and the blobs the README records for it.

    `expected` is the blob the file here must hash to: the entry's
    `ours` line where it has one, its `blob` line otherwise. `blob` is
    upstream's, absent where upstream has no one blob to name, and is
    what upstream's tree at `commit` must hold.
    """

    heading: str
    local: str
    repo: str
    path: str
    commit: str
    expected: str
    blob: str | None


@dataclass(frozen=True)
class Drift:
    """A pin drifted from the tip of its own path, or whose path has no tip.

    An entry carrying a `pattern` drifts where its file is not what the
    pattern derives at that tip, and `difference` then says how; any
    other entry drifts where its commit is no longer that tip.
    """

    entry: Entry
    latest_commit: str
    latest_date: str
    difference: str | None = None

    @property
    def has_no_tip(self) -> bool:
        """True where no commit on the branch walked touches the pinned path.

        The empty `latest_commit` is what says so: there is no tip to
        name, `_latest_commit` having answered None. Reading it through
        a name keeps that encoding in one place.
        """
        return not self.latest_commit


def _blocks(readme: str) -> Iterator[tuple[str, dict[str, str]]]:
    """Yield each fenced block's nearest heading before it and its fields."""
    heading = ""
    pos = 0
    for match in re.finditer(r"```text\n(.*?)\n```", readme, re.DOTALL):
        if headings_before := _HEADING.findall(readme[pos : match.start()]):
            heading = headings_before[-1]
        pos = match.end()
        yield heading, dict(_FIELD.findall(match.group(1)))


def _entries_at_tip(readme: str) -> tuple[list[Entry], list[str]]:
    """Return the checkable entries, and the headings this skips.

    A heading is skippable for several reasons: no fenced block of its
    own -- a group heading superseded by finer ones, or a pin whose block
    an edit broke, the two indistinguishable from here -- no
    repo/path/commit triple, a path carrying a `<name>` placeholder, no
    `behind` line, a `behind` line with no value, or a `behind` already
    other than 0 -- a gap a human already decided not to close. The two
    before it are named apart from that last one, being blocks nobody
    has assessed rather than a decision somebody made. An entry carrying
    a `pattern` is skipped too where its heading is not one file's path,
    there being no file to hold to what it derives.
    """
    entries: list[Entry] = []
    skipped: list[str] = []
    owned: set[str] = set()
    for heading, fields in _blocks(readme):
        owned.add(heading)
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
        pattern = fields.get("pattern", "").strip() or None
        if pattern is not None and not _LOCAL.match(heading):
            skipped.append(f"{heading} (a pattern and no one file to hold to it)")
            continue
        ref = fields.get("ref")
        entries.append(
            Entry(
                heading,
                repo,
                path.strip(),
                commit.split()[0],
                ref.strip() if ref else None,
                pattern,
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
    commits = json.loads(_gh_output(*args))
    if not commits:
        return None
    commit = commits[0]
    date: str = commit["commit"]["committer"]["date"][:10]
    sha: str = commit["sha"]
    return sha, date


def _blob_of(data: bytes) -> str:
    """Return the git blob SHA-1 of `data`."""
    header = b"blob %d\0" % len(data)
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def _under(name: str, path: str) -> bool:
    """Tell whether `name` is `path` itself or a path inside it."""
    return name == path or name.startswith(f"{path}/")


def _line_matches(pattern: re.Pattern[bytes], line: bytes) -> Iterator[bytes]:
    r"""Yield the matches `git grep -o` prints for one line, in its order.

    git stops a line at its first empty match, and after a match it
    searches the rest of the line as a string of its own, so a
    lookbehind, `\b` or `\A` there sees no byte before it. The rest is
    searched the same way here. git also keeps `^` from matching at the
    start of that rest, and Python's `re` has no such switch, so a `^`
    there matches here where it does not in git.
    """
    rest = line
    while (match := pattern.search(rest)) is not None and match[0]:
        yield match[0]
        rest = rest[match.end() :]


def _matches(pattern: re.Pattern[bytes], files: Iterable[bytes]) -> bytes:
    """Return every match `_line_matches` finds in `files`, one per line.

    Each file is read line by line, and the lines returned are sorted
    bytewise and deduplicated, as `LC_ALL=C sort -u` sorts them.
    """
    found = {
        match
        for data in files
        for line in data.split(b"\n")
        for match in _line_matches(pattern, line)
    }
    return b"".join(line + b"\n" for line in sorted(found))


def _derived(repo: str, path: str, commit: str, pattern: str) -> bytes:
    """Return what `pattern` derives from upstream's `path` at `commit`.

    The files are read in memory from the tarball the API serves, and
    extracted nowhere. A tarball is `git archive`'s, so an `export-ignore`
    or `export-subst` attribute upstream can make it differ from the
    tree: each file under `path` the derivation reads is held to the
    blob the recursive trees API answers for it, and a file the tarball
    lacks, adds or holds otherwise raises, a symlink it gives as a
    regular file included.
    """
    compiled = re.compile(pattern.encode())
    tree = json.loads(
        _gh_output(
            "api",
            "--method",
            "GET",
            f"repos/{repo}/git/trees/{commit}",
            "-f",
            "recursive=1",
        )
    )
    # mode 120000 is a symlink's, left out as the README says of `pattern`
    blobs = {
        item["path"]: item["sha"]
        for item in tree["tree"]
        if item["type"] == "blob"
        and item["mode"] != "120000"
        and _under(item["path"], path)
    }
    archive = _gh_bytes("api", "--method", "GET", f"repos/{repo}/tarball/{commit}")
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar:
            # the archive holds the tree under one directory of its own
            name = member.name.partition("/")[2]
            reader = (
                tar.extractfile(member)
                if member.isfile() and _under(name, path)
                else None
            )
            if reader is not None:
                files[name] = reader.read()
    if (
        tree["truncated"]
        or {name: _blob_of(data) for name, data in files.items()} != blobs
    ):
        msg = f"the tarball of {repo} at {commit} is not its tree under {path}"
        raise ValueError(msg)
    return _matches(compiled, files.values())


def _printable(line: bytes) -> str:
    """Return `line` as text, each character that does not print escaped.

    A byte that is not UTF-8 is shown as its escape too. The issue body,
    an argument of `gh`, can then hold no NUL.
    """
    return "".join(
        char if char.isprintable() else char.encode("unicode_escape").decode("ascii")
        for char in line.decode("utf-8", "backslashreplace")
    )


def _shown(lines: Iterable[bytes]) -> str:
    """Return lines in backticks, sorted and comma-separated.

    Each is shown as `_printable` shows it.
    """
    return ", ".join(f"`{_printable(line)}`" for line in sorted(lines))


def _lines(data: bytes) -> set[bytes]:
    r"""Return the lines of `data`, split at `\n` alone, as `_matches` splits.

    What follows the last `\n` is a line only where it is not empty.
    """
    pieces = data.split(b"\n")
    return set(pieces[:-1] if pieces[-1] == b"" else pieces)


def _difference(found: bytes, held: bytes) -> str | None:
    r"""Say how the file's bytes, `held`, differ from the derived ones, `found`.

    None where they are the same bytes. Otherwise the lines only the
    derivation holds, and those only the file holds, as `_lines` splits
    them; where there are neither, the same lines in another order or
    number, or with no `\n` after the last.
    """
    if found == held:
        return None
    new, old = _lines(found), _lines(held)
    parts = [
        f"{label}: {_shown(lines)}"
        for label, lines in (("derived only", new - old), ("here only", old - new))
        if lines
    ]
    return "; ".join(parts) or "the same lines, in other bytes"


def find_drift(
    readme_path: Path,
) -> tuple[list[Drift], list[str], list[tuple[str, str]]]:
    """Return every pin drifted from upstream's tip, the skips, and the derived.

    The third list names each entry carrying a `pattern` whose file is
    what that pattern derives at the tip, beside the tip.
    """
    entries, skipped = _entries_at_tip(readme_path.read_text(encoding="utf-8"))
    drifted = []
    derived = []
    for entry in entries:
        latest = _latest_commit(entry.repo, entry.path, entry.ref)
        if latest is None:
            # a path the branch walked never held: drift with no tip to name
            drifted.append(Drift(entry, "", ""))
        elif entry.pattern is not None:
            # the heading is one file's path in backticks, as
            # _entries_at_tip asked of an entry carrying a pattern
            local = Path(entry.heading[1:-1])
            difference = (
                _difference(
                    _derived(entry.repo, entry.path, latest[0], entry.pattern),
                    local.read_bytes(),
                )
                if local.is_file()
                else "the file is not here"
            )
            if difference is None:
                derived.append((entry.heading, latest[0]))
            else:
                drifted.append(Drift(entry, *latest, difference))
        elif latest[0] != entry.commit:
            drifted.append(Drift(entry, *latest))
    return drifted, skipped, derived


def _pins(readme: str) -> tuple[list[Pin], list[str]]:
    """Return the files whose bytes can be compared, and those that cannot be.

    An entry is compared where its heading is one file's path and its
    block names a repository, a path and a commit and carries a `blob`
    or an `ours` line. One that names a file and carries neither has
    nothing to compare against, which is said rather than passed over.
    """
    pins: list[Pin] = []
    skipped: list[str] = []
    for heading, fields in _blocks(readme):
        local = _LOCAL.match(heading)
        repo, path, commit = (
            fields.get("repo"),
            fields.get("path"),
            fields.get("commit"),
        )
        if not (local and repo and path and commit) or "<" in path:
            continue
        values = [fields.get(key, "").split() for key in ("blob", "ours")]
        blob, ours = (v[0] if v else None for v in values)
        expected = ours or blob
        if expected is None:
            skipped.append(f"{heading} (no blob or ours line)")
            continue
        pins.append(
            Pin(
                heading,
                local.group(1),
                repo,
                path.strip(),
                commit.split()[0],
                expected,
                blob,
            )
        )
    return pins, list(dict.fromkeys(skipped))


def _git_blob(path: Path) -> str:
    """Return the git blob SHA-1 of a file's bytes on disk.

    The bytes are the committed ones because `.gitattributes` marks every
    file the README names `-text`, so no checkout converts line endings,
    whatever `core.autocrlf` says. Hashing the bytes on disk, not through
    git's filters, is what catches a file checked out converted.
    """
    return _blob_of(path.read_bytes())


def _upstream_blob(repo: str, path: str, commit: str) -> str | None:
    """Return the blob SHA-1 upstream's tree holds for path at commit.

    None where the tree at that commit has no such path. The trees API
    answers with the directory's entries and so downloads no file, which
    the contents API would, and which caps out on a 9 MB one.
    """
    directory, _, name = path.rpartition("/")
    tree = f"{commit}:{directory}" if directory else commit
    answer = _gh_output("api", "--method", "GET", f"repos/{repo}/git/trees/{tree}")
    return next(
        (item["sha"] for item in json.loads(answer)["tree"] if item["path"] == name),
        None,
    )


def find_mismatches(readme_path: Path) -> tuple[list[str], list[str], int, int]:
    """Return what does not match, what could not be compared, and both counts.

    The counts are the files hashed and the recorded blobs asked of
    upstream, so that a run reading zero of either is visible as such.
    """
    pins, skipped = _pins(readme_path.read_text(encoding="utf-8"))
    mismatches: list[str] = []
    hashed = asked = 0
    for pin in pins:
        local = Path(pin.local)
        if not local.is_file():
            mismatches.append(f"{pin.local}: the README names it and it is not here")
        else:
            hashed += 1
            found = _git_blob(local)
            if found != pin.expected:
                mismatches.append(
                    f"{pin.local}: its bytes hash to blob {found},"
                    f" the README records {pin.expected}"
                )
        if pin.blob is None:
            continue
        asked += 1
        try:
            upstream = _upstream_blob(pin.repo, pin.path, pin.commit)
        except subprocess.CalledProcessError as error:
            mismatches.append(
                f"{pin.local}: asking {pin.repo} for {pin.path} at"
                f" {pin.commit} failed: {error.stderr.strip() or error}"
            )
            continue
        if upstream != pin.blob:
            mismatches.append(
                f"{pin.local}: {pin.repo} at {pin.commit} holds"
                f" {pin.path} as blob {upstream}, the README records {pin.blob}"
            )
    return mismatches, skipped, hashed, asked


def _branch(entry: Entry) -> str:
    """Name the branch, tag or commit `_latest_commit` walked for an entry."""
    return f"`{entry.ref}`" if entry.ref else "the default branch"


def _issue_body(readme_path: Path, drifted: list[Drift], skipped: list[str]) -> str:
    lines = [
        f"`{readme_path}` pins below have drifted from upstream's tip.",
        "Refreshing is a decision, not a chore -- this issue only reports it.",
        "",
    ]
    for drift in drifted:
        if drift.difference is not None:
            lines.append(
                f"- **{drift.entry.heading}**: not what its `pattern` derives from"
                f" `{drift.entry.path}` at `{drift.latest_commit}`"
                f" ({drift.latest_date}), `{drift.entry.repo}` --"
                f" {drift.difference}"
            )
            continue
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
        lines.extend(("", "Not checked by this run, for the reason named:"))
        lines.extend(f"- {heading}" for heading in skipped)
    return "\n".join(lines)


def _open_issue_number(title: str) -> str | None:
    """Return the open issue whose title is exactly `title`, if any.

    The search matches the title as a phrase, so it also finds a longer
    title that holds it. Only an exact title is this script's issue, and
    it can sort behind the longer ones, so the call asks for every issue
    the search can answer rather than gh's default page.
    """
    issues = json.loads(
        _gh_output(
            "issue",
            "list",
            "--state",
            "open",
            "--search",
            f'"{title}" in:title',
            # the most the search API answers
            "--limit",
            "1000",
            "--json",
            "number,title",
        )
    )
    numbers = [str(issue["number"]) for issue in issues if issue["title"] == title]
    return numbers[0] if numbers else None


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
                    (
                        "Re-checked: no pin with behind: 0 has drifted from"
                        " upstream's tip."
                    ),
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


def _drift_line(drift: Drift) -> str:
    """Return the line `main` prints for one drift."""
    if drift.difference is not None:
        return (
            f"DIFFERS: {drift.entry.heading} is not what its pattern derives"
            f" from {drift.entry.path} at {drift.latest_commit}"
            f" ({drift.latest_date}): {drift.difference}"
        )
    if drift.has_no_tip:
        return (
            f"NO COMMIT: {drift.entry.heading} pinned to"
            f" {drift.entry.commit}, and no commit on"
            f" {_branch(drift.entry)} of {drift.entry.repo} touches"
            f" {drift.entry.path}"
        )
    return (
        f"BEHIND: {drift.entry.heading} pinned to {drift.entry.commit},"
        f" latest commit touching it is {drift.latest_commit}"
        f" ({drift.latest_date}), which may have deleted or renamed it"
    )


def main() -> int:
    """Check the README named on argv, report drift, and say so on stdout.

    Exit 1 where a vendored file or a recorded blob does not match,
    after the issue has been dealt with.

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
    drifted, skipped, derived = find_drift(readme_path)
    mismatches, byte_skipped, hashed, asked = find_mismatches(readme_path)
    for drift in drifted:
        print(_drift_line(drift))
    for heading, tip in derived:
        print(f"DERIVED: {heading} is what its pattern derives at {tip}")
    for heading in skipped:
        print(f"SKIPPED: {heading}")
    if not drifted:
        print("No checked pin has drifted from upstream's tip.")
    for heading in byte_skipped:
        print(f"SKIPPED: {heading}")
    for mismatch in mismatches:
        print(f"MISMATCH: {mismatch}")
    print(
        f"Hashed {hashed} files and asked upstream for {asked} blobs:"
        f" {len(mismatches)} mismatches."
    )
    if not dry_run:
        report(readme_path, title, drifted, skipped)
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
