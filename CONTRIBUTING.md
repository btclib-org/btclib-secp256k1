# Contributing

What this repository holds in common with the others of the organization
— the toolchain, the lint gate, the tool tables behind it, the workflow
set and the branch rules — is stated once in the
[btclib-org repository standard](https://github.com/btclib-org/.github),
each rule with the alternative it was decided against. It binds this
repository, so a change departing from it is a divergence, and one filed
as an issue in that repository rather than here: a difference between two
repositories belongs to neither of them.

**This file is the same in every repository of the organization up to
its last section.** What is true of one tree only — the commands that
build its environment, the gates it runs, which of its workflows decide
a merge — is under that heading, and the comparison stops there.

## The issue tracker

Where an issue is filed, and what an alignment finding has to name, is
[the standard's *What this repository is*][s-what]: an issue spanning
repositories, or whose subject is the standard, goes to
[btclib-org/.github](https://github.com/btclib-org/.github/issues), and
one about this tree alone stays here.

A finding noticed while doing something else is filed, not carried.
`REVIEWING.md`'s *Every collateral finding becomes an issue* is the whole
of what to do with one, and it applies to an author as much as to a
reviewer: a pull request answering two questions cannot be accepted for
either.

## Documentation and comments

[Section 9 of the standard][s9] is the prose style, and it governs the
prose this tree ships — comments, docstrings and markdown. It is not
restated here: a second wording is the one that goes stale, which is
that section's own *One fact in one place*.

A commit message is prose this tree ships too, though section 9 does not
say so: [the only merge method the rule accepts][s11] puts it on `main`
as the landing commit's body, so what is written in one is read there
long after the branch is gone.

## Pull requests

What `main` accepts, and what it refuses to everyone, is [section 11 of
the standard][s11]. Run the gates locally before opening anything —
the last section of this file says which they are — because CI runs
exactly them, so a red run there is a local run that was not done.

What a pull request's title and description have to say about the issues
it closes, and why a manual link in the Development panel is a trap
neither of them shows, is [the standard's *What a pull request says it
is*][s-title]. Read it before opening one; it is the rule most often
found broken after the fact.

**Before it is opened, the branch's own commit subjects and bodies are
read against that same rule.** The description does not exist yet to
disagree with them, and [the standard][s-title] has the command that
scans the branch's own commit text for a verb in front of a reference.

**The two spellings are named here as well as there, against [section 9's
*One fact in one place*][s9]**, the paragraph above naming the section
and not the forms, which are the half a citation is got wrong in:
`(closes #N)` cites an issue the change closes, wherever the citation
sits — the title, the commit subject where [*Merge method*][s11] makes
that the thing that lands, and a `CHANGELOG.md` entry — and `(issue #N)`
cites, in those same places, an issue the change advances and does *not*
close. One token holds one meaning whichever file it sits in, so the
pair is chosen by what is true of the change rather than by which file
is being written, and a tree's own landed subjects are not what to copy
it from: nothing already landed is rewritten, so what a repository wrote
before the rule stays where it is.

`REVIEWING.md` is the standard a review is written against, and is this
file's other half. Read before opening a pull request, it is what the
pull request will be answered against.

`CHANGELOG.md` gets an entry for anything a reader would notice, and the
release notes move only for something a user has to *act* on, in the
repositories that publish.

### One subject, opened as soon as it is written

A pull request answers one question. Issues that share a subject are one
pull request, closing each of them; issues that do not are one pull
request each, however small either of them is.

It is opened the moment it is written and verified — not held for the
previous one to be reviewed or to land, and not batched with the next. A
batch arrives as one reviewing job with several subjects, which is the
shape that costs the most to read; a finished pull request held back is
review that could have started and did not.

Working this way stacks branches, which is fine and costs one rule: a
child whose base was amended is moved with the old base named,

```shell
git rebase --onto <new-base> <old-base-sha> <child>
```

because a plain rebase replays the base's old commit inside the child,
and the forge then shows the base's old text as additions with nothing
red anywhere. Read the child's diff afterwards rather than trusting the
rebase, and retarget each child onto `main` as its parent lands.

### The landing queue

Where more than one pull request is open against this repository, only
one is carried to `main` at a time: rebased onto the tip, reviewed on
that head, and landed, while every other one waits, untouched, for its
turn. This governs which of several *already open* pull requests reaches
`main` next; *One subject, opened as soon as it is written* above governs
the moment before that, when a finished one is opened — the two do not
conflict, since a pull request is still opened without delay and still
waits its turn once several are open.

The reason is CI throughput, not the ack a waiting pull request keeps —
`REVIEWING.md`'s *The verdict* states what an ack belongs to, and
*Landing it* below states which rebase voids one. Every rebase queues
this repository's whole check matrix against the organization's ceiling
on concurrent jobs, so rebasing every waiting pull request after each
landing spends that capacity on runs the next landing invalidates
anyway, and delays the one pull request that is actually next: work
spent on a pull request that is not next is work that delays the one
that is. The ceiling's figure is `REPOSITORY.md`'s, under *Plan-gated
settings*, beside the command that re-derives it.

Order is cheapest and least contended first, most invasive last, so that
a large change does not sit at the head blocking everything behind it.

The maintainer may declare a bounded exception — several pull requests in
flight against one repository, for a named piece of work — trading the
cost above for throughput; it is recorded as a comment in
[btclib-org/.github](https://github.com/btclib-org/.github/issues), by
*The issue tracker* above, and holds only for the work it names.

### The review

A review is given promptly and on local evidence. It does not wait for
CI, does not report a check as a finding, and does not discuss a run at
all: whether CI is green is the author's business, once, at landing time.

The exchange is anchored to a sha rather than to a branch, a branch being
free to move under a review:

- the author hands off by naming the sha pushed and the evidence run
  against it, then leaves that head alone;
- the reviewer answers with findings — where, what is wrong, how they
  know it, and whether each is blocking;
- the author accepts what is reasonable, declines the rest with a reason
  in the thread, and pushes the answer without waiting for CI;
- the reviewer resolves the threads they opened, that being what says a
  finding is closed, and re-reviews the delta rather than the branch.

**What ends the loop is the ack of record**, and the author does not
supply their own. A reading that says what it found and delivers no
verdict is a review too and ends nothing; [the standard's *Review*][s-rev]
has which is which, and `REVIEWING.md` has how each is written. A
disagreement that survives a second exchange goes to the maintainer
instead of into a third round.

### Landing it

CI is read once, and this is where. Rebase onto `main`'s tip, push that
head so the checks run on the tree that will land, and only then wait for
them: checks read before a rebase describe a tree nobody is landing. A
rebase that moved nothing but the base leaves the ack standing; one that
resolved a conflict does not, that resolution being a change no reviewer
has seen.

Then squash, [the only method the rule accepts][s11].

**The maintainer's bypass is not automatic — it has to be invoked, and
`gh pr merge` cannot invoke it**, refusing client-side before it asks
GitHub anything:

```text
Pull request is not mergeable: the base branch policy prohibits the merge
```

The merge endpoint applies it server-side, and it is the same endpoint
the merge button asks:

```shell
gh api -X PUT repos/{owner}/{repo}/pulls/<n>/merge \
  -f merge_method=squash -f sha=<the head the checks ran on>
```

**The `sha` is not optional.** Reading the ack and merging are two
calls, and the head is free to move between them — the push that would
move it comes out of the same round the verdict does. Unpinned, the
command takes whatever sits at the head when it runs; pinned, [the
endpoint answers `409` where the head has moved][gh-merge], and a round
lost that way is cheaper than a tree nobody has read reaching `main`.
*The review* above anchors the exchange to a sha and [section 11][s11]
has an ack name one: the pin is that rule reaching the call that
performs the landing.

**Verify what landed rather than trusting the answer**, the signature
[the standard asks for][s-sigs] being a valid one rather than a
particular signer's:

```shell
gh api repos/{owner}/{repo}/commits/main \
  --jq '.commit.verification | {verified, reason}'
```

**What it closed is read again here too, from the landed sha rather
than from the pull request**: [the standard's *What a pull request says
it is*][s-title] has the second read, and why the first alone does not
reach a squash subject composed after it runs.

The forge deletes the head branch itself, per the setting section 11
names. What is still yours is bringing every checkout sitting on `main`
up to date,
that being where the next session starts from and a stale one being where
a branch gets built on a base that has moved. `REPOSITORY.md` carries the
settings and why they are what they are.

[s-what]: https://github.com/btclib-org/.github#what-this-repository-is
[s11]: https://github.com/btclib-org/.github#11-github-settings
[s9]: https://github.com/btclib-org/.github#9-prose-comments-and-docstrings
[s-title]: https://github.com/btclib-org/.github#what-a-pull-request-says-it-is
[s-rev]: https://github.com/btclib-org/.github#review
[s-sigs]: https://github.com/btclib-org/.github#signatures
[gh-merge]: https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request

## This repository in particular

Everything above is the same file in every repository of the
organization; everything below is this one's, and the comparison stops at
this heading.

### Which repository an issue belongs to

These are thin python bindings to
[libsecp256k1](https://github.com/bitcoin-core/secp256k1). An issue in
the wrong repository is slow to route:

- the cryptography is upstream, vendored here as a submodule and only
  ever read from: a flaw in the library itself is not ours to fix, and
  it goes to that library's own tracker. The import line says which
  library answered —
  [bitcoin-core/secp256k1](https://github.com/bitcoin-core/secp256k1/issues)
  outside `btclib_secp256k1.zkp`, and
  [BlockstreamResearch/secp256k1-zkp](https://github.com/BlockstreamResearch/secp256k1-zkp/issues)
  under it. `.gitmodules` names every vendored submodule and where it
  comes from
- anything with state of its own — a wallet, a transaction, a signing
  session — belongs in
  [btclib](https://github.com/btclib-org/btclib/issues), which is what
  these bindings are for. The Design section of the README says where the
  line is
- what belongs here is how the bindings drive what they wrap: the
  wrapping, the argument validation at the cffi boundary, the packaging,
  and the wheels

The bug form asks which of the three artifacts is installed — a static
wheel, a dynamic one, or a build from the sdist — because they differ in
how libsecp256k1 is linked and a bug is rarely in all three. A
vulnerability is never an issue: see the
[security policy](./SECURITY.md).

### The environment and the gates

<!-- The toolchain badges are here rather than in README.md because they
report no state: each names a choice, and this is the section that says
how the choice is enforced and what the command for it is. They are under
this heading rather than at the top of the file because everything above
it is the same file in every repository of the organization, so nothing
at the top of it can be one repository's. The README keeps the badges
that can turn red. -->
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![format: ruff](https://img.shields.io/badge/format-ruff-yellowgreen.svg?logo=ruff)](https://docs.astral.sh/ruff/formatter/)
[![lint: ruff](https://img.shields.io/badge/lint-ruff-yellowgreen.svg?logo=ruff)](https://docs.astral.sh/ruff/)
[![docstrings: ruff](https://img.shields.io/badge/docstrings-ruff-yellowgreen.svg?logo=ruff)](https://docs.astral.sh/ruff/rules/#pydocstyle-d)
[![type check: mypy](https://img.shields.io/badge/type_check-mypy-yellowgreen.svg?logo=mypy)](https://mypy-lang.org/)
[![lint: markdownlint-cli2](https://img.shields.io/badge/lint-markdownlint--cli2-yellowgreen.svg?logo=markdown)](https://github.com/DavidAnson/markdownlint-cli2)
[![pre-commit enabled](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

uv is the only thing that has to be installed; it fetches interpreters
and tools itself. A C toolchain is the second prerequisite, this package
compiling the vendored library and an extension against it, and the
[Build](./README.md#build) section of the README says what each platform
needs.

The vendored libraries are submodules, and a clone gets their
directories without the files in them, so a checkout is two commands
before it is anything:

<!-- markdownlint-disable MD013 -->
```console
$ git submodule init
Submodule 'secp256k1' (https://github.com/bitcoin-core/secp256k1.git) registered for path 'secp256k1'
Submodule 'secp256k1-zkp' (https://github.com/BlockstreamResearch/secp256k1-zkp.git) registered for path 'secp256k1-zkp'
$ git submodule update
Cloning into '.../secp256k1'...
Cloning into '.../secp256k1-zkp'...
```
<!-- markdownlint-enable MD013 -->

Each `Cloning into` line carries the absolute path of the directory git
writes to, elided above. A `Submodule path ...: checked out ...` line
follows per submodule, left out here because the commit it names moves
with the pin.

Then the environment. `.python-version` pins the interpreter and uv
installs it if it is missing, so neither pyenv nor a hand-made virtualenv
is needed; the development dependencies are the PEP 735 groups declared
in `pyproject.toml`.

```shell
uv sync --locked
```

That also builds and installs the extension in editable mode, which is
the minutes rather than seconds part of it.

A `git worktree` starts with those directories empty however complete
the checkout it was made from, so the submodules are a precondition of
the gates below and not of a clone alone:

```shell
git submodule update --init
```

With no path after it, that reaches every submodule `.gitmodules` names.

The test and documentation gates install this package, and installing it
compiles libsecp256k1 out of `secp256k1/` before any `automodule`
directive imports the result. The lint gate installs no project —
`--only-group` omits it — and needs the vendored clone all the same:
`submodule-pin` resolves the release `README.md` names in that clone's
own refs, which is what lets the check run offline.

That gate fails outright where a submodule `.gitmodules` names is not
checked out at all: `submodules-checked-out` asks that on every
invocation, whatever the commit touches.

Three gates decide a merge, and each command below is close to the one
its workflow runs — the second is what a contributor types, not what
`test.yml` runs, and the difference is coverage's own:

```shell
uv run --locked --only-group lint pre-commit run --all-files
uv run --locked --no-default-groups --group test pytest
uv run --locked --no-default-groups --group docs \
    sphinx-build -n -W -b html docs/source docs/build/html
```

Coverage is measured in branch mode, `--cov` sitting in `addopts` so
nothing has to be typed after `pytest` to see it. The `fail_under`
ratchet in `pyproject.toml` gates at 100%, but the plain command above no
longer reaches it on its own: `btclib_secp256k1.zkp.musig` (#607 onward)
is opt-in behind `BTCLIB_LIBSECP256K1_ZKP` by decision (#603), and
without the flag nothing calls into it. The module is imported all the
same — `tests/all_test.py`'s census and `tests/secret_test.py`'s walk
both descend into the subpackage, and the documentation build imports
it for its own `:members:` — so what an unflagged run executes there is
its module-level lines and no function body. Nothing drives it: a test
that does carries `pytest.importorskip("_btclib_secp256k1_zkp")` and the
`zkp` marker, so an unflagged run skips it. Nothing in it can be
*called* there either: every entry point reads `ffi`, `lib` or `ctx`
inside the call rather than at module scope, and that read is what
raises `btclib_secp256k1.zkp`'s `ImportError` naming the flag. This
command reports short of 100% on an ordinary checkout —
that shortfall is not the module alone: `[tool.coverage.run]` names
`tests` in `source` too, so `tests/zkp_musig_test.py` and
`tests/zkp_musig_vectors_test.py` are measured the same way, and each
stops at its own `importorskip` before a line below it runs, reported
missed rather than absent from the table. A flagged module and its test
files appearing short in that report is what a contributor should expect to
see, not a broken tree; which files those are grows with every module #603
still has queued behind it, so nothing here counts them.
`test.yml`
runs this same command against three builds: once per linkage, plus
once more against the flagged build restricted to the tests marked
`zkp` — `-m zkp`, a selection rather than the whole suite, the same
restriction this paragraph goes on to call out below — each carrying
its own `--cov-fail-under=0`, and gates the union of the three at 100%
after `combine`; "Measure coverage, gated at 100%" below is the
sequence that reproduces that union, and its own 100.00% is CI's real
number, for whoever builds the extension to check it locally. A run
that asks for less than the full suite even at that — a path leaving
part of `tests` out, `-k`, `-m`, `--deselect`, `--ignore`,
`--ignore-glob` or `--lf` — reports its coverage and is gated at
nothing either way, `tests/conftest.py` being where that is decided and
why.

The group flags are not decoration. `uv run` syncs the environment
itself, and without `--no-default-groups --group test` it installs the
whole dev set, wider than what the suite needs. After touching
`pyproject.toml`, `uv lock` — the `uv-lock` hook does it too, and then the
gate is a second run.

**Check exit codes, not filtered output.** `pre-commit run ... | grep -v
Passed` hides a failure, and `grep` finding nothing exits 1, which is not
the gate's answer to anything.

**The lint gate is not installed as a git hook.** `pre-commit install`
writes into the common git directory, which every worktree of this
repository shares:

```shell
git rev-parse --git-path hooks
```

answers with the primary checkout's `.git/hooks` in every worktree, so
one session installing it installs it for every other. Run the gate by
hand before committing.

Two hooks are regenerated rather than fixed when they fail. The test data
is private keys, so `detect-secrets` would report all of it; the known
findings are recorded as reviewed rather than excluded, in two baselines
that differ only in whether the entropy detectors run. Adding a hex
constant to a test module, or a vector to a file under `tests/` matching
`*.csv` or `*.json`, fails the corresponding hook until its baseline is
regenerated.

The first command regenerates `.secrets.baseline`, over the tree with entropy
detectors on. `--slim` omits `line_number` and `generated_at`, so the
file stops changing when a flagged line moves; the scan is fresh rather
than `--baseline`, which writes the full form whatever it read —
`--slim` reaches `format_for_output` only on the branch that prints to
stdout — so the exclusion is spelled out rather than read back from the
baseline's own filter:

```shell
uvx --from detect-secrets detect-secrets scan --slim \
    --exclude-files '^(\.secrets\..*baseline|tests/.*\.(csv|json))$' \
    > .secrets.baseline
```

The second command regenerates `.secrets.vectors.baseline`, over the
vendored vector data with entropy detectors off: these files are
64-character hex and nothing else, so a new vector would read as a new
secret. The paths are the hook's `files` pattern spelled out:

```shell
uvx --from detect-secrets detect-secrets scan --slim \
    --disable-plugin HexHighEntropyString \
    --disable-plugin Base64HighEntropyString \
    tests/*.csv tests/*.json \
    > .secrets.vectors.baseline
```

Both are slim, and what that costs is one field of the diff: a new secret
still arrives as a new `hashed_secret` under its filename, and finding
*where* it is takes a grep instead of a line number. `detect-secrets
audit` needs the full form and says so, which is a reason to regenerate
without `--slim` for an audit rather than to keep the churn in the
committed file.

The redirect costs a second thing, which is the one to know before
auditing: `--baseline` does not only save, it **merges**, and what it
carries forward is exactly the audit's product — `is_secret` and
`is_verified` per finding, "verification of secrets, both automated and
manual" in its own words. A scan into a file has no old baseline to
merge, so those marks go back to their defaults, and slim output prints
no `is_secret` at all when it is unset: the loss shows up as a diff of
nothing. `jq '[.results[][]] | length' .secrets.baseline` (and the same
against `.secrets.vectors.baseline`) is how to check whether there is
anything to lose — every finding in either file being unverified and none
carrying `is_secret` means there isn't, today — but an audit's marks want
saving elsewhere or re-applying after the next regeneration. Read the
diff before committing it, which is the whole point of a baseline: what
appears there is what nobody has looked at yet.

Two things the gates enforce about the prose, which section 9 of the
standard states as a rule and does not say is checked here. `pydoclint`
requires an `Args` entry per parameter and a `Returns` section, in the
Google style napoleon renders, so a new argument nobody documented fails
the lint gate; `Raises` is not enforced, and `pyproject.toml` says why
beside the setting that turns it off. And anything written as a doctest,
in a docstring or in `README.md`, is run by `tests/examples_test.py` on
every interpreter and every kind of wheel — which constrains an example
to be deterministic: fixed keys, and a verification rather than a
signature wherever the value depends on randomness that is not pinned.
A docstring under `btclib_secp256k1.zkp` runs only where the flagged
extension is built: `tests/examples_test.py` marks that module's case
`zkp` and guards it with an `importorskip`. In CI that is the `Build the
flagged secp256k1-zkp extension, and run its tests` job below and the
flagged step of the coverage job.

To time these bindings against the other python wrappers of
libsecp256k1, clone
[btclib-benchmarks](https://github.com/btclib-org/btclib-benchmarks) and
run `scripts/libsecp256k1_wrappers.py` there. The comparands are that
project's dependencies rather than this one's, which is the point: the
library downstream of these bindings is one of them, and depends on
these bindings itself.

To test against another supported interpreter, bypass the build cache:
uv keys it on the sources, which do not tell it that the compiled
extension belongs to one ABI version only.

```shell
uv run --python 3.10 --no-cache pytest
```

On a Windows arm64 machine, mind which interpreter that request gets:
uv installs an x86-64 one unless the architecture is named
(`--python cpython-3.13-windows-aarch64`), reporting that support for
the native architecture is not yet mature. Both work — the build follows
the interpreter — but only the native one exercises what the `win_arm64`
wheels are.

Beware that this replaces `.venv` with an environment built on that
interpreter, and leaves it there. Going back is another `uv sync`, and
`--reinstall-package btclib-secp256k1 --no-cache` if the extension it
finds in the cache is the one of the ABI just left behind. Requesting a
free-threaded interpreter (`--python 3.14t`) has a second effect: it
installs it as a managed one, and `uv sync` then prefers it to a system
3.14, so `uv python install 3.14` is what makes the default environment
reproducible again.

Naming the environment keeps the default one instead, at the price of a
second build of the extension:

```shell
UV_PROJECT_ENVIRONMENT=.venv-3.10 uv run --python 3.10 --no-cache pytest
```

`.gitignore` matches that name with `.venv*/`, the comment beside the
pattern saying what ships the environment when nothing matches it.

A `git pull` that changes `scripts/hatch_build.py` is not itself enough
to reach a `.venv` a `uv sync --locked` already considers satisfied: the
sync reports the package `Checked`, not rebuilt, and installs nothing
new even where the pulled change moves what the hook decides.
`--reinstall-package btclib-secp256k1` is what forces the rebuild;
`--refresh-package btclib-secp256k1` alone does not.

To build the distributions:

```shell
uv build --sdist
uv build --wheel
```

#### The editor

`.vscode/settings.json` and `.vscode/extensions.json` are tracked, and they
hold no preference: the recommended extensions are the tools
`.pre-commit-config.yaml` already runs, and the settings put the fixing ones
on save. Installing them is optional and changes nothing about what a commit
enforces — what they buy is learning of a finding while typing rather than
at the commit that trips over it.

Anything machine-local — an interpreter path, a telemetry answer, a theme —
belongs in the editor's own user settings instead, those two files being
read by every checkout of this repository.

### Running what CI runs

Each job of the `lint`, `docs` and `test` workflows, and the local command
that reproduces it. Two of them cannot be reproduced on a machine that is
not the runner, and that is worth knowing before trying; `codeql` has no
command at all, for the reason below, and nothing requires its result.

- `Lint and type-check`

  ```shell
  uv run --locked --only-group lint pre-commit run --all-files
  ```

- `Ask which files the pull request touches`, whose answer decides whether
  the rest of `test.yml` runs at all

  ```shell
  gh api "repos/btclib-org/btclib-secp256k1/pulls/<number>/files" \
      --paginate --jq '.[].filename' > files.txt
  eval "$(/usr/bin/grep -m1 '^ *prose=' .github/workflows/test.yml)"
  if [ ! -s files.txt ] || /usr/bin/grep -qvE "$prose" files.txt; then
      echo "everything runs"
  else
      echo "prose only"
  fi
  ```

  The second line lifts the pattern out of the workflow rather than
  restating it here, so the two cannot drift. `/usr/bin/grep` rather than
  `grep`, because where the shell's is [ugrep](https://ugrep.com) the
  third line answers the opposite question: ugrep takes the status from
  whether the *pattern* matched anywhere and inverts that, rather than
  from whether `-v` selected a line. A list of only prose and a list of
  only code come out right either way; one mixing the two exits 1 and
  reads as "prose only", which is the direction that skips a matrix that
  should have run, and nothing says it has. `-q` is what asks the
  question of the file rather than of the lines, and ugrep takes the same
  path when the output is discarded, so `-cvE` and a numeric test agree
  with both greps. The runner's `grep` is GNU's, so what ugrep can get
  wrong here is the reproduction and not the workflow
  (<https://github.com/btclib-org/btclib-secp256k1/issues/242>)

- `Measure coverage, gated at 100%`, which is the suite against each
  linkage, the tests marked `zkp` against the flagged build, and the
  union of the three gated at the ratchet

  ```shell
  COVERAGE_FILE=coverage-data-static \
      uv run --locked --no-default-groups --group test pytest \
      --cov-fail-under=0
  BTCLIB_LIBSECP256K1_DYNAMIC=true COVERAGE_FILE=coverage-data-dynamic \
      uv run --locked --no-default-groups --group test \
      --reinstall-package btclib-secp256k1 --no-cache pytest \
      --cov-fail-under=0
  BTCLIB_LIBSECP256K1_ZKP=true COVERAGE_FILE=coverage-data-zkp \
      uv run --locked --no-default-groups --group test \
      --reinstall-package btclib-secp256k1 --no-cache pytest \
      -m zkp --cov-fail-under=0
  uv run --locked --no-default-groups --group test \
      coverage combine coverage-data-static coverage-data-dynamic \
      coverage-data-zkp
  uv run --locked --no-default-groups --group test coverage report
  ```

  none of the three is gated at 100 on its own any more, each carrying
  its own `--cov-fail-under=0` for a different line it cannot execute:
  the linked-in branch of `_load_lib` for the dynamic run, and
  `btclib_secp256k1.zkp.musig` (#607 onward) for both the static and
  the dynamic run, since neither sets `BTCLIB_LIBSECP256K1_ZKP` and the
  zkp run's own `-m zkp` selection is what reaches it. What answers for
  each missing line is one of the other two runs, and the combined
  report -- the first and only place 100 is actually asked for -- is
  what answers for a line none of the three reaches, taking its
  threshold from `[tool.coverage.report]`. The data files are written
  where the command runs and `.gitignore` names them, `combine`
  consuming all three and leaving `.coverage`, which it names too

- `Build the flagged secp256k1-zkp extension, and run its tests`

  ```shell
  BTCLIB_LIBSECP256K1_ZKP=true uv run --locked --no-default-groups \
      --group test --reinstall-package btclib-secp256k1 --no-cache \
      python -c "import _btclib_secp256k1_zkp as m; print(m.lib)"
  BTCLIB_LIBSECP256K1_ZKP=true uv run --locked --no-default-groups \
      --group test pytest -m zkp --no-cov
  ```

  `--reinstall-package` and `--no-cache` on the first command for the
  same reason the coverage job's own dynamic run needs them: uv's build
  cache is not keyed on this variable, only on the source tree, so a
  local venv already holding an unflagged build serves it back unless
  told not to -- a fresh venv does not need either flag, and the job
  carries them regardless of which a runner happens to be. The second
  command selects the tests marked `zkp`, over
  `btclib_secp256k1.zkp.musig` (#607) and the modules #608 and #609
  add; an exit of 5, pytest's own "no tests ran", is a real failure
  here -- a selection that collected nothing, from a renamed marker, a
  moved file, or a `-m` matching no test

- `Build wheels on <os>`, for this platform only

  ```shell
  uv run --locked --only-group build cibuildwheel
  ```

  the job pins the build timestamp first, and reproducing the wheel
  means pinning the same one:

  ```shell
  export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
  ```

  every member of the archive carries it: `hatchling` stamps the members
  it writes at a constant of its own without it, and `auditwheel` or
  `delocate` gives the clock of the moment to the members the repair
  rewrites, which is what makes two builds of one commit differ where
  nothing else does. `[tool.cibuildwheel.linux]` passes the variable into
  the container; the reasoning is in `test.yml`, next to the step that
  exports it.

  The Linux wheels of that job are built in a manylinux container, so
  reproducing them needs a container runtime (`colima` on macOS)

- `Build dynamic wheel on <os>`

  ```shell
  BTCLIB_LIBSECP256K1_DYNAMIC=true uv build --wheel
  ```

  on macOS the job exports a deployment target first — 11.0, or 10.13
  on x86_64, the floor cibuildwheel gives the static x86_64 wheels — and
  reproducing it means exporting the same one:

  ```shell
  export MACOSX_DEPLOYMENT_TARGET=11.0
  ```

  a dynamic wheel compiles no extension, so nothing derives its platform
  tag from a toolchain: without that variable `hatch_build.py` falls back
  to `platform.mac_ver()`, and the wheel comes out `macosx_26_0_arm64` on
  a macOS 26 machine — a tag `pip` refuses on every older macOS the file
  would in fact have loaded on. CMake reads the same variable, so the
  vendored library is built for the floor the tag then claims; the two
  values and the reasoning behind them are in `test.yml`, next to the
  step that exports them.

  On every platform of that job the build timestamp is pinned as well,
  as in `Build wheels on <os>` above -- `auditwheel` and `delocate` run
  here as steps of the job rather than inside `cibuildwheel`, and read
  it the same way:

  ```shell
  export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
  ```

- `Build sdist`, and `Install from the sdist and run the suite on <os>`
  after it. The build timestamp is pinned as in `Build wheels on <os>`
  above, and the normalizer that follows the build reads that same
  variable to rewrite every member's `mtime`, refusing to run without
  it -- its own docstring has the reasoning. That job installs with pip
  rather than uv, its subject being pip resolving the published artifact
  rather than uv reading the lock, so reproducing the install wants a
  fresh venv rather than the project's own:

  ```shell
  export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
  uv run --locked --only-group build python -m build -s
  uv run --no-project --python 3.14 \
      .github/scripts/normalize_sdist.py dist/
  python -m pip install --verbose dist/*.tar.gz
  ```

- `Inspect the distribution files and install one`

  ```shell
  uv run --locked --only-group check twine check --strict dist/*
  uv run --locked --only-group check check-wheel-contents dist/*.whl
  uv run --locked --only-group check pyroma --min 10 dist/*.tar.gz
  ```

- `Build on Linux for Windows` needs `mingw-w64`, and a Linux host to be
  faithful: the cross-compilation CI does is from ubuntu, not from macOS.
  That job pins the build timestamp too, and nothing repairs its wheel,
  so `hatchling` alone writes the members and this is what decides their
  timestamp:

  ```shell
  export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
  ```

- `test: every job passed` reproduces as nothing, and is here because it
  is the required check and therefore the one a contributor sees red: it
  reads the conclusions of the jobs above it and runs no command of its
  own. What turned it red is one of them, in the run

- `Build the documentation`, the same command `.readthedocs.yaml` runs
  and `docs/README.rst` documents

  ```shell
  uv run --locked --no-default-groups --group docs \
      sphinx-build -n -W -b html docs/source docs/build/html
  ```

The `pypi-install` workflow has no local equivalent by design: what it
installs is what PyPI serves.

The sentinels beside it gate nothing, so a red one is read in the Actions
tab rather than fixed on a branch. Each is dispatchable, and all but `links`
run locally.

- `os-ubuntu`, `os-macos` and `os-windows`, the suite on both images of
  a platform and on every interpreter, so only the row matching the
  machine at hand reproduces. A cell is these two commands in this order —
  the suite run once against each linkage, with `--python` standing for
  the interpreter the row names:

  ```shell
  uv run --locked --no-default-groups --group test --python 3.10 \
      pytest --no-cov
  BTCLIB_LIBSECP256K1_DYNAMIC=true uv run --locked --no-default-groups \
      --group test --python 3.10 --reinstall-package btclib-secp256k1 \
      --no-cache pytest --no-cov
  ```

  the second re-installs rather than reusing what the first built,
  because neither the environment nor the build cache is keyed on the
  variable that chooses the linkage. `--no-cov` is in both, against the
  `--cov` `addopts` carries: what a cell asks is whether an (image,
  interpreter) pair passes, and coverage is measured and gated once, on
  the gate's cell

- `deps-latest`, which resolves every dependency at its newest before
  running the suite. The upgrade rewrites `uv.lock`, so restore it
  afterwards with `git checkout uv.lock`:

  ```shell
  uv lock --upgrade
  uv run --locked --no-default-groups --group test pytest
  ```

- `links` needs a tool uv does not provide, lychee being a rust binary, so
  the workflow uses the action. `.lycheeignore` holds the URLs a checker
  cannot judge, each with the reason it cannot be checked rather than the
  reason checking it is inconvenient

- `mutation`, scoped by `.github/mutation/bindings.toml`, which is what the
  workflow reads too:

  ```shell
  uv run --locked --no-default-groups --group test --group mutation \
      cosmic-ray baseline .github/mutation/bindings.toml
  uv run --locked --no-default-groups --group test --group mutation \
      cosmic-ray init .github/mutation/bindings.toml bindings.sqlite
  uv run --locked --no-default-groups --group test --group mutation \
      cr-filter-operators bindings.sqlite .github/mutation/bindings.toml
  uv run --locked --no-default-groups --group test --group mutation \
      cosmic-ray exec .github/mutation/bindings.toml bindings.sqlite
  uv run --locked --no-default-groups --group test --group mutation \
      cr-report --surviving-only --show-diff bindings.sqlite
  uv run --locked --no-default-groups \
      python .github/scripts/mutation_counts.py bindings.sqlite
  ```

  `baseline` first, always: it runs the configured test command against the
  unmutated tree, and without it a stale command fails every mutant
  identically and the session reports a perfect kill rate — the one failure
  mode of a mutation run that looks like good news. The session mutates the
  source in place and restores it, so nothing else may read the tree while
  it runs: no second session, no `pytest` in another shell, and a
  `git status` in the middle is a working tree with a mutant in it. `exec`
  is resumable, so interrupting one costs only the mutant it was on, and the
  `.sqlite` is what the workflow uploads beside the reports — `cr-report`,
  `cr-html` and the counter all read one.

  `cr-filter-operators` marks as skipped what the configuration excludes by
  operator, which here is every mutant of a `|` in an annotation: none of
  them is reachable by any test, and an unreachable mutant costs a whole run
  of the suite to survive. Skipping them is what leaves a survivor list
  somebody reads to the end — the comment in `bindings.toml` carries the
  grep that keeps the exclusion honest.

  `--surviving-only` is the whole of what anybody acts on, a killed mutant
  being the suite doing its job. Read the list expecting nothing: the two
  shapes that used to be in it — an output buffer sized twice, and
  generated randomness whose length no answer reveals — were answered in
  the code rather than excused in a comment, and the session that measured
  that reported no survivor at all. So whatever is in the list is a test
  nobody has written yet.

  The counter last, and not `cr-rate`: that tool reads anything that is not
  SURVIVED as a kill, so it counts the skipped mutants among them and
  divides by the whole session. `mutation_counts.py` prints killed, survived
  and skipped with the rate over what actually ran, and exits non-zero on an
  outcome that is no verdict at all — an INCOMPETENT mutant, or a worker
  that raised, which is Cosmic Ray not having measured rather than a test
  that is missing.

- `vendored-vectors`, whose two jobs ask two unrelated questions and
  reproduce separately. `check` re-reads every pin in `tests/README.md`
  against upstream, and `--dry-run` is what the `pull_request` trigger
  passes so that the run edits no tracking issue — which is what a run
  by hand wants too:

  ```shell
  uv run --no-project python \
      .github/scripts/check_vendored_vectors.py tests/README.md --dry-run
  ```

  `--no-project` because there is no environment to build for it: the
  script imports only the standard library and shells out to `gh`, which
  has to be authenticated. The workflow's own line is a bare `python`,
  which is setup-python's on the runner and need not be anything on a
  machine that has uv and no interpreter of its own on `PATH`. Without
  the flag it is the scheduled run, and it opens, edits or closes the
  issue it finds.

  `pin` asks the two halves `submodule-pin` cannot ask offline —
  whether the tag `README.md` names is the one upstream publishes, and
  whether a libsecp256k1 maintainer signed it. The last two lines below
  are the comparison itself: the first prints what upstream's tag
  resolves to and the second what this tree's gitlink pins, and the pin
  is correct where the two commits agree:

  ```shell
  gpg --keyserver hkps://keys.openpgp.org --recv-keys \
      $(grep -oE '\b[0-9A-F]{40}\b' .github/workflows/vendored-vectors.yml)
  named=$(sed -n 's|.*secp256k1/releases/tag/\(v[0-9][0-9.]*\).*|\1|p' \
      README.md | head -1)
  git -C secp256k1 fetch --force origin "refs/tags/${named}:refs/tags/${named}"
  git -C secp256k1 tag -v "${named}"
  git -C secp256k1 rev-parse "${named}^{commit}"
  git ls-tree HEAD secp256k1
  ```

  the fingerprints are lifted out of the workflow rather than written
  again here, a second list being one that drifts, and their case is
  what selects them: the action pins in that same file are hex of the
  same length in lower case. What the runner never has to care about and
  a developer does is where the two writes land — `--recv-keys` puts
  three third-party public keys in whichever keyring it is pointed at,
  the default one unless `GNUPGHOME` says otherwise, and the
  `fetch --force` moves the tag `README.md` names in the vendored clone
  to what upstream serves, which is the question being asked and is also
  what `submodule-pin` resolves against afterwards.

  `${named}` is braced against this shell rather than against the
  runner's. zsh reads the `:r` of an unbraced `$named:refs/tags/...` as
  a history modifier, strips the last dotted component and fetches
  `refs/tags/v0.8efs/tags/v0.8.0`, which upstream does not have; bash,
  which is what the workflow runs, reads the same line as written. The
  same asymmetry as `/usr/bin/grep` above, and in the same direction:
  what a local shell gets wrong here is the reproduction and not the
  workflow

- `wheel-reproducibility`, which builds this commit's wheel twice, from
  two directories it extracts `HEAD` into, and diffs the two archives
  member by member. The job pins the build timestamp first, as in
  `Build wheels on <os>` above; `hatchling`'s own fallback constant
  would make the two local builds agree either way, so what pinning it
  buys here is that this measurement and the wheel a release actually
  builds do not differ in an exported variable:

  ```shell
  export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
  uv run --no-project python \
      .github/scripts/check_wheel_reproducibility.py
  ```

  `--no-project` for the same reason as `check_vendored_vectors.py`
  above: the script imports only the standard library and shells out to
  `uv` itself to run each build. Only the environment the command runs
  in is answered locally; the workflow's own matrix is what asks the
  rest, the second image it builds each platform on included

  The workflow's `repaired` job asks the same question of the file PyPI
  actually receives: `uv build` stops at the archive `hatchling` writes,
  where `cibuildwheel` repairs it with `auditwheel`, `delocate` or
  `delvewheel`, and it is that rewritten archive the job builds twice
  and diffs. It pins the same timestamp first, and here the export is
  not optional: `auditwheel` and `delocate` take each member's `mtime`
  from the clock of the moment where the variable is unset, so two
  sequential builds of one unchanged commit disagree and the check
  reports a wheel that does reproduce as one that does not. It
  reproduces the same way otherwise, for this platform only, and needs
  `cibuildwheel` on `PATH`:

  ```shell
  export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
  uv run --locked --only-group build python \
      .github/scripts/check_wheel_reproducibility.py --repaired
  ```

  as with `Build wheels on <os>` above, the Linux build runs inside a
  manylinux container, so reproducing it needs a container runtime
  (`colima` on macOS). `CIBW_BUILD` narrows the workflow's own run to
  one interpreter; left unset, this builds every interpreter
  `cibuildwheel` selects for the platform at hand

  The `dynamic` and `cross-windows` jobs ask the same question of the
  `py3-none-*` wheels, which `build-dynamic` and `build-windows` build
  with `python -m build` rather than with either frontend above and
  which `publish-pypi` uploads with the rest. `--dynamic` builds the
  wheel of the platform it runs on and repairs each build the way that
  job does, with `auditwheel` or `delocate`; `--cross-windows` builds
  the `win_amd64` one and repairs nothing, wanting a `mingw-w64`
  toolchain where the job above wants a container. Both refuse an unset
  `SOURCE_DATE_EPOCH`: where a repair runs the reason is the one above,
  and where none does it is that the archive would carry `hatchling`'s
  fallback constant rather than the instant the rest of the release
  carries:

  ```shell
  export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)
  uv run --locked --only-group build python \
      .github/scripts/check_wheel_reproducibility.py --dynamic
  ```

### What a change here has to satisfy

Past the gates above, and past what section 9 of the standard asks of any
tree's prose:

- **new wrapped functionality is validated against external vectors.**
  A test that compares these bindings against themselves proves nothing.
  `tests/vectors_test.py` documents where each vendored vector file comes
  from — BIP340, RFC6979, trezor-firmware — and a new wrapper should
  reach for something published elsewhere in the same way. A test's
  docstring says which side of the assertion is the independent one,
  which is why a docstring is required of a test at all: the name says
  which call is under test, and not what is being claimed about it
- **a new wrapper checks sizes and delegates the rest.** What the
  boundary is for is stopping a short buffer from reaching a bare
  pointer; whether the bytes are a valid key, point or signature is
  libsecp256k1's answer to give, and an argument of the wrong size or
  form raises rather than being padded or reinterpreted into a valid one.
  The reasoning is in the README, under What the boundary checks
- **warnings are errors** (`filterwarnings`), because the spread of
  interpreters this package claims turns a deprecation into a breakage
- **a script under `.github/scripts` runs on Python 3.10.11**, which is
  older than any 3.10 a machine here is likely to have. cibuildwheel
  pins the macOS `cp310` to python.org's `python-3.10.11-macos11.pkg`
  and the Windows one to that same patch — 3.10.11 is the last 3.10
  python.org publishes an installer for — where a manylinux image
  carries a current patch instead, so a standard library keyword
  backported after it (`TarFile.extractall`'s `filter` arrived in
  3.10.12) is fatal on the macOS and Windows wheel jobs and fine on the
  Linux ones. No static check reaches it: mypy's `python_version` is a
  minor version and it refuses a patch, so nothing it can be aimed at
  tells 3.10.11 from 3.10.12. Nor does any check a branch has to pass:
  the wheel jobs that run the suite under `cp310` are narrowed on a pull
  request to one interpreter per image, which leaves the red for the
  push to `main`
- **the version is declared once,** in `pyproject.toml`, and
  `__version__` reads the installed metadata. Never bump it in an
  ordinary change: releases are cut by a maintainer following
  [RELEASING.md](./RELEASING.md), and `release.yml` checks the tag
  against it
- **a vendored submodule moves on purpose.** Bumping one is a change of
  what this package wraps and belongs in its own pull request, with what
  README.md's Versioning section says about that submodule's pin moved
  with it. Where the upstream cuts releases, as `secp256k1` does, the
  pin is the commit a release tag names, the version number tracks that
  release, and `RELEASE_NOTES.md` names it in the release the bump lands
  in; where the upstream cuts none, as `secp256k1-zkp`, the pin is a
  commit no tag names, reviewed against the one it replaces, and there
  is no version for either file to carry. Dependabot signals upstream
  movement but tracks the upstream default branch, so its pull request
  says that a bump is available and not which commit to pin

### What gates a merge, and what only reports

`.pre-commit-config.yaml` is the single definition of what "clean" means,
and the `lint` workflow runs that very file, so what CI enforces is what
the local gate enforces. Never add a check that exists only in a
workflow, and never leave a hook weaker locally than on a runner: a hook
that needs a tool the developer may not have carries it in
`additional_dependencies`, which is why `actionlint` ships `shellcheck-py`
and `zizmor` is a `local` hook pinned to a version. A check discovered by
CI after a push is a check in the wrong place.

The aggregate of `test`, the `lint` job and the documentation build are
the required checks, and `REPOSITORY.md` reads that rule back from the
endpoint rather than restating it. `release` reuses all three. Everything
else reports: a sentinel opens no issue when it fails, `vendored-vectors`
excepted for the reason its own header gives, because each is expected to
go red for something no pull request introduced and a red check nobody
can act on from a branch is noise.

<!-- markdownlint-disable MD013 -->

| workflow | when | what it varies |
| --- | --- | --- |
| `test` | pull request, push | the wheels, the sdist, one suite cell |
| `lint`, `docs` | pull request, push | — |
| `claude-review` | pull request, and `@claude` in a comment | — |
| `vendored-vectors` | weekly, a pull request touching what it reads | — |
| `codeql` | pull request, push to main, weekly | the two scanned languages |
| `scorecard` | push to main, weekly | — |
| `os-ubuntu` | weekly, a release | both ubuntu images × every interpreter |
| `os-macos` | weekly, a release | both macOS images × every interpreter |
| `os-windows` | weekly, a release | both Windows images × every interpreter |
| `deps-latest` | weekly | the dependencies, at their newest |
| `links` | weekly, a pull request touching its own configuration | — |
| `mutation` | weekly | — |
| `wheel-reproducibility` | weekly, a pull request touching what it builds | every wheel platform, on two images, built twice on each, and the repaired, dynamic and cross-compiled wheels, built twice on one image per platform |
| `pypi-install` | weekly, a release | what PyPI serves |
| `release` | a tag | calls the gates and the rows marked *a release* |

<!-- markdownlint-enable MD013 -->

The first two rows are what a merge waits for, and the suite cell among them
is one: `ubuntu-latest` on the interpreter `.python-version` pins, measured
for coverage. Which day each of the rest runs, and at which minute, is
section 10 of the organization standard in `btclib-org/.github` and not this
file's to restate — one calendar covering the organization is one thing to
remember, and a copy of it per repository is one more thing to keep true in
each.

Why so little gates is one number: the ceiling the plan puts on how many
jobs the organization may run at once, shared across every repository in
it, which `REPOSITORY.md`'s *Plan-gated settings* holds beside the command
that re-derives it. A
commit here, in bitcoin-core-rpc and in one more repository each ask for
more jobs than that ceiling alone allows, so a pull request in any of the
three spent its wall clock waiting for a slot. At that ceiling a cell
before a review buys a rarer answer at the price of every review: macOS
runners queue for tens of
minutes rather than for two, and the twenty-one Windows suite cells were
27.3 of a run's 112.9 runner-minutes, the largest family of jobs in it and
ahead of every wheel build. The numbers are in `test.yml`'s header.

**What the sentinels vary, they vary whole.** `os-ubuntu` runs both images
on every interpreter, the cell the gate already covers included. A matrix with
the gate's cell cut out of it is one nobody can read the shape of, and
whoever asked what ran would have to re-derive the hole from the gate.

**Every image still builds wheels on every pull request**: `cibuildwheel`
runs the suite against each wheel as it builds it, and the release publishes
the artifacts of a run that built every one. What narrows on a branch is how
many per image — one interpreter's rather than every interpreter's, ubuntu
included — because what a pull request asks of an image is whether this tree
still builds there, and the toolchain, the CMake build of the vendored
library and the cffi extension are what differ per image rather than per
interpreter. Nothing on a branch reads past that first build: `check-dist`
installs one wheel by path and takes it from `build-dynamic`, which builds
whole. `test.yml` carries the measurement beside the step.

What a pull request no longer asks is pip's *selection* among a directory of
wheels tagged for several interpreters, which now runs nowhere; the wheel
each interpreter would get is still tested by the job that builds it, and
`os-ubuntu`, `os-macos` and `os-windows` still compile both linkages from
the tree on every interpreter. What no run asks at all is the suite
against the dynamic wheel as a package — the sentinels compile that
linkage from the tree instead. `os-ubuntu.yml`'s header records both
costs beside each other.

Every workflow here takes `workflow_dispatch`, the gates included, except
`claude-review` and `scorecard`, and for the three platform workflows it is
the only way to ask about a branch at all. Both of `claude-review`'s jobs
read the pull request or the comment that triggered them, so a manual run
would start with nothing to read. `scorecard`'s triggers are its action's
rather than this organization's: `ossf/scorecard-action`'s own README names
push and schedule on the default branch as what it supports, and calls
`workflow_dispatch` experimental.

`codeql` runs on a pull request as well as on `main` and its weekly
schedule, and none of the three makes it a gate: nothing requires the
result, and REPOSITORY.md is where the rule that could is read back from
the endpoint. What the pull-request trigger buys is that such a rule has a
name to hold — one aggregate over the matrix rather than one context per
language — at the price of those cells on every push to a branch.
There is no local command for it either: reproducing it means the CodeQL
CLI, a bundle GitHub distributes rather than a dependency `uv.lock` can
pin, so what answers a finding is the run itself and the Security tab
beside it.

`scorecard` gates nothing and could not: it runs on `main` and on its
weekly schedule, so there is no pull request run for a branch rule to
name. It has no local command either — the score is the action's, and
`README.md`'s badge reads it back from the API that serves it — and what
the run finds arrives as code scanning alerts beside CodeQL's. Which
repositories of the organization run it at all is section 10 of the
standard, this one among them.
