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
signing state lives, in the library downstream of these bindings.
`musig.KeyAggCache` and `musig.Session` are the one place this package
holds a libsecp256k1 object with no serialization to be one, and
`musig.py`'s module docstring carries the reasoning for taking that
exception. See the Design section of the README before adding a
module.

Below it, `scripts/cffi_build.py` builds the vendored library with CMake
and then compiles the extension by one of three paths — static with
MSVC, static with the interpreter's own toolchain, or dynamic with no C
compiled at all — chosen by `BTCLIB_LIBSECP256K1_DYNAMIC`,
`BTCLIB_LIBSECP256K1_CROSS_COMPILE` and `CFFI_PLATFORM`.
`stubs/_btclib_secp256k1.pyi` is what lets strict mypy typecheck a
module that only exists after a build.

## The primary checkout is the maintainer's

**Never work in it.** No edit, no `git add`, no commit, no branch
switch, no rebase, no `git stash` — the hooks fix files in place. It is a
local reference only, and it stays on `main`.

Reading it is fine, but `git fetch` moves `refs/remotes/origin/main` and
leaves the work tree where it was, so a `grep` or a `Read` against the
checkout answers for whenever it was last brought forward, not for now.
The read that cannot go stale is `git show origin/main:<path>`: it
answers from the ref `git fetch` just moved, never from the tree.

Where the checkout has to be current rather than merely readable, a
fast-forward of a clean `main` brings it up:

```shell
git fetch origin && git merge --ff-only origin/main
```

That writes no commit, switches no branch and runs no hook, so it is on
the permitted side of *never work in it*, not an exception to it. Stop
if the checkout is not on `main` or is not clean: that is no longer
bringing it forward.

**Every session works in a worktree**, its own, from the first edit, named
`wt-<tracker>-<issue>-<repo>-<role>` rather than after the issue alone, most
general part first: an issue filed in `btclib-org/.github`'s tracker is the key
and the repository is a detail of it — `btclib-org/.github#255` is one issue
owed by seven repositories, `btclib-org/.github#177` by two — so the repository
is what varies underneath an issue rather than the other way round, which is why
`repo` comes after `issue`. Naming it that way also sorts every worktree of one
issue together, which is what a port leaves behind.

Each of the four parts earns its place against a different collision,
and none of them is the same collision. `tracker` is the repository
whose issue tracker holds the issue: an issue number is unique only
within one tracker, so `btclib-org/.github#45` and
`btclib-org/btclib#45` are different issues that would otherwise name
the same worktree. `issue` is what prevents the collision that has
actually happened — two worktrees of different work sharing a generic
basename in one repository's own `.git`, keyed on its path's basename.
`repo` prevents a different collision, a *path* one rather than a `.git`
one: two repositories each keep their own `.git/worktrees/<basename>`
and cannot collide there, but the workers of one session share one
scratchpad directory, so a session carrying one issue into several
repositories computes the same target path for each of them, and `git
worktree add` refuses a directory that already exists — or worse, a
second worker reads the first one's tree. `role` covers the narrower
case of a coder and its reviewer holding a worktree at once, which the
ordinary sequence avoids by each removing its own.

An issue of `btclib-org/.github`'s tracker, worked in `btclib` by a coder, names
its worktree `wt-github-255-btclib-coder`. The environment is created in the
worktree, not the checkout, by whatever that tree's own `CONTRIBUTING.md` names
under *The environment and the gates*, and a session reads that section, not
this one, for the command. The editing, the gates and the commits all happen in
the worktree before the push.

```shell
WT=<scratchpad>/wt-<tracker>-<issue>-<repo>-<role>
git worktree add "$WT" origin/main -b <branch>
git -C "$WT" push origin HEAD:refs/heads/<branch>
```

`-b <branch>` sits after the path and the commit-ish so that the placeholder
ends the command, which is section 9 of `btclib-org/.github`'s rule. With the
placeholder ahead of `"$WT"`, its `<` and its `>` are redirections performed
left to right, so the `>` is reached only where the reader's own directory
already holds the name `branch`: there the `<` succeeds, the line runs, and the
`>` takes `"$WT"` as its target — a path with no directory at it is the file it
creates. Ordinarily nothing holds that name, so the `<` fails first (`no such
file or directory: branch`) and the line ends before the `>` opens anything.

The push names the worktree with `git -C "$WT"` because a `cd` binds the
shell that runs it: a session that runs each line as its own command
starts the next one in the directory it began in, the primary checkout,
so a push after a `cd` offers that checkout's `HEAD` instead of the
worktree's. `env -C <dir>` is the same binding for a command that takes
no `-C` of its own. Neither binding rescues the assignment above it: a
session that loses the `cd` loses `WT` with it, and `git -C ""` is
documented to leave the working directory unchanged, so that push lands
the same way, exit 0 and no diagnostic. That silence is `git`'s rather
than the binding's: the BSD `env` macOS ships documents no case for an
empty `-C` and refuses one — `cannot change directory to ''`, exit 125 —
so a line bound with `env -C` stops there instead of running against the
wrong tree. What the `-C` buys is a path that can be written out in
full; write it out.

