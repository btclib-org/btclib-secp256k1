# Release process

Releases are published by the `release` workflow, which reuses the
`lint` gate and the whole `test` build and test pipeline, and then
uploads what the latter produced. Where it uploads is not an input to
choose at dispatch time: a `v*` tag publishes to PyPI, a manual run
publishes to TestPyPI. Both go through
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/), so no
long-lived token exists anywhere, and both upload PEP 740 attestations.
The `attest` job then signs a build provenance statement for the sdist,
which is the file the GitHub release attaches and therefore the one copy
the index's attestation says nothing about.

**No CycloneDX bill of materials is attached, on purpose.** This
package's `Requires-Dist` names only `cffi` — the dependency it
actually wraps, the vendored libsecp256k1 C library at its pinned
commit in the `secp256k1` submodule, does not appear there and so is
invisible to a generator that builds its components from
`Requires-Dist`. That holds for both wheels this package ships, not
only the static one: a static build links the library into the
extension, a dynamic (ABI-mode) build ships it as a shared object
beside the extension instead (see CLAUDE.md's Architecture section) —
`Requires-Dist` says nothing about the pin either way, so a document
built from it would look complete while staying silent about the one
component a verifier would most want described. That was the
generator's own limit rather than this package's, and it no longer
holds:
[btclib-org/btclib#1280](https://github.com/btclib-org/btclib/issues/1280)
taught a generator to read a submodule's pinned commit from its
`.gitmodules` entry and gitlink instead of from `Requires-Dist`. What
is still missing is adoption here, not a technical inability.
[btclib-org/.github#24](https://github.com/btclib-org/.github/issues/24)
stays open until that adoption lands; an issue no longer open watches
nothing.

The version published is the one in `pyproject.toml`; the tag only
decides which index is reached. The `version-check` job cross-checks
them, and runs before anything is built: a `v0.7.1` tag on a tree still
reading `0.7.1rc1` fails there, rather than burning `0.7.1rc1` on PyPI.
The same job checks that `uv.lock` carries the version the tree declares,
that the libsecp256k1 release named in `README.md` is the commit the
submodule is pinned to, that `RELEASE_NOTES.md` and `CHANGELOG.md` each
carry a section headed by the tag alone and not empty, and that the
tagged commit is on `main`. Every invariant a release rests on is
checked there, before the point of no return.

**Every `gh` call here names the repository**, rather than leaving `gh`
to resolve its `{owner}/{repo}` placeholder against whatever checkout the
shell stands in; REPOSITORY.md's opening has the reason at length. A
release is carried out from a checkout of this repository, so the
placeholder would answer correctly for whoever follows the steps top to
bottom, and what it does not survive is a step copied out and run
somewhere else — the merge call under "Cutting a release" is a `PUT`. A
block making several calls names the repository once, in `repo`; a call
standing alone in prose names it in full; a block making one call does
either, `repo` being what keeps a path too long for the margin off the
call itself; and a command named without the run or the pull request it
acts on is being referred to rather than called. That no placeholder is
left is checkable:

```shell
grep -n 'repos/{owner}/{repo}' RELEASING.md
```

which answers with that command's own line and with nothing else. The
placeholder form is all it reaches. `gh pr merge`, `gh run list` and
`gh run rerun` take the repository in a `--repo` flag that can simply
be absent, and a call omitting it leaves nothing for a grep to key on,
so that half of the convention is held to by reading rather than by
running anything.

## Which version string is which

Six strings here look like versions, and telling them apart is most of
what can go wrong:

- **`0.7.1`**, in `pyproject.toml`, is *the* version. It is what gets
  published, on either index, and the only one a human edits
- **`0.7.1.1`**, a fourth number on an already-final version, plays two
  roles this list would otherwise leave out: right after 0.7.1 ships,
  the step that opens the next version puts the tree on it as a
  placeholder, nothing having moved the submodule since to renumber
  it; and if 0.7.1 itself shipped broken,
  "When a release turns out to be broken" ships the very same string
  as the fix, tagged. Both are typed by hand, like `0.7.1` above, and
  both read the same way — "the same libsecp256k1, one change since" —
  whichever of the two prompted it
- **`v0.7.1`**, the tag, carries no version of its own: it picks the
  index, PyPI rather than TestPyPI, and `version-check` exists to
  confirm it says what `pyproject.toml` says, which is where the tagging
  step reads it from rather than typing it
- **`.dev<run><attempt>`** is not a version but what the
  `version-check` job computes, `run_number * 100 + run_attempt`. Only a
  `workflow_dispatch` run computes it, and the build jobs append it to
  what `pyproject.toml` declares. Nothing writes it down, and no commit
  ever carries it
- **`0.7.1.dev1`** is what the earlier `.dev<run number>` template
  produced the first time this workflow was dispatched, rehearsing
  0.7.1: `0.7.1` from `pyproject.toml`, and run number 1. A later
  dispatch's suffix is whatever the formula above computes for it then,
  not a value worth writing down here, since it moves with every
  dispatch. `github.run_number` counts the runs of `release.yml` alone,
  not of the repository, so it started at one
  and rises by one per dispatch; `github.run_attempt` starts at one and
  rises with each re-run of a single dispatch, which is what a run
  number alone could not tell apart. Between them every attempt of every
  rehearsal has a version of its own, and all of them sort below the
  release being rehearsed
- **`0.7.1rc1`**, and a `v0.7.1rc1` tag, are none of the above and have
  no place in this scheme. There are no release candidates here: what
  tells a rehearsal apart is generated by the run, not declared by the
  tree. The two ways of trying anyway fail differently, which is why
  `version-check` makes two checks and not one — declaring `0.7.1rc1` is
  refused for not being digits and dots, while tagging `v0.7.1rc1` on a
  tree declaring it would *pass* that comparison and take the
  pre-release to PyPI itself, where `--pre` installs would find it from
  then on

PEP 440 sorts `0.7.1.dev1` before `0.7.1`, so a rehearsal never shadows
the release it rehearses.

## Cutting a release

`deps-latest` is worth dispatching before the tag rather than waiting for its
cron, because what it answers is cheaper to know before a version is
consumed than after. It gates nothing, so it will not stop you: reading
it is the point. It resolves every dependency at its newest and then runs
the suite, the lint gate and the packaging checks; a release ships what
`uv.lock` pins, so a red run here does not make the release wrong — it
says the next dependency bump is going to be work, and that is worth
knowing before rather than during.

`mutation` is not: it asks whether the suite would notice a wrong line,
which a release does not change the answer to, and a session is measured
in minutes to hours against a schedule already built for the weekend it
runs on regardless. Dispatching it as part of cutting a release conflates
two independent activities for no question a release-timing answers. A
release pull request's own checklist is not exempt from that argument: an
item asking whether a mutation run is "owed" before marking it ready
reintroduces the same coupling under a different name, one more session
gating a button it does not answer anything for. 0.7.1.2 ran one anyway,
by hand and out of band — the weekly cron was days off and two merged
pull requests had changed wrappers a survivor list had not seen since —
and that is the right shape for it: read on its own terms, the sqlite
kept or discarded on its own schedule, never a condition of the tag.

Updating the pinned dependencies is a decision of the same shape, and
belongs here for the same reason: whether to run `uv lock --upgrade` (or
wait for Dependabot's own pull requests to catch up) is not itself a
release-timing question, `uv.lock` pinning what ships regardless of what
`deps-latest` resolved against. Unlike `mutation`, though, it is worth
deciding on purpose rather than defaulting by omission: `deps-latest`'s run
for 0.8.0.4 found ruff 0.16.3→0.16.4, stevedore 5.9.0→5.9.1 and pygments
2.20.0→2.21.0 already past what `uv.lock` pinned, with nobody having
chosen either way. State the choice — upgraded, or left as `deps-latest`
found it, and why — in the release pull request, the same line
`deps-latest`'s own result already gets.

Then:

1. bump the version in `pyproject.toml` and run `uv lock`, which carries
   it into `uv.lock`. Version numbers track the wrapped libsecp256k1,
   with a fourth number for a release of the bindings alone: see the
   Versioning section of [README.md](./README.md). The previous release
   left a fourth number open, by the step that opens the next version
   below, so this is often a matter
   of confirming what is already declared, or of renumbering it if the
   submodule has moved since
1. check the breaking-changes list against the API itself, which
   nothing else here does before the tag -- the run's own `public-api`
   job asks it again, red on a break and gating nothing, `release.yml`'s
   comment on that job saying why:

   ```shell
   uv run --isolated --no-project --with griffe \
       griffe check btclib_secp256k1 -s . -s src -a <previous release tag>
   ```

   `uv run` alone syncs the project first, which builds the bindings —
   cmake, the `secp256k1` submodule, the whole C library — and fails
   before griffe is ever reached in a fresh clone; griffe is static, it
   reads Python source and needs nothing built, so `--isolated
   --no-project` skips that build and `-s . -s src` points griffe at the
   package in the working tree instead of an installed one. Both search
   paths are wanted: `src` is where this tree keeps the package and `.`
   is where a release from before it moved under `src/` keeps it, so a
   comparison against such a tag loads neither side without the other —
   `release.yml`'s own griffe step carries the same pair and the same
   reason. The tag stands last, where the `>` closing it has nothing to
   open, which is what section 9 of the organization standard asks of a
   bare placeholder. It reports
   breakage alone — a public object removed, a parameter that changed
   kind or default or moved — and says nothing about an addition, so
   every line it prints wants an entry in `RELEASE_NOTES.md`. Discount
   `__init__.py: __version__: Attribute value was changed:
   version('btclib_secp256k1') -> unset` on sight and every time: not a
   break, `__version__` reading installed metadata through a lazy
   `__getattr__` that griffe's static read has nothing to compare
   against — `python -c "import btclib_secp256k1 as m;
   print(m.__version__)"` answers the real version regardless. The list
   of what else to discount is per release rather than inherited, the
   way a sibling repository's own griffe step names `Union[X, Y] -> X | Y`
   as PEP 604 spelling and nothing to act on.

   Measured rather than assumed: `v0.8.0.3` to `main` (0.8.0.4) reports
   nothing beyond the `__version__` line above, `musig` being purely
   additive; `v0.8.0.2` to `v0.8.0.3` reports 23 findings, matching what
   that release's own `RELEASE_NOTES.md` already named one by one, and
   is the positive control that says the command is reading the package
   rather than finding nothing (#291)
1. close the release notes. `CHANGELOG.md` and `RELEASE_NOTES.md` are
   written as each change lands, not here, so what is left is to read
   the open section of both against `git log`, drop the `(work in
   progress, not released yet)` from each heading, and renumber them
   if the version bump above renumbered it. `version-check` refuses a tag
   whose section in either file is missing, empty, or still carrying
   anything after the version in its heading, so a forgotten retitle
   stops the release before the matrix builds anything. Dropping those
   five words is the whole of what that check asks, and it asks it of
   both files: it is the step this one exists to be, not a formality
   downstream of it. If the vendored libsecp256k1 moved, update the
   version named at the top of `README.md` too (`grep -n 'wraps
   libsecp256k1' README.md` finds the line without a search through
   the prose).

   In the same pull request, open the next version's section in both
   files, above the one just closed: headed `## v<version> (work in
   progress, not released yet)` with the fourth number the step that
   opens the next version will declare, and nothing under it yet. What
   lands next then has somewhere to be written down as it lands, which
   is the whole of closing the release notes at the end of the cycle —
   with one branch and no long-lived release pull request to hold a
   body, it is also the whole of what giving the pull request its title
   and body reads the cycle off. Opening it in a pull request of its own
   after this one, ahead of anything else landing, is the rejected
   alternative: until that pull request lands the topmost section of
   each file is the release's, so a branch landing in between files its
   entry under a release it is not in, and nothing reports it, the
   release commit having touched only the heading. `version-check` reads
   the section headed by the tag alone, so a heading above it is nothing
   it sees, and it is not what the release publishes: the notes are
   lifted from the section whose heading is the tag's own
1. give the pull request its title and its body before merging it, not
   after. The title is the version; the body says what the release is —
   what moved, what did not, and which of the two a user would notice.
   The pull request is where that stays, and where a reader of the commit
   arrives from `main`'s history. A template left unfilled, or a bot's
   summary of the diff, is not a substitute — the summary can stay, but
   what the diff cannot say has to be written, and what a reader should
   not have to discover at the button belongs there too.

   What the cycle actually contained is not this pull request's diff,
   which is a version bump and the headings the previous step closed and
   opened: it is everything merged since the last tag. Read it off the
   log rather than off the branch, and against the sections of
   `CHANGELOG.md` and `RELEASE_NOTES.md` which closing the release notes
   above has just closed, and which are where each change was described
   as it landed.

   The previous version takes a fence of its own with nothing under it
   to reach, the way the run id does below: written into the range,
   `v<previous version>..main` is a `<previous` redirection that creates
   a file named `..main` wherever the reader's directory holds a file
   called `previous`. `${tag:?}` answers the other paste, the second
   fence alone, where the value is merely unset: unguarded it asks for
   `..main`, which is `HEAD..main` and empty on a release branch up to
   date with `main`, and an empty log reads as a cycle that contained
   nothing.

   ```shell
   tag=v<previous version>
   ```

   ```shell
   git log "${tag:?}"..main --oneline
   ```

   `deps-latest`'s result and the breaking-changes check's griffe findings
   belong here too, a line rather than a screenshot: neither gates
   anything, and a pull request that never
   mentions them having run reads exactly like one that skipped them.

   A deliberate skip and an item nobody has gotten to yet are different
   facts and do not fit under one checkbox: 0.7.1.2's own checklist
   folded "dispatch `deps-latest`" and "`mutation` is owed" into a single
   line, which could not say "skipped this once, on purpose" and "done,
   by hand and out of band" at the same time without being rewritten
   first. Separate lines for independent questions cost nothing and stay
   accurate without an edit.

   Then merge it into `main` with a green CI. It is an ordinary pull
   request against the only branch there is, and it lands the way every
   other one here does: squash, pressed by auto-merge once the review and
   the checks are in — the same button and the same `pull_request`-mode
   bypass every other pull request lands through, REPOSITORY.md's "Merge
   methods" and "Auto-merge" sections having the ruleset that grants it.
   A direct push, fast-forwarded from the command line, is refused for
   everyone now, this pull request included: the bypass that once allowed
   it moved from `always` to `pull_request` mode, so nothing reaches
   `main` outside a pull request GitHub itself merges.

   `gh pr merge <n> --repo btclib-org/btclib-secp256k1 --squash` alone
   still refuses this pull request — `the base branch policy prohibits
   the merge`, gh's own client-side mergeable check reading
   `REVIEW_REQUIRED` and declining before it asks the server at all.
   `--auto` is the wrong answer to that message: it waits for the same
   approving review that a solo-maintainer repository cannot produce, so
   it never fires. `--admin` is gh's own suggestion, asking for the pair
   REPOSITORY.md's "Branch protection" names — `enforce_admins` `false`
   together with holding `admin` — and `gh api -X PUT
   repos/btclib-org/btclib-secp256k1/pulls/<n>/merge -f
   merge_method=squash` asks the same question of the endpoint directly,
   bypassing gh's client-side check rather than satisfying it: this is
   the one measured, on 0.8.0.4 (#288), which carried no approving
   review — only comments — and landed through the direct call after the
   plain `gh pr merge` refused it locally.

   The button used to be the wrong landing on this pull request in
   particular: it is the release commit that gets tagged, and
   fast-forwarding from the command line kept that commit's signature the
   maintainer's own where a squash composed by GitHub would have left it
   under the web-flow key instead. That distinction stopped mattering
   once `required_signatures` was read as asking for a valid signature
   and not for a particular signer — a commit GitHub composes and signs
   on merge is exactly as good a base for the release tag as one signed
   from the command line, which is what section 11 of the organization
   standard asks of every pull request here, this one included.

   What no landing here can cost any more is the history of a cycle. It
   could once: 0.7.1 was *Squash and merge* on a release pull request
   carrying ninety-two commits from a development branch, and it left one
   commit where ninety-two records of a decision had been. The trees were
   identical, so nothing published was wrong, but it could not be put
   back — the trunk refuses force pushes with `enforce_admins` on, six of
   the ninety-two were unsigned where signatures are required, and the tag
   could not have followed a rewrite either, the PEP 740 attestation
   binding 0.7.1 to that commit and to `refs/tags/v0.7.1` alike. They are
   kept at the tag `history/dev-0.7.1`. With one branch the question does
   not arise: every change reached `main` in its own pull request as it
   landed, and this one carries the release and nothing else.

   What has to be green is `lint`, `docs` and `test` on the commit `main`
   ends up at, which is worth asking for by commit rather than reading
   off a branch, and worth fetching before asking — the merge lands on
   the forge, not in this checkout, and nothing before this step moves
   `refs/remotes/origin/main` to the commit the merge produced:

   ```shell
   git fetch origin
   sha=$(git rev-parse origin/main)
   echo "$sha"
   gh run list --repo btclib-org/btclib-secp256k1 --commit "$sha"
   ```

   and worth waiting for rather than assuming: the push the merge makes
   to `main` fires those workflows again from their `push` trigger, runs
   of their own rather than the `pull_request` runs already green on the
   pull request a moment earlier. The red `Dependabot Updates` runs
   sitting beside them are Dependabot's own updater failing to compute an
   update, not a workflow of this repository, and say nothing about the
   tree
1. tag the commit `main` now points at, signed, and push that tag
   alone, checking for `Good signature` before anything is pushed:

   ```shell
   sha=$(git rev-parse origin/main)
   tag=v$(uv version --short)
   git tag -s "$tag" -m "btclib-secp256k1 $tag" "$sha"
   git tag -v "$tag"
   git push origin "$tag"
   ```

   `$sha` rather than the `HEAD` a bare `git tag` would default to:
   the merge above lands on the forge, and this checkout is still the
   release branch, which the squash merge never puts on `main`'s own
   history. Naming it reads the same ref the step above already fetched and
   checked runs against, rather than trusting a checkout the merge
   never moved.

   The tag's name is read from the tree rather than typed: `uv version
   --short` gives what `pyproject.toml` declares here, on the release
   branch rather than on `$sha`, and the two agree because the version
   bump is exactly the change the squash carried onto `main` unchanged.
   `version-check` fails a tag naming anything else, so that is the
   only tag a release can be cut on.

   `-s` rather than a bare `git tag`, which makes a lightweight tag: a
   name pointing at a commit, carrying no signature, no tagger and no
   date of its own. That is the wrong shape for the one ref this release
   is identified by — the PEP 740 attestation binds to it, the GitHub
   release is created from it, and `version-check` refuses a tree that
   does not match it — so the tag is the thing most worth being able to
   attest, and a lightweight one cannot be. libsecp256k1 itself tags this
   way, and `secp256k1/README.md` documents verifying it with
   `git tag -v`; this repository holds itself to what it vendors.

   `-s` explicitly rather than relying on `tag.gpgsign` being true in the
   git config: a global setting is not visible in this document, and the
   command here is the instruction. `-m` because signing implies
   annotating, and an annotated tag with no message opens an editor,
   which is not what a release step should do.

   `git tag -v` before the push, not after: a tag that has been pushed is
   a tag the release workflow has already started acting on, and the
   signature is the one thing about it that no later check looks at.

   `git push --tags` would push whatever other local tags happen to
   exist. The workflow then builds and tests every artifact the release
   ships and stops at the `pypi` environment.

   A run that comes back `startup_failure` with **zero jobs
   scheduled** -- not even `version-check`, which has no dependencies
   at all -- is not the matrix failing to build; `release.yml` itself
   was refused before a single job started, and the REST API says
   nothing more than a generic "workflow file issue": the actual error
   is on the run page alone, not in anything `gh run view` or
   `gh api .../runs/<id>/jobs` prints. `v0.8.0.3` hit this on three tag
   pushes and a `workflow_dispatch`, all identical and independent of
   the trigger, because a called workflow's jobs are capped at what
   the *caller* grants, not at what the called workflow's own
   top-level default declares -- `test.yml`'s `changes` job (#189)
   asks for `pull-requests: read`, and `release.yml` granted only
   `contents: read`. Retagging does not help here the way it does for
   `invalid-publisher` below: nothing had been built yet either way,
   but this is a structural defect in the workflow file, not a
   transient one, and a freshly re-signed tag on the same commit failed
   the same way two hours later. What answered it was the missing
   permission, granted on the calling job (#281) -- confirmed with a
   `workflow_dispatch` rehearsal on the fix branch before retagging,
   scheduling dozens of jobs where the unfixed commit scheduled none
1. approve the `pypi` deployment when the run pauses for review. Up to
   here nothing is public and the tag can still be deleted; the upload
   that follows is the point of no return — the upload, and not the
   approval, the token exchange happening after it. A registration that
   does not match the claims fails there having uploaded nothing, as the
   0.7.1 rehearsal did on TestPyPI, and a version survives a failed
   exchange: delete the tag, fix the registration, tag again.

   Retagging rebuilds a matrix that was never at fault, though: 0.7.1.2
   hit this same `invalid-publisher` for real, on `pypi` rather than a
   rehearsal's `testpypi`, the registration having gone stale behind an
   eyeballed check of the project settings — a repository rename is
   enough to do that silently, and the settings page does not flag a
   `workflow_ref` or `environment` that no longer matches. The matrix had
   already built and only the publish step had failed, so fixing the
   registration and running `gh run rerun <run id> --repo
   btclib-org/btclib-secp256k1 --failed` republished from the artifacts
   already there, in minutes rather than the better part of an hour, the
   tag never touched. Retagging is the right answer only when the failure
   happened before the artifacts existed
1. read the run job by job once it has ended, for `skipped` rather than
   for red. A failed job is loud; a skipped one carries no step, starts
   and completes in the same second, and leaves the run looking finished
   with a job missing from it, which is what a bare `needs:` behind a
   red `public-api` produces -- section 12 of the organization standard
   has the rule, and the `skipped` `github-release` of 0.8.0.2 below is
   this tree's own instance of the mechanism.

   The run id stands in a fence of its own, with nothing under it to
   reach: an interactive shell discards a line ending in a placeholder
   as a parse error and reads the next line of the same fence as a
   fresh command. Each fence that takes a value from one of these
   writes it `${name:?}`, and chains its commands with `&&` where it
   holds more than one, against the other paste -- the second fence
   alone, where the value is merely unset and no parse error discards
   anything. Unguarded here, the run id asks for `runs//jobs`, whose
   404 reads as an answer about the run rather than as a line nobody
   filled in.

   ```shell
   run=<run id>
   ```

   ```shell
   gh api --paginate \
     --jq '.jobs[] | [.conclusion, (.steps|length), .name] | @tsv' \
     "repos/btclib-org/btclib-secp256k1/actions/runs/${run:?}/jobs?per_page=100"
   ```

   On a tag `Publish to TestPyPI` is `skipped`, its trigger being the
   dispatch, and `public-api` is red on any cycle with breaking changes
   in it, being the griffe step above run again. Every other job reads
   `success`, the ones behind `public-api` included: each of them opens
   its `if:` with `always()` and names the results it does require, so
   a red `public-api` costs the release nothing, and a `skipped` among
   them is a defect in `release.yml` rather than a red to look past. A
   rehearsal is the mirror image, `Publish to PyPI` skipped and with it
   whatever is guarded on its success, and `documented` skipped on its
   own account, its guard being the push. `gh run rerun --failed` does not
   reach a skipped job -- that flag reruns `failure`, and a skip is
   neither a failure nor within its blast radius -- so what recovers one
   is doing by hand what it would have done, the way the GitHub release
   step below shows for that job
1. check that what was published installs, in an environment of its own
   rather than one that may already hold it, and run something with it —
   installing being weaker than working where a compiled extension is
   what was installed:

   ```shell
   version=$(uv version --short)
   uv run --isolated --no-project --with "btclib-secp256k1==$version" \
     python -c "
   from btclib_secp256k1 import ssa
   msg = bytes(32)
   pub = bytes.fromhex('F9308A019258C31049344F85F89D5229B531C845836F99B08601F113BCE036F9')
   sig = bytes.fromhex('E907831F80848D1069A5371B402410364BDF1C5F8307B0084C55F1CE2DCA821525F66A4A85EA8B71E482A74F382D2CE5EBEEE8FDB2172F477DF4900D310536C0')
   assert ssa.verify(msg, pub, sig)
   "
   ```

   The version comes from the tree as at the tagging step above, so what
   this installs is the release that was just published.

   BIP340 vector 0, the same check `pypi-install` makes below. Then check
   the attestations, the two checks the rehearsal makes and for the same
   reasons: a compiled extension can install and not work, and the
   attestations are under `/integrity/<project>/<version>/<filename>/provenance`
   rather than in the JSON API, which answers `null` for `provenance`
   even where they are
1. `pypi-install` no longer needs a manual dispatch to answer this for the
   release itself: `release.yml`'s own `published` job (`needs:
   publish-pypi`) calls the same workflow directly, so by the time the run
   finishes it has already installed from PyPI what was just uploaded, on
   every platform and at both ends of the supported interpreter range, and
   verified BIP340 vector 0 with it. Read its result in the run rather
   than dispatching a second one. It still runs weekly on its own too, and
   a failure there means the outside world moved, not this repository —
   which is why it stayed a workflow of its own rather than folding into
   `release.yml` outright.

   A cell of that matrix can still lose the race with the index even
   though `version-check` already confirmed PyPI serves the version: 0.8.0
   failed `Install 3.14 from PyPI on ubuntu-24.04-arm` this way, one cell
   out of the whole matrix, `pip` answering "no matching distribution"
   seconds after the JSON API had confirmed the release — the file was on
   the index by then (`pypi.org/pypi/<project>/<version>/json` lists it
   in `urls`), so this is `files.pythonhosted.org`'s CDN a step behind
   Warehouse's own database, not a missing wheel. `gh run rerun <run id>
   --repo btclib-org/btclib-secp256k1 --failed` reruns the cell alone and
   it passes the second time
1. check the GitHub release the workflow created once PyPI had accepted
   the upload — and check that it exists at all before reading anything
   in it: `github-release` was left `skipped` on 0.8.0, 0.8.0.1 and
   0.8.0.2, despite `publish-pypi` and `attest` succeeding every time.
   The cause is `attest`'s own `if: always() && (...)`, needed so it can
   run past a skipped sibling — `publish-testpypi` is always skipped on a
   real tag, `publish-pypi` on a dispatch. GitHub's needs-based skip is
   structural, not a property of which question a job's own `if` asks: a
   job with a skipped job anywhere in its ancestry is force-skipped
   regardless of its condition, unless that condition itself starts with
   `always()` — and the override does not clear the taint for whoever
   depends on the job that used it. That is what the 0.8.0 fix got wrong:
   it gave `github-release` an explicit `if:
   needs.publish-pypi.result == 'success' && needs.attest.result ==
   'success'`, reasoning that asking only about direct needs would be
   enough, and 0.8.0.2 shipped with exactly that and was skipped all the
   same — `attest`'s `always()` keeps attest itself from being skipped
   when `publish-testpypi` is, but `github-release`, needing attest,
   still sat behind that same skipped ancestor and was force-skipped in
   turn. `github-release`'s `if` needs its own `always()` too: `if:
   always() && needs.publish-pypi.result == 'success' &&
   needs.attest.result == 'success'`. A release cut after this second fix
   should not need what follows here; keep it for a release that
   predates it, or for a failure of `github-release` itself rather than a
   skip, which `gh run rerun --failed` reaches directly — a skip, unlike
   a failure, is not what that flag reruns, so before this fix a rerun
   scoped to some other job's failing cell always left `github-release`
   exactly where it was.

   Recreate a skipped release by hand from the run's own artifacts, which
   is the same thing that step would have done. `tag` is typed beside
   `run` because both name which release is being recreated, rather than
   what the tree declares now.

   Both are placeholders and take a fence with nothing under them, and
   the block below guards each of them: unguarded, its `awk` writes
   `notes.md` wherever the reader is standing and `gh release create` is
   one line further down.

   ```shell
   run=<run id>
   tag=v<version>
   ```

   ```shell
   repo=btclib-org/btclib-secp256k1 &&
   gh run download "${run:?}" --repo "${repo:?}" \
     --name sdist --dir dist &&
   gh run download "${run:?}" --repo "${repo:?}" \
     --name attestation --dir attestation &&
   cp attestation/attestation.jsonl "${tag:?}.attestation.jsonl" &&
   awk -v tag="${tag:?}" '
     $0 ~ "^## " tag "( |$)" {found=1; next}
     /^## / && found {exit}
     found {print}
   ' RELEASE_NOTES.md > notes.md &&
   gh release create "${tag:?}" dist/* "${tag:?}.attestation.jsonl" \
     --repo "${repo:?}" --title "${tag:?}" \
     --notes-file notes.md --verify-tag
   ```

   `--verify-tag` aborts where the tag is not already on the remote,
   `gh release create` otherwise creating one from the default branch.
   Verify the sdist this produces the same way the step below does: the
   hash has to match the file `pypi.org/pypi/<project>/<version>/json`
   already lists, since nothing rebuilt it. Its notes are the tag's
   section of `RELEASE_NOTES.md`, and the sdist is attached, with
   `<tag>.attestation.jsonl` beside it. A run that warns
   `RELEASE_NOTES.md has no v0.7.1 section` generated the notes from
   the merged pull requests instead, and they are worth replacing by
   hand either way
1. verify the sdist on the releases page, which is the copy PyPI's
   attestation says nothing about — the step above says the file is
   there, this one says where it came from:

   ```shell
   repo=btclib-org/btclib-secp256k1
   tag=v$(uv version --short)
   dir=$(mktemp -d)
   gh release download "$tag" --repo "$repo" --dir "$dir"
   gh attestation verify "$dir/btclib_secp256k1-${tag#v}.tar.gz" \
     --repo "$repo" --signer-workflow "$repo/.github/workflows/release.yml"
   ```

   PEP 625 escapes the distribution's `-` to `_` in an sdist filename,
   which is the whole of the difference between the tag and the file it
   names, so neither is typed here.

   `--signer-workflow` is the flag that makes it say *which* workflow
   signed: without it a valid attestation from any workflow in this
   repository passes. Adding `--bundle "$dir/$tag.attestation.jsonl"`
   asks the same question of the statement downloaded beside the file
   rather than of the attestations API, which is the form for whoever
   mirrors the page instead of trusting it live
1. read the `documented` job rather than the site. Read the docs
   activates and builds a new release tag from an automation rule of its
   own, and that job waits for
   `https://btclib-secp256k1.readthedocs.io/en/<tag>/` to be served and is
   red if it never is. Green means the release has a permanent URL of its
   own, which is the one to link wherever the version is named; a rendered
   `/en/latest/` says nothing about it, serving the tip of `main`
   regardless of what any tag built. Red means
   [the builds page](https://app.readthedocs.org/projects/btclib-secp256k1/builds/)
   is where the reason is, and it is the one red in this file that
   withholds nothing — no job needs this one, PyPI has the files by the
   time it decides, and the fix is a build on their side rather than a
   moved tag. The automation rule is a dashboard action nothing in this
   repository can make, tracked at btclib-org/.github#26, so a red run
   with no build attempted at all is that rule missing rather than a
   build failing
1. open the next version: bump `pyproject.toml` to a fourth number over
    what was just published — `0.7.1.1` after `0.7.1` — and run `uv
    lock`, through a pull request like any other. It is a placeholder,
    and the version-bump step renumbers it if the submodule
    moves before the next release; what it buys is a tree that no longer
    claims to be a version it is not. `__version__` reads installed
    metadata, so a checkout a developer installed stops reporting itself
    as the release, and a report from it is unambiguous. And pushing
    `v0.7.1` a second time — the mistake a just-finished release invites
    — then fails at `version-check` in a minute, the declared version
    having moved, rather than building the whole matrix and dying at an
    upload PyPI refuses for a version it already carries. A fourth
    number below the published one would be worse than no bump at all:
    `0.7.0.1` sorts *under* `0.7.1`, so nothing would ever resolve it,
    and `version-check` accepts it, being digits and dots. The sections
    for it in `CHANGELOG.md` and in `RELEASE_NOTES.md` are already
    there, closing the release notes above having opened them in the
    release's own pull request. What stays here is the version, which
    cannot move earlier with them: `version-check` compares the tag
    against what `pyproject.toml` declares, so a tree already bumped
    would offer it the placeholder instead of the version being released

## Rehearsing on TestPyPI

A tag cannot be taken back: a version, once on PyPI, can only be yanked,
never replaced. So the same workflow can be run manually, and a manual
run publishes to TestPyPI instead. It is the same file, the same jobs and
the same gate as the release it rehearses, which a second workflow of its
own could not be: a trusted publisher is registered for a workflow
*filename*, so a `release-test.yml` would only ever prove itself.

The rehearsal is what the release machinery itself is tested with, when
the workflow, the packaging metadata or the build matrix changed. A
release that only bumps versions and notes does not need one.

A trusted publisher can only be registered by an owner of the project,
so a name an unrelated project already holds on an index cannot be
registered from here: the run builds the whole matrix, collects every
artifact, waits for its approval and then stops at the token exchange
with `invalid-publisher`. Owner rights on that project, and a
registration matching the claims the failure prints, are the whole of
what it takes; `gh run rerun <run id> --repo
btclib-org/btclib-secp256k1 --failed` then publishes from the artifacts
already built.

1. run the `release` workflow from the Actions tab, on the branch holding
   it: a manual run builds the full matrix and stops at the `testpypi`
   environment. Nothing has to be done to the version first. A version is
   consumed by the upload on TestPyPI as much as on PyPI, so every build
   job appends `.dev<run><attempt>` to what `pyproject.toml` declares,
   which is unique per attempt and sorts before the release being
   rehearsed. A re-run is therefore a version of its own and cannot
   collide with the rehearsal it repeats — it used to, the run number
   being all the suffix carried, and the 400 arrived after the
   three-quarters of an hour the matrix takes.
   What a version is consumed by is the upload, and only the upload: a
   rehearsal that failed before it — at the token exchange, say — left
   its version free, and `gh run rerun --failed` re-runs the publish job
   alone against the artifacts already built, instead of an hour of
   matrix again. That is what published 0.7.1.dev1, three minutes after
   a registration was corrected, and it holds for as long as the
   artifacts do — a window the endpoint answers for the day it is read:

   ```shell
   repo=btclib-org/btclib-secp256k1
   gh api "repos/$repo/actions/permissions/artifact-and-log-retention"
   ```

   `days` is the window, and `maximum_allowed_days` is the ceiling the
   organization's own setting puts on what a repository may ask for: the
   two reading the same is this repository not having narrowed it. Note
   that a re-run rebuilding the matrix now carries the attempt in its
   version, so what it uploads is not what the first attempt built under
   a different name.
   Never tag a rehearsal: the trigger is what picks the index, so a
   `v0.7.1rc1` tag would take the pre-release to PyPI itself and burn it
   there, and `0.7.1rc1` is a version PyPI would then hand to `--pre`
   installs. The `version-check` job refuses a tag whose version is not
   digits and dots, so the mistake stops before anything is built
1. approve it, then check that what was published installs, in an
   environment of its own rather than one that may already hold it. A
   re-run has to be approved again, the protection applying to each
   deployment attempt rather than once per run:

   ```shell
   version=$(uv version --short)
   uv run --isolated --no-project \
     --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ \
     --index-strategy unsafe-best-match --prerelease allow \
     --with "btclib-secp256k1==$version.dev<run><attempt>" \
     python -c "import btclib_secp256k1 as m; print(m.__version__)"
   ```

   the extra index being needed for `cffi`, which TestPyPI does not have,
   and `--prerelease allow` for the `.dev<run><attempt>` suffix the
   version installed carries. Those two numbers are the run's own and are
   the whole of what is typed here, the version before the suffix being
   read from the tree as in the check after a release above
1. run something with it, installing being weaker than working where a
   compiled extension is what was installed. The check the `pypi-install`
   workflow makes — BIP340 vector 0, and the round trip of a signature
   the build makes itself — is the one to reach for, and it is worth
   reaching for here rather than only after PyPI: this is the first
   moment a wheel this repository built is fetched from an index by a
   resolver, and the last before the version cannot be replaced
1. check the attestations. The JSON API will not show them, its
   `provenance` field being null on every file of a release that has
   them; the project page shows them, and machine-readably they are
   under `/integrity/<project>/<version>/<filename>/provenance`, whose
   `attestation_bundles[].publisher` should name this repository and
   `release.yml`
1. check the statement the `attest` job signed, which on this path has no
   release to be attached to: it went to the attestations API all the
   same, keyed by the digest of the file, so the sdist the run built is
   what asks for it. The run id is assigned rather than written into the
   `gh run download` line: inline it is a `<run` redirection, guarding
   only while the reader's directory holds no file called `run`, where
   an assignment ending in a placeholder is a parse error whatever the
   directory holds.

   ```shell
   run=<run id>
   ```

   ```shell
   repo=btclib-org/btclib-secp256k1 &&
   dir=$(mktemp -d) &&
   gh run download "${run:?}" --repo "${repo:?}" \
     --name sdist --dir "${dir:?}" &&
   gh attestation verify "${dir:?}"/*.tar.gz \
     --repo "${repo:?}" \
     --signer-workflow "${repo:?}/.github/workflows/release.yml"
   ```

   This is the whole reason `attest` runs in a rehearsal at all: the
   permissions and the API it needs are exercised here, where a failure
   costs a dispatch, rather than for the first time on release day, where
   it lands after PyPI has the files and the tag can no longer be moved

There is no version commit to revert, and nothing to clean up: the
suffix only ever exists inside the run that built it.

What the rehearsal covers is the OIDC exchange, the approval gate, the
artifacts the publish job collects — sixty-three wheels and one sdist, at
0.7.1 — the PEP 740 attestations, the Sigstore signature `attest` writes,
and a real Warehouse accepting the metadata, which is more than
`twine check --strict` can say. What it
cannot cover is the trusted publisher on PyPI itself, a separate
registration that can be wrong on its own, nor the deployment branch
policy of the `pypi` environment, which the environment a rehearsal does
reach has none of, nor the checks of `version-check` that need a tag: the
version comparison, the `RELEASE_NOTES.md` section, and the ancestry on
`main`.

## Rebuild a release from its tag

`build-sdist` in `test.yml` exports `SOURCE_DATE_EPOCH` from the commit
date and normalizes the sdist, so a rebuild of a released tag is the
same bytes as what was published — that job's own upload is what
`publish-pypi` publishes, unchanged. A worktree and not `git checkout`,
for the reason CLAUDE.md gives.

The tag is the reader's, so it is a placeholder rather than a version
spelled out, and it stands in a fence of its own. The block below guards
it and chains its lines: unguarded, a paste of that block alone reaches
`git submodule update` and the `uv` build with the reader's own
directory as their working directory, the `cd` above them having had no
worktree to enter. The chain is the run-time guard as well, a rebuild
that carries on past a failed `uv build` normalizing and verifying
whatever `dist/` already held.

```shell
tag=v<version>
```

```shell
git worktree add --detach /tmp/btclib-secp256k1-rebuild "${tag:?}" &&
cd /tmp/btclib-secp256k1-rebuild &&
git submodule update --init --recursive &&
export SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct) &&
uv run --locked --only-group build python -m build -s &&
uv run --no-project --python 3.14 \
  .github/scripts/normalize_sdist.py dist/ &&
repo=btclib-org/btclib-secp256k1 &&
gh attestation verify "dist/btclib_secp256k1-${tag#v}.tar.gz" \
  --repo "${repo:?}" \
  --signer-workflow "${repo:?}/.github/workflows/release.yml"
```

is the whole of it, `--locked` included for the same reason as before: a
rebuild from a released tag has nothing rewriting the version, so the
lock and `pyproject.toml` already agree, and the flag asserts that the
lock is the one the tag committed rather than taking `uv.lock` as it
finds it. Verifying the *rebuilt* file this way rather than comparing
its digest against the index's is one command short of the "verify the
sdist on the releases page" step above: it can only pass if the file
`gh attestation verify` hashes is the one the signed statement covers,
where a digest compared against the index only says PyPI serves what it
always served.

**What the script rewrites here, and what it leaves alone.** This
repository's `build-system.build-backend` is `hatchling.build`, unlike
both siblings' `uv_build`, and hatchling's sdist writer already stamps
every member's ownership at `uid`/`gid` `0` and `uname`/`gname` `""` —
measurable with `tarfile.getmembers()` against a build of this tree —
so the script does not touch them. Nor does it touch mode: each
member's mode is the executable bit git tracks for that file,
`secp256k1/autogen.sh` and the small set of vendored tools beside it
staying executable on a plain extract, and flattening that to one
constant would strip the bit those files need to run. `mtime` is the
field left, and the one hatchling does not fix on its own: unset,
`SOURCE_DATE_EPOCH` falls back to hatchling's own constant,
`1580601600`, neither of which is the tagged commit's date, so the
script — and the `SOURCE_DATE_EPOCH` step ahead of the build, belt and
braces against a future hatchling release deciding the variable
differently — is what makes it that instead. The property those two
serve is section 12 of the organization standard's: a published sdist
reproduces from its tag. The steps between the tag and the archive are
this file's to name, with the reason beside each, and section 12 refuses
the reading under which a publisher weighs whether its backend has made
one of them redundant.

The vendored `secp256k1` submodule is not a source of drift on top of
that: `.gitmodules` pins it to a commit, and a git checkout of a pinned
commit is the same bytes wherever and whenever it happens, the
recursive `submodule update` above included.

The static wheels reproduce too, and within narrower bounds than the
sdist: one image rather than anywhere. They are `cibuildwheel` output
over that same vendored C library, one build per platform and
interpreter, and two builds of one commit in one image are one archive,
member for member. The timestamp is what makes that true, and it is
pinned the way the sdist's is — every job of `test.yml` that builds a
distribution exports `SOURCE_DATE_EPOCH` from the commit, and
`[tool.cibuildwheel.linux]`'s `environment-pass` carries it into the
container the Linux build and its `auditwheel` repair run in, which
inherits nothing from the runner. Without it the repair is what writes
the clock into the archive: `auditwheel` repacks from a directory it
extracted the wheel into and stamps every member, and `delocate` stamps
the members it rewrites.

The `py3-none-*` wheels the release publishes beside them are built
another way again: `build-dynamic` and `build-windows` build them with
`python -m build` on the runner, and `publish-pypi` uploads them with
the rest under the `*-wheels-*` pattern. They carry the same pinned
timestamp, for the reason above and so that one release's files agree
on when they were built. The sentinel below builds each of them twice
in one image and diffs the pair, so what they reproduce to is that
workflow's output rather than a sentence here.

What is not settled is two *environments*. A wheel compiled on the
runner carries the compiler, its version and the toolchain that image
happened to have, and nothing pins any of the three, so such a wheel
rebuilt on another image is other bytes and is not claimed to be
anything else. That is one measurement across the platforms and not one
decision: a rebuild is a check only where the environment it needs is
something the person running it can obtain, and that holds on one of
them.

On Linux it holds for the static wheels. `build-cibuildwheel` compiles
those inside a manylinux or a musllinux container, and
`[tool.cibuildwheel.linux]` names that container by the digest of its
content: `docker pull`able by anyone, outliving the runner image that
hosted it, so the digest states the environment to somebody who was
never on the machine. `wheel-reproducibility.yml`'s `repaired` job
builds one commit through that container on two host images on both
Linux platforms, and `across-images` is what compares them
(btclib-org/btclib-secp256k1#524).

The `py3-none-manylinux*` wheels are outside it. `build-dynamic`
compiles them on the runner in no container, so
`[tool.cibuildwheel.linux]` is not read by the job that builds them at
all, and `auditwheel` names what it repairs for the glibc the compiled
object requires — the `manylinux` in those file names is a
compatibility tag rather than an image. Their environment is the
runner's own, which is the paragraph above.

On macOS and Windows the pin is declined rather than pending.
`xcode-select` and `-vcvars_ver` choose among what the runner image
already carries, so a version recorded here describes nothing to a
reader who does not have that image; GitHub retires the images, so the
one a given wheel was built on stops being available; and rebuilding a
macOS wheel needs a Mac and a Windows wheel needs Windows, where the
container runs wherever `docker` does. Pinning there narrows the drift
and leaves the check unrunnable, so what those two wheels carry instead
is the PEP 740 attestation `publish-pypi` uploads with every file, which
says who built it and where rather than what is in it.

A verifier who rebuilds a released static wheel outside the image that
built it and gets other bytes therefore has the expected outcome and not
a defect to report. On Linux the image is obtainable, so the rebuild
inside it is a check a stranger can run; on macOS and Windows there is
no image to rebuild in, and that is the end state rather than something
a fix is coming for.
btclib-org/btclib-secp256k1#439 is the umbrella over both halves. Which
issue section 12 of the organization standard cites for a compiled
wheel's exemption is that file's own to state, not this one's to
restate.

`wheel-reproducibility.yml` is what measures any of the above rather
than leaving it asserted. Its `rebuild`, `repaired`, `dynamic` and
`cross-windows` jobs each build one commit twice in one image and name
the members that differ, and `across-images` compares two images'
wheels of one platform: `rebuild`'s wherever it builds one, and
`repaired`'s on the two Linux platforms, which carry a second image of
their own. `repaired`, `dynamic` and
`cross-windows` take the frontend and the repair from the job that
uploads the wheel each is about, so the file under measurement is the
one PyPI receives; `build-windows` runs no repair, so `cross-windows`
runs none either. Two images differ
in more than one input at a time, so which input reached a member is a
question that output poses rather than answers. `rebuild` and
`repaired` narrow to one interpreter, so whether a wheel of another ABI
tag reproduces is outside what either measures, which that workflow's
own header states. `dynamic` and `cross-windows` have no interpreter
axis to narrow, the jobs they follow building one wheel per platform;
what they leave unasked instead is the environment, neither carrying a
second image.

So a rebuild of a released static wheel is a rebuild in the image that
built it, from the tag, with `SOURCE_DATE_EPOCH` exported from the
commit as the workflow exports it.

Both siblings ship one pure-Python wheel each, and `uv build` builds it
directly from the very sdist that already reproduces there too, no
compiled step in between — which is why neither sibling's file draws
this line. This repository's wheels are compiled, and that is the whole
of the asymmetry.

## When a release turns out to be broken

Nothing can be reuploaded under the same version, on either index. A
broken release is yanked, which hides it from resolution while leaving it
installable by exact pin, and the fix ships as a new version: a fourth
number when the wrapped libsecp256k1 is unchanged (`0.7.1.1`). Yanking
is done from the PyPI project page; the tag and the GitHub release are
worth keeping, as what a yanked file was built from.

## One-time setup, per index

A registration is per project name, so **a name this has not been done
for needs it done** — on PyPI and on TestPyPI both — before anything can
be published under it. For a name no project holds yet the form to use
is a *pending* publisher, which is the same registration made against a
name rather than a project and which creates the project on the first
upload it accepts. Without it the run gets as far as the token exchange
and stops there with `invalid-publisher`, having built the whole matrix
first.

The rest of this section is here for the next index, or the next fork.

- on PyPI, and on TestPyPI, project Publishing settings: add a GitHub
  trusted publisher for `btclib-org/btclib-secp256k1`, workflow
  `release.yml`, environment `pypi` and `testpypi` respectively. The two
  indexes are separate accounts and separate registrations, and separate
  credentials with them, TestPyPI being its own deployment of Warehouse
  with its own user database: owning the project on one says nothing
  about the other, and neither does having an account. On TestPyPI the
  name was somebody else's `0.0.1` from 2021, which is what the
  rehearsal's `invalid-publisher` was; only an owner can add a
  registration, and what unblocked it was being made one, which costs a
  collaborator invitation rather than a transfer of the project
- what a mismatched registration looks like, since only the run can tell
  you: `invalid-publisher`, followed by the claims the token carried.
  Those claims are the answer key — `repository`, `environment`, and the
  `workflow_ref` naming the file and the ref it ran from — and the
  registration has to be read against them rather than the other way
  round, the log itself warning that the claims are for debugging and
  not for configuring from. A registration that matched once is not
  guaranteed to keep matching: 0.7.1.2 hit `invalid-publisher` on `pypi`
  itself, the registration having gone stale — most likely behind the
  repository's rename — since 0.7.1 last needed it, with nothing on this
  side having touched it in between
- on GitHub, repository Settings, Environments: create the `pypi` and
  `testpypi` environments, each with the required reviewers who approve
  -- `fametrano` on both. Self-review stays allowed on purpose: the
  maintainer who pushes the tag is the reviewer, and forbidding it would
  deadlock a one-maintainer release. The approval is a confirmation
  step, not a second pair of eyes; it becomes one as soon as there is a
  second reviewer to add. Leaving `testpypi` without reviewers would be
  the one part of a release that the rehearsal stops exercising
- `pypi` carries a deployment branch policy besides, a custom rule
  admitting the tag pattern `v*`, that environment being reachable only
  from a tag; `testpypi` has none, being reached from a branch by
  dispatch. REPOSITORY.md's "Publishing" section reads the policy back
  and has what the rule constrains, which is the *name* of the ref and
  nothing else: the reviewer approving sees the tag name rather than its
  ancestry
