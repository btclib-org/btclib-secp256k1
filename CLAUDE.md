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
time by `btclib_secp256k1/__init__.py`: `_load_lib` returns
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

**Every session works in a worktree**, its own, from the first edit:

```shell
WT=<scratchpad>/wt<issue>
git worktree add -b <branch> "$WT" origin/main
cd "$WT"
git submodule update --init secp256k1  # a worktree isolates files, and a
                                       # submodule is a checkout of its
                                       # own that it does not inherit
uv sync --locked                       # a second venv, and a second build
                                       # of the extension: minutes, not
                                       # seconds
# edit, gate and commit here, then
git push origin HEAD:refs/heads/<branch>
git worktree remove --force "$WT" # removing it is part of finishing
```

The venv, the C build and a second clone of the submodule are the whole
of the cost, and they buy the thing that matters: a commit cannot
contain work that was never in it, and the maintainer's branch does not
move under them. The clone is the third of those because a linked
worktree gets a submodule module of its own rather than sharing the
primary checkout's — `secp256k1/.git` there reads `gitdir:
…/.git/worktrees/<wt>/modules/secp256k1` — which was measured at 14 MB
under `.git/worktrees/<wt>/modules` and 7 MB of tree. `--reference`
against the primary's module is what a session asks about next, and it
works: `git submodule update --init --reference
<primary>/.git/modules/secp256k1 secp256k1` leaves the module directory
exactly where git puts it, writes one `objects/info/alternates` pointing
at the primary's `objects`, and measures **128 KB** against those 14 MB,
with the primary's own `core.worktree` untouched and its submodule
clean. What it costs is the pointer: the worktree's submodule then has
no copy of its own objects, so a `git gc` or a repack in the primary —
or moving or deleting it — can leave this one unable to find them. What
git is keeping apart by giving each linked worktree a module of its own
is the submodule's *state*, so that two worktrees can have it checked
out at two commits; the object store sitting inside that module is a
consequence of where the state lives rather than a refusal to share
objects, which is why `--reference` is allowed to share them and why it
changes nothing about `core.worktree`. For a recipe whose last line
removes the worktree anyway that is a trade worth declining, and
declining knowingly is the point of the paragraph.

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
- **every `schedule` and `workflow_dispatch` here is inert off `main`**:
  both only run from the default branch, so a rehearsal of `release.yml`
  cannot be dispatched from a branch, and `os-macos.yml`,
  `deps-latest.yml` and the other sentinels are reachable there through
  nothing at all until merged
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
- uv commands pass `--locked`, never `--frozen` — except the wheel-build
  steps of `test.yml` (`build-cibuildwheel`, `build-dynamic`,
  `build-sdist`, the Windows cross-build), which run after the
  `dev-version` action has rewritten `pyproject.toml` on the rehearsal
  path; `--locked` refuses exactly that disagreement, so those steps use
  `--frozen`, and the comment above `build-cibuildwheel`'s `Build wheels`
  step has the reasoning in full
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
