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

One thing decides how this package behaves, and it is decided at import
time by `src/btclib_secp256k1/__init__.py`: `_load_lib` returns
`module.lib` when the extension has libsecp256k1 linked into it (a static
build) and otherwise `ffi.dlopen`s the shared object shipped beside it (a
dynamic, cffi ABI mode build). Only one of those two branches exists in a
given wheel, which is why `_load_lib` takes the module as an argument
rather than reading it from the enclosing scope: the branch this build
does not have is testable only with a stand-in, and that is how coverage
still reaches every line. Every question of the form "why does this differ
between platforms" comes back here.

Above it, one module per libsecp256k1 module wrapped: `dsa`, `ssa`,
`ecdh`, `recovery`, `ellswift`, `silentpayments`, plus `keys`, `xonly`,
`hashes`, `context`, `_scalar`, `_secret` and `_cdata` for what crosses
the boundary. No module is one call of another: `mult` had become that
-- `pubkey_from_prvkey` with a flag fixed -- and was folded into `keys`.

MuSig2 is deliberately *not* wrapped as a protocol: its two-round session
holds a secret nonce that cannot be reused, which belongs where the
signing state lives, in btclib. `musig.KeyAggCache` and `musig.Session`
are the one place this package holds a libsecp256k1 object with no
serialization to be one, and `musig.py`'s module docstring carries the
reasoning for taking that exception. See the Design section of the README
before adding a module.

Below it, `scripts/cffi_build.py` builds the vendored library with CMake
and then compiles the extension by one of three paths — static with
MSVC, static with the interpreter's own toolchain, or dynamic with no C
compiled at all — chosen by `BTCLIB_LIBSECP256K1_DYNAMIC`,
`BTCLIB_LIBSECP256K1_CROSS_COMPILE` and `CFFI_PLATFORM`.
`stubs/_btclib_secp256k1.pyi` is what lets strict mypy typecheck a
module that only exists after a build.

## The primary checkout is the maintainer's

**Never work in it.** No edit, no `git add`, no commit, no branch switch,
no rebase, no `git stash`, no `pre-commit run` — the hooks fix files in
place. It is the maintainer's window on the tree: whatever is open in
their editor, whatever they have half-staged, and the branch they are
looking at are theirs, and one working tree has one index and one HEAD to
lose. Reading it is fine — `git log`, `git show`, `git diff`, `gh`, and a
`git fetch`, which writes refs and leaves the work tree alone.

So a `grep` or a `Read` against the checkout's files answers for whenever
it was last brought forward, not for now. The read that cannot go stale
is `git show origin/main:<path>`: it answers from the ref `git fetch`
just moved, never from the tree. Where the checkout has to be current
rather than merely readable, a fast-forward of a clean `main` brings it
up:

```shell
git fetch origin && git merge --ff-only origin/main
```

That writes no commit, switches no branch and runs no hook, so it is on
the permitted side of *never work in it*, not an exception to it. Stop if
the checkout is not on `main` or is not clean: that is no longer bringing
it forward.

**Every session works in a worktree**, its own, from the first edit,
named `wt-<tracker>-<issue>-<repo>-<role>` rather than after the issue
alone. `tracker` is the repository whose issue tracker holds the issue:
an issue number is unique only within one tracker, so
`btclib-org/.github#45` and `btclib-org/btclib#45` are different issues
that would otherwise name the same worktree. `issue` is what prevents
the collision that has actually happened — two worktrees of different
work sharing a generic basename in one repository's own `.git`, keyed on
its path's basename. `repo` prevents a different collision, a *path*
one rather than a `.git` one: two repositories each keep their own
`.git/worktrees/<basename>` and cannot collide there, but the workers of
one session share one scratchpad directory, so a session carrying one
issue into several repositories computes the same target path for each
of them, and `git worktree add` refuses a directory that already
exists — or worse, a second worker reads the first one's tree; naming it
this way also sorts every worktree of one issue together. `role` covers
the narrower case of a coder and its reviewer holding a worktree at
once, which the ordinary sequence avoids by each removing its own.

An issue in `btclib-org/.github`'s tracker, worked in `btclib-secp256k1`
by a coder, names its worktree `wt-github-255-btclib-secp256k1-coder`. A
worktree isolates files, and a submodule is a checkout of its own that it
does not inherit, which is why `git submodule update --init` follows the
`cd`; `uv sync --locked` after it is a second venv and a second build of
the extension, minutes rather than seconds. The editing, the gates and
the commits all happen in the worktree before the push.

```shell
WT=<scratchpad>/wt-<tracker>-<issue>-<repo>-<role>
git worktree add "$WT" origin/main -b <branch>
cd "$WT"
git submodule update --init
uv sync --locked
git push origin HEAD:refs/heads/<branch>
```