Removing the worktree is part of finishing, and it stands in a block of
its own: the block above ends in a placeholder, and a shell that
discards that line as a parse error reads the next as a fresh command —
which, in one block, is this line against whatever `$WT` already held.
Standing alone it is a second fence, so `${WT:?}` is what it writes:
with `$WT` unset or empty the expansion fails and the removal does not
run. Those are the only cases it catches — a `$WT` an earlier session or
command left holding a path expands, and the removal runs against
whatever worktree that path names.

```shell
git worktree remove --force "${WT:?}"
```

**Never `git stash` in a worktree either: `refs/stash` is shared.** A
worktree isolates files, not refs, so `git stash push` pushes onto the
same stack every other session pops from. Commit to your own branch
instead.

**Do not rewrite `refs/heads/main`, and move it only onto
`origin/main`.** That name is the local branch's, and no ruleset reaches
it: a ruleset binds the forge's copy. The fast-forward above moves it
onto `origin/main` and is inside that, where a merge, a commit on `main`
or an `update-ref` to a branch tip leaves the ref somewhere
`origin/main` is not. Your own branch is what you push, and the pull
request is what moves `origin/main`.

## The worktree's submodules

The environment step *The environment and the gates* names is two
commands here, `git submodule update --init` and then `uv sync --locked`:
a worktree isolates files, and a submodule is a checkout of its own that
it does not inherit; the sync after it is a second venv and a second
build of the extension, minutes rather than seconds.

`--init` with no path initializes every submodule `.gitmodules` lists,
`secp256k1-zkp` (btclib-org/btclib-secp256k1#604) alongside `secp256k1`
-- naming `secp256k1` alone, as an earlier revision of this recipe did,
leaves `secp256k1-zkp` uninitialized, and the lint gate is what says
so: `.pre-commit-config.yaml`'s `submodules-checked-out` hook looks for
a `.git` of its own under every path `.gitmodules` names and exits 1
naming each one missing, so `uv run --locked --only-group lint
pre-commit run --all-files` -- which installs no project and needs
nothing built -- fails on a half-initialized worktree. `check-sdist` is
the gate that does not say so: it compares the sdist it builds against
`git ls-files --cached --recurse-submodules`, and that command drops
the gitlink of a submodule the repository has configured active whose
directory is empty, so the missing tree is absent from both sides of
the comparison and the answer is still "SDist matches git"
(btclib-org/btclib-secp256k1#612). A worktree is in that state until
`git submodule update --init` runs in it: `.git/config` is the primary
checkout's, so `git -C "$WT" config --get-regexp '^submodule\.'`
answers `active true` for each submodule from the moment the worktree
exists. The activation is what the drop needs rather than the empty
directory (btclib-org/btclib-secp256k1#765): a checkout that never
registered the submodule has its gitlink listed like any other cached
entry, which is the state a plain `git clone` leaves and the one
`check-sdist` fails on rather than passing. A claim about the gates
names the gate and the command that decides it: they do not move
together, and one of them learning something falsifies a sentence
written about all of them. The build compiles `secp256k1-zkp` where
`BTCLIB_LIBSECP256K1_ZKP` is `true` (btclib-org/btclib-secp256k1#605),
which is a different question from what the sdist gate sees: a build
that leaves the flag unset is no reason to leave the submodule
uninitialized.

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

**`git submodule update --init` is what makes `uv sync --locked` run**,
and leaving it out costs a session rather than a build: `git submodule
status` answers a leading `-` in a fresh worktree, and `uv sync --locked`
then dies inside CMake naming the empty `secp256k1/` and closing on
"Build failures usually indicate a problem with the package or the build
environment" — the two things that are not wrong. CI never meets it,
every checkout there passing `submodules: true`. It is the same sentence
as the one above about `refs/stash`: a worktree isolates files, and
neither a submodule checkout nor a ref is one.

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
  required contexts -- `lint / Lint and type-check`,
  `docs / Build the documentation`, `test: every job passed` -- reported:
  the full matrix triggers on the push regardless of which file changed.
  The bypass a `pull_request` ruleset's `bypass_actors` entry grants
  covers the review requirement, not those checks. `gh pr checks <n>`
  naming the three, not a retried
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
  first place: `CLAUDE_REVIEW_ENABLED`, the switch the workflow
  `claude-review.yml` calls reads, is an organization variable
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
- **`uv run --locked`'s build cache is keyed on the source tree, not on
  `BTCLIB_LIBSECP256K1_DYNAMIC` or `BTCLIB_LIBSECP256K1_ZKP`, so a venv
  already holding a flagged build serves that build back to every later
  measurement taken in the same environment.** `uv sync --locked` alone
  does not rebuild it — it reports the packages it checked and returns,
  and `import _btclib_secp256k1_zkp` still succeeds afterwards. Nothing
  fails and nothing warns: the signal is the suite's own `passed`/
  `skipped` counts, which move by exactly the `zkp`-marked tests, and a
  session that does not know what they should read reads the flagged
  run as a better result. `CONTRIBUTING.md`'s coverage sequence states
  the same fact for its own three commands, but the cache does not know
  which command asked — any local measurement that alternates linkages
  in one environment needs `--reinstall-package btclib-secp256k1
  --no-cache` between builds, not only that one

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
