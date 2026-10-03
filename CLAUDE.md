# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

Python bindings to a vendored [libsecp256k1](./secp256k1/), built from
source. The package is thin: the cryptography is upstream, and what lives
here is the wrapping, the argument validation at the cffi boundary, and
the packaging — one wheel per platform and linkage, which is where most of
the complexity is. How many that comes to is a question for the release
that asks it, and `gh run view <id> --json artifacts` answers it; a number
here would be a line every matrix change has to edit, and nothing would
fail when it was not edited.

How to work here — what the issue tracker takes, the prose style, how a
pull request is opened and landed — is
[CONTRIBUTING.md](./CONTRIBUTING.md), which is the same file in every
repository of the organization up to its last section, that one holding
this tree's environment, its gate commands and which of its workflows
decide a merge. Reviewing is [REVIEWING.md](./REVIEWING.md), the same way
and with the same last section, and `/review` is that file as a command;
read it before reviewing a pull request and before opening one, since it
is what the pull request will be answered against. Repository
configuration — branch protection, required checks, token permissions,
publishing environments, Dependabot, secret scanning — is
[REPOSITORY.md](./REPOSITORY.md): read it before changing a workflow, a
branch rule or a setting.

The rest of the documentation, and none of it repeated here:

- [README.md](./README.md) — design, wrapped modules, build, and the
  static/dynamic/sdist distinction
- [RELEASING.md](./RELEASING.md) — the release, and the rehearsal
- [scripts/README.md](./scripts/README.md) — the build backend, one file
  at a time
- the comments in `.github/workflows/*.yml` and `pyproject.toml`, which
  carry the reasoning behind their choices

## Architecture

[ARCHITECTURE.md](./ARCHITECTURE.md) is the design: the two builds a
wheel can be, the module layout and the `_foo_` boundary convention, the
zkp subpackage, the vendored submodules and how they are compiled, and
how a release is produced and can be checked. Read it before touching
`src/btclib_secp256k1/__init__.py`, `scripts/cffi_build.py` or
`scripts/hatch_build.py`, and see the Design section of the README
before adding a module.

## The primary checkout is the maintainer's

Never work in it: no edit, no `git add`, no commit, no branch switch, no
rebase, no `git stash` — the hooks fix files in place. The one write
allowed there brings it forward, and only while it is on `main` and
`git status --porcelain` prints nothing; where it is not, stop:

```shell
checkout=<checkout>
```

```shell
git -C "${checkout:?}" pull --ff-only
```

Read it only after that, once this prints one sha twice:

```shell
git -C "${checkout:?}" rev-parse HEAD origin/main
```

A measurement that has to hold at a named revision reads
`git -C "${checkout:?}" show <sha>:<path>` instead.

Every session works in a worktree of its own, from its first edit, named
`wt-<tracker>-<issue>-<repo>-<role>` — `wt-github-255-btclib-writer` for
issue 255 of `btclib-org/.github`'s tracker, worked in `btclib` by a
writer. The environment is created there, with the command `CONTRIBUTING.md`
names under *The environment and the gates*. Every path is written out in
full, `<scratchpad>` being the session's scratch directory:

```shell
git worktree add \
  <scratchpad>/wt-<tracker>-<issue>-<repo>-<role> origin/main -b <branch>
```

Removing it is part of finishing:

```shell
git worktree remove --force <scratchpad>/wt-<tracker>-<issue>-<repo>-<role>
```

`refs/stash` and the local `main` are shared by every worktree: never
`git stash`, and move `main` only by the `git pull --ff-only` above.

## The worktree's submodules