`--init` with no path initializes every submodule `.gitmodules` lists,
`secp256k1-zkp` (btclib-org/btclib-secp256k1#604) alongside `secp256k1`
-- naming `secp256k1` alone, as an earlier revision of this recipe did,
leaves `secp256k1-zkp` uninitialized, and nothing in the gates says so:
`check-sdist` reads `git ls-files`, which reports an uninitialized
submodule as its own single gitlink rather than as the files under it,
so the sdist it builds ships neither directory's content and still
answers "SDist matches git" (btclib-org/btclib-secp256k1#612, reproduced
against `secp256k1` alone and so not this branch's own defect to carry).
That the build does not yet read `secp256k1-zkp`
(btclib-org/btclib-secp256k1#605 is what first does) is not the same
question as whether the sdist gate does.

`-b <branch>` sits after the path and the commit-ish so that the
placeholder ends the command, which is section 9 of the organization
standard's rule. With the placeholder ahead of `"$WT"` the `>` closing
it takes that path as its target, and a path with no directory at it is
a file the paste creates.

Removing the worktree is part of finishing, and it stands in a block of
its own: the block above ends in a placeholder, and a shell that
discards that line as a parse error reads the next as a fresh command —
which, in one block, is this line against whatever `$WT` already held.
Standing alone it is a second fence, so `${WT:?}` is what it writes:
with no `$WT` set the expansion fails and the removal does not run.

```shell
git worktree remove --force "${WT:?}"
```

The venv, the C build and a clone of each submodule are the whole of the
cost, and they buy the thing that matters: a commit cannot contain work
that was never in it, and the maintainer's branch does not move under
them. The clone is the third of those because a linked worktree gets a
submodule module of its own per submodule rather than sharing the
primary checkout's — `secp256k1/.git` there reads `gitdir:
…/.git/worktrees/<wt>/modules/secp256k1`, `secp256k1-zkp/.git` the same
one directory over — which was measured at 14 MB and 13 MB respectively
under `.git/worktrees/<wt>/modules`, 7 MB of tree each. `--reference`
against the primary's own module is what a session asks about next, one
invocation per submodule, each against that submodule's own path under
the primary's `.git/modules/`: `git submodule update --init --reference
<primary>/.git/modules/secp256k1 secp256k1` leaves the module directory
exactly where git puts it, writes one `objects/info/alternates` pointing
at the primary's `objects`, and measures **128 KB** against those 14 MB,
with the primary's own `core.worktree` untouched and its submodule
clean. The same command against `secp256k1-zkp` needs the primary
checkout to already carry a `secp256k1-zkp` module of its own to
reference — true once the primary has been brought forward past
btclib-org/btclib-secp256k1#604 and had `git submodule update --init
secp256k1-zkp` run in it once, and not before: asked of a primary still
on `main` before that, it fails outright with "reference repository …
is not a local repository" rather than falling back to a plain clone,
measured by trying it. What `--reference` costs, once it works, is the
pointer: the worktree's submodule then has no copy of its own objects,
so a `git gc` or a repack in the primary — or moving or deleting it —
can leave this one unable to find them. What git is keeping apart by
giving each linked worktree a module of its own is the submodule's
*state*, so that two worktrees can have it checked out at two commits;
the object store sitting inside that module is a consequence of where
the state lives rather than a refusal to share objects, which is why
`--reference` is allowed to share them and why it changes nothing about
`core.worktree`. For a recipe whose last line removes the worktree
anyway that is a trade worth declining, and declining knowingly is the
point of the paragraph.

**The submodule line is what makes the rest of the recipe run**, and
leaving it out costs a session rather than a build: `git submodule status`
answers a leading `-` in a fresh worktree, and `uv sync --locked` then dies
inside CMake naming the empty `secp256k1/` and closing on "Build failures
usually indicate a problem with the package or the build environment" —
the two things that are not wrong. CI never meets it, every checkout there
passing `submodules: true`. It is the same sentence as the one below about
`refs/stash`: a worktree isolates files, and neither a submodule checkout
nor a ref is one.

**Two things the recipe leans on, both measured rather than assumed**, and
worth knowing because a submodule inside a linked worktree is a known sharp
edge. `core.worktree` in `.git/modules/<name>/config` is a single value, so
a second checkout of one submodule can rewrite it under the first — and
does not here, git giving the linked worktree its own module: the primary's
`core.worktree` still reads `../../../secp256k1` and `git -C secp256k1
status` there stays clean through the whole sequence. And `git worktree
remove --force` still finishes with an initialized submodule inside: exit
0, tree gone, `.git/worktrees` gone with it, nothing left for
`git worktree prune`. So the recipe's last line needs no companion.

**Never `git stash`, in the primary checkout or in a worktree:
`refs/stash` is shared.** A worktree isolates files, not refs, so
`git stash push` pushes onto the same stack every other session pops
from — and on a clean tree it creates nothing, so the `git stash pop`
that follows applies and *drops* whatever another session shelved. Commit
to your own branch instead. What is already lost is still in the object
store: `git fsck --unreachable` names the commit and `git stash store
<sha>` puts the ref back.

**`git checkout -- <file>` is the other way to lose work**, and it does it
quietly: it restores from the index, so an edit made and not staged is
gone with no output at all. Reverting a deliberate experiment is what a
copy is for — `cp file file.bak`, then put it back.

## Model

The default model for this repository is Sonnet. Switch to Opus only
for architectural decisions with conflicting constraints -- design
choices with non-obvious trade-offs, refactors with unclear
dependencies, diagnosis where the symptom does not point to the
cause. Use `/model opus` for the session, then switch back to Sonnet.

Do not use Fable unless explicitly instructed.

## Non-obvious facts that will otherwise waste a session

- **the settings that cannot be enabled are in REPOSITORY.md**, with the
  API call that shows each still off: the two secret-scanning extensions
  are the ones that answer a PATCH with 200 and change nothing. Do not
  spend a session rediscovering them
- **`schedule` here is inert off `main`; `workflow_dispatch` is not**:
  cron fires only from the default branch, but `workflow_dispatch` only
  needs its trigger to exist on `main` for the workflow to be
  dispatchable at all, and `--ref` then picks which branch's copy of the
  file runs — so a rehearsal of `release.yml`, or a change to
  `os-macos.yml`, `deps-latest.yml` or another sentinel, is dispatchable
  from the branch that carries it and runs that branch's own copy before
  either lands. Only a workflow that has never landed on `main` is
  reachable through nothing at all until it does
- **a hand-applied mutation can outlive its restore.** `(0, 1, 2, 3)` and
  `(0, 1, 1, 3)` are the same length, so restoring the file with `cp` in the
  same second leaves mtime *and* size matching what the `.pyc` recorded, and
  python reuses the mutated bytecode — silently, in the next unrelated run.
  `PYTHONDONTWRITEBYTECODE=1`, with a passing baseline run before and a
  passing control run after, is what makes a hand verification mean
  anything. **cosmic-ray does not have the problem, and the mechanism is
  worth naming rather than trusting** (#229): `cosmic_ray/testing.py`
  sets that very variable in the environment of the test command, under a
  comment giving this reason, so a session writes no `.pyc` at all — the
  baseline included, both measured by looking at `__pycache__` before and
  after a real `cosmic-ray exec`. Grepping the package for
  `dont_write_bytecode` finds nothing and means nothing: the string it
  sets is the environment variable's own spelling. What no flag stops is
  a *read*, so a `.pyc` already on disk from an earlier `pytest` is still
  used where its size and truncated mtime match — which is the same
  window as above, and the reason the hand recipe wants the control run
  and not only the variable
- **a mutation session mutates the source in place and restores it**, so
  nothing else may read the tree while one runs: no second session, no
  `pytest` in another shell, and a `git status` in the middle is a
  working tree with a mutant in it. `cosmic-ray baseline` comes first,
  always — without it a stale test command fails every mutant
  identically and the session reports a perfect kill rate, which is the
  one failure mode of a mutation run that looks like good news
- **the `pypi-install` workflow went green with 0.7.1**, on 4 August
  2026, nineteen cells out of nineteen, having been nineteen out of
  nineteen red the day before: 0.4.0 had no arm64 wheel and its sdist no
  longer built, so that red was a fact about what users could install
  rather than a broken workflow. A red there still means the outside
  world moved, which is why it is a workflow of its own and not a job of
  `release`
- **`check-sdist` compares the sdist it builds against `git ls-files`,
  not against `git status`.** An untracked directory left inside a
  worktree -- a wheel built there for manual verification, or a
  `pytest --basetemp` pointed at the worktree instead of outside it,
  both do it -- is swept into that build and fails the hook with "SDist
  does not match git", even though `git status --porcelain` reports the
  tree clean: an untracked file passes that check silently and still
  breaks this one. The fix is not rerunning the hook; it is not leaving
  such a directory inside the worktree in the first place, or building
  it somewhere else entirely
- **the merge API queues behind the required checks even for a pull
  request that touches no workflow file.** `gh api -X PUT .../merge` on
  a pull request touching no workflow file -- `pyproject.toml`, source
  and tests, no CI configuration -- returned a transient `502`, then
  `405 Merge already in progress`, and stayed unmerged until all three
  required contexts -- `Lint and type-check`, `Build the documentation`,
  `test: every job passed` -- reported: the full matrix triggers on the
  push regardless of which file changed. The bypass a `pull_request`
  ruleset's `bypass_actors` entry grants covers the review requirement,
  not those checks. `gh pr checks <n>` naming the three, not a retried
  merge call, is what says whether it is time to try again
- **A `###` in the open section names one entry, never a theme several
  entries share** (issue btclib-org/.github#586). Section 9's
  `CHANGELOG.md and RELEASE_NOTES.md` makes grouping by theme the
  rejected alternative, and this tree's open section carries headings
  from before that rule which do group several entries under one theme.
  Such a heading is landed text and stays exactly as it is (*Nothing
  already written is rewritten*, same subsection); a new entry never
  joins one, but takes its own `###` at the end of the open section,
  naming only that entry. Which of the headings there are themes and
  which are one entry whose bullets cite separately is a reading of what
  sits under them, not a list to be kept here: section 9 says an entry's
  bullets are separate facts and cite separately, so several citations
  under one `###` are no evidence of a theme
- **`wheel-reproducibility.yml`'s `across-images` job is red by design;
  only its Linux-repaired half is a claim about this tree.** `rebuild`
  builds the wheels its *Diff the wheels two images of one platform
  built* step compares with a plain `uv build` on the runner, entering
  no container, so what disagrees is the host image's own toolchain —
  `RELEASING.md`'s rebuild section already gives other bytes from a
  rebuild outside the image that built the original as the expected
  outcome. That step is `failure` on runs of branches unrelated to it
  (`33788435813`, `33784301251`, `33756652274`), the disagreement
  identical across them — `linux-aarch64`'s extension module at
  `1819920 vs 1875352 bytes, crc32 5ebec3ee vs 2f8938f0` on every one.
  In a dispatched run of the same job (`33811045142`) the *Diff the
  repaired wheels two images of one Linux platform built* step, added
  by #524, compares the `cibuildwheel`-repaired wheels built inside the
  pinned container instead, and answers `linux-x86-64: its images
  agree, member for member` — that is the half a red job still has to
  keep green
- **`markdownlint-cli2` is reachable only through `pre-commit`, not
  through `uv run --only-group lint` on its own.** It is a node hook
  rather than a member of the `lint` dependency group:
  `uv run --locked --only-group lint markdownlint-cli2 --fix
  CHANGELOG.md` dies with `error: Failed to spawn: markdownlint-cli2 /
  No such file or directory`, exit `2`. The invocation that reaches it
  is `uv run --locked --only-group lint pre-commit run markdownlint-cli2
  --files CHANGELOG.md`, which exits `1` with `files were modified by
  this hook` where the fixer repaired something — that exit is the
  fixer working, not a failure. It is the one automated repair for what
  the `merge=union` driver does to `CHANGELOG.md`, below
- **`pre-commit`'s own log names the sdist hook `check sdist`, with a
  space, though `.pre-commit-config.yaml`'s `id:` is `check-sdist`.** A
  `grep -c check-sdist` over a run's log answers `0` on a run where the
  hook passed, which reads as the hook never having run rather than as
  the hook succeeding; grep the display name, or read the region
- **The control for an empty Actions variable store here is the
  organization endpoint, not the repository's.**
  `repos/btclib-org/btclib-secp256k1/actions/variables` and
  `.../actions/secrets` both answer `total_count: 0`, so neither
  controls the other — an endpoint that answers zero for every
  repository measures nothing. `gh api orgs/btclib-org/actions/secrets`
  answers `total_count: 1` (`CLAUDE_CODE_OAUTH_TOKEN`, visibility
  `all`), which is what makes `gh api orgs/btclib-org/actions/variables`
  answering `total_count: 0` a real absence rather than an endpoint
  nobody populates. Organization level is also where to ask in the
  first place: `CLAUDE_REVIEW_ENABLED`, `claude-review.yml`'s own
  switch, is an organization variable
- **The `merge=union` driver's blank-line damage to `CHANGELOG.md` is
  invisible to `git diff --numstat` and to `git rebase`'s own exit
  code.** Where a rebase's two sides both append at the end of the open
  section, the driver keeps the order right and eats only the single
  blank line above the later `###` — `git diff --numstat` reports the
  change as a pure addition with no deleted line, and `git rebase`
  exits `0`. What finds it is reconstructing the file from the new
  base's own blob with the branch's own block spliced back in and
  comparing byte for byte; the `markdownlint-cli2` `pre-commit` hook
  above is what repairs it, since the bare `uv run --only-group lint`
  invocation cannot reach the tool at all

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
  `dev-version` action that does it re-locks in the same step, so every
  uv command here passes `--locked` with no exception, the build steps
  after that action included; the action's own comment has the reasoning
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
- when adding a check, hand it something bad and watch it fail. Every hook
  here was verified that way
- prefer reading a log to predicting one: `gh run view <id> --log-failed`
- read exit codes, not filtered output: `… | grep -v Passed` is a habit
  that eventually reports a failure as a success
- a claim about another repository, or about what a published version
  does, is measurable too: install it in an isolated environment and look