`CONTRIBUTING.md`'s *The environment and the gates* has the step a
worktree needs before `uv sync --locked`. Skipped, `git submodule
status` answers a leading `-` and the sync dies inside CMake naming the
empty `secp256k1/`. Half done, the lint gate's `submodules-checked-out`
hook names what is missing, and `check-sdist` passes where the primary
checkout has the submodule active (#612, #765). `secp256k1-zkp` is
initialized whether or not `BTCLIB_LIBSECP256K1_ZKP` is set (#605).

`--reference` to the primary checkout's submodule modules is declined:
it saves the clone but leaves the worktree's submodule without objects
of its own, so a `git gc` in the primary, or moving it, can break the
worktree. `git worktree remove --force` removes a worktree with
initialized submodules and leaves nothing for `git worktree prune`.

## Model

Default model: Sonnet; Opus for design decisions with conflicting
constraints. Do not use Fable unless instructed.

## Non-obvious facts that will otherwise waste a session

- **the settings that cannot be enabled are in REPOSITORY.md**, with the
  API call that shows each still off: the two secret-scanning extensions
  are the ones that answer a PATCH with 200 and change nothing. Do not
  spend a session rediscovering them
- **`schedule` fires only from `main`; `workflow_dispatch` runs the copy on
  the branch `--ref` names**, once its trigger exists on `main`, so a
  rehearsal of `release.yml` or a change to a sentinel is dispatchable from
  the branch that carries it
- **a hand-applied mutation of the same length can outlive its restore**
  through a `.pyc` whose mtime and size still match: use
  `PYTHONDONTWRITEBYTECODE=1`, with a passing baseline run before and a
  control run after. cosmic-ray sets that variable itself (#229), but still
  reads a stale `.pyc`
- **A red `pypi-install` means what users can install moved** (the index, a
  platform), not that the workflow broke; that is why it is a workflow of
  its own and not a job of `release`
- **`check-sdist` fails on an untracked file that neither `.gitignore` nor
  `pyproject.toml`'s sdist `exclude` covers**, with "SDist does not match
  git". `docs/_build/` is one: `.gitignore` has
  `build/`, and `git check-ignore -v docs/_build/x` prints nothing. Build the
  docs as `CONTRIBUTING.md` does, `docs/source docs/build/html`, and anything
  else outside the worktree
- **no local gate runs `check-wheel-contents`; only CI does**, in the
  `Check wheel contents` step of `test.yml`'s `check-dist` job and in
  `deps-latest.yml`. Neither `.pre-commit-config.yaml` nor `tests/`
  invokes it, so a change to what a wheel carries -- `license-files`,
  `scripts/hatch_build.py` -- meets its checks for the first time on the
  runner. Its W002, duplicate files, reads every member of the wheel,
  `.dist-info/licenses/` included, and `secp256k1/COPYING` and
  `secp256k1-zkp/COPYING` are byte-identical, so a `license-files`
  listing both is refused. Checking by hand is a wheel built with `uv
  build --wheel --out-dir` pointed outside the worktree, for the reason
  the bullet above gives, then `uv run --locked --only-group check
  check-wheel-contents <wheel>` run from the worktree's root: the tool
  finds `[tool.check-wheel-contents]` by searching the working directory
  and its parents, and run from elsewhere it reports the codes that
  table ignores
- **A new `CHANGELOG.md` entry takes its own `###` at the end of the open
  section**; the older theme headings there stay as landed
  (btclib-org/.github#586)
- **`wheel-reproducibility.yml`'s `across-images` job compares two
  kinds of pair, and holds only one of them to the whole archive.**
  `rebuild`'s wheels are a plain `uv build` on the runner, so each
  image's extension is compiled by that image's own compiler, which the
  binary names in its `.comment` section, its `LC_BUILD_VERSION` or its
  Rich header (#992). That step passes `--across-toolchains`, which
  leaves the extension's bytes and its `RECORD` row's hash and size out
  and still compares everything else byte for byte. `repaired`'s Linux
  wheels are compiled in the pinned container and compared whole, with
  `--across-images`
- **`markdownlint-cli2` is reachable only through `pre-commit`, not
  through `uv run --only-group lint` on its own.** It is a node hook
  rather than a member of the `lint` dependency group:
  `uv run --locked --only-group lint markdownlint-cli2 --fix
  CHANGELOG.md` dies with `error: Failed to spawn: markdownlint-cli2 /
  No such file or directory`, exit `2`. The invocation that reaches it
  is `uv run --locked --only-group lint pre-commit run markdownlint-cli2
  --files CHANGELOG.md`, which exits `1` with `files were modified by
  this hook` where the fixer repaired something — that exit is the
  fixer working, not a failure. It is also the repair for what the
  `merge=union` driver does to `CHANGELOG.md`
- **`pre-commit`'s own log names the sdist hook `check sdist`, with a
  space, though `.pre-commit-config.yaml`'s `id:` is `check-sdist`.** A
  `grep -c check-sdist` over a run's log answers `0` on a run where the
  hook passed, which reads as the hook never having run rather than as
  the hook succeeding; grep the display name, or read the region
- **`uv run --locked`'s build cache is keyed on the source tree, not on
  `BTCLIB_LIBSECP256K1_DYNAMIC` or `BTCLIB_LIBSECP256K1_ZKP`, so a venv
  already holding a flagged build serves that build back to every later
  measurement taken in the same environment.** `uv sync --locked` alone
  does not rebuild it — it reports the packages it checked and returns,
  and `import _btclib_secp256k1_zkp` still succeeds afterwards. Nothing
  fails and nothing warns: the signal is the suite's own `passed`/
  `skipped` counts, which move by exactly the `zkp`-marked tests, and a
  session that does not know what they should read reads the flagged
  run as a better result. Any local measurement that alternates linkages
  in one environment needs `--reinstall-package btclib-secp256k1
  --no-cache` between builds
- **A new `raise RuntimeError` in `src/` is written after reading the
  comment above `[tool.coverage.report]`'s `exclude_also` in
  `pyproject.toml`.** The pattern there excludes a raise by its text, so
  how the raise is written decides whether coverage counts it, and a
  session writing one in `src/` has no reason to open `pyproject.toml`
  on its own. That comment says which form a raise an input can reach
  takes, and `tests/coverage_exclusion_test.py`'s docstring says where
  that is checked and where it is not
- **`sysctl -n vm.loadavg` prints a decimal comma on the maintainer's
  Mac**, whose locale is Italian: `{ 5,29 9,43 8,02 }`. A load wait
  that compares the value as printed does not compare the load: zsh's
  `(( l < 20 ))` reads the comma as its comma operator and compares only
  the digits after it, passing at `45,10` and holding at `5,29`, and
  `[ "$l" -lt 20 ]` refuses the value with exit 2. `LC_ALL=C sysctl -n
  vm.loadavg` prints a decimal point, and so does piping the value
  through `tr , .`

## Conventions to match

Section 9 of the organization standard is the prose style and section 10
is what every workflow of the organization does; neither is re-listed
here, that standard's own *One fact in one place* being the reason.
`CONTRIBUTING.md`'s last section has the gates and the commands, and what
a change to these bindings has to satisfy.

What is left to this file is where this tree departs from section 10, or
holds something it does not reach. `actionlint` and `zizmor` are hooks
precisely so these stay true, and both must report zero findings.

- `concurrency` groups are named literally, and `github.ref` in a called
  workflow is the *caller's* ref, so a reusable workflow here also takes
  a `concurrency-suffix` input and `release.yml` passes one: without it a
  rehearsal dispatched on a branch shares a group with a push to that
  branch, and one cancels the other
- the rehearsal path rewrites the version in `pyproject.toml`, and the
  `dev-version` action that does it re-locks in the same step, so a uv
  command that installs from the lock passes `--locked`, the build steps
  after that action included; `CONTRIBUTING.md` lists the exceptions, and
  the action's own comment has the reasoning
- the packaging tools come from the pinned `check` group, not from `uvx`,
  which would fetch whatever the index holds when the job runs
- a hook that needs a tool carries it in `additional_dependencies`, with
  a version: unpinned it is whatever existed when each environment was
  built, and nothing ever moves it

## Verifying

The build matrix is expensive — tens of jobs compiling C — and this
package exists to behave identically everywhere, so a claim about it is
worth a command:

- run the thing. A local `pre-commit` pass is not evidence that CI passes
  if the runner has a tool this machine lacks
- when adding a check, hand it something bad and watch it fail
- prefer reading a log to predicting one: `gh run view <id> --log-failed`
- a claim about another repository, or about what a published version
  does, is measurable too: install it in an isolated environment and look
