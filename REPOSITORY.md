# Repository configuration

Read this before changing a workflow, a branch rule or a repository
setting; writing code does not need it. [CLAUDE.md](./CLAUDE.md) points here
rather than carrying it, so that a session fixing a wrapper does not hold
it in context.

The branch rules and the repository settings live *outside* the
repository. Every value below was read from the API, and the command
that reads it is beside it.

The topics and `.homepage` have a second form in the tree —
`pyproject.toml`'s `keywords` and its `[project.urls]` field of that
name — so each is read back here for comparison rather than as the only
place the answer lives, which is what *Topics* and *No website* say of
them. Nothing else here is recoverable by reading the tree.

**Every call here names the repository in full.** `gh`'s
`{owner}/{repo}` placeholder resolves against whatever repository the
shell is standing in, so a command copied out of this file and run from
a sibling's checkout answers for that sibling, with nothing in the
answer saying which repository it came from — and a readback of the
wrong repository is a readback of nothing. That the file holds to it is
checkable:

```shell
grep -n 'repos/{owner}/{repo}' REPOSITORY.md
```

It answers with that command's own line and with nothing else: the hit is
what says the pattern reaches the file, and a second one is a call left
for the shell to resolve. The placeholder form is all it reaches: `gh pr
view` takes the repository in a `--repo` flag that can simply be absent,
and a call omitting it leaves nothing for a grep to key on, so that half
of the convention is held to by reading rather than by running anything.

The shared half of `CONTRIBUTING.md` keeps the placeholder, for the same
reason read the other way round: it is the same file in every repository
of the organization, so it can name none of them.

What is recorded is the settings the organization standard asks about —
the ones [section 16's
checklist](https://github.com/btclib-org/.github#16-checklists) sets on
a new repository, the ones a section of the standard states a rule for,
and the ones a behaviour it describes rests on — together with whatever
a call quoted for one of those answers alongside it. That is this file's
scope, and *What this file passes over* at the foot says what falls
outside it.

## Required checks on main

**Never name matrix contexts in a branch rule.** The rule lives outside
the repository, so a context that stops being produced blocks every merge
with nothing in the tree to explain why — and the matrices here are
`Build wheels on ${{ matrix.os }}` and its siblings, whose contexts
change with every image added or dropped. `test: every job passed` is the
aggregate job at the end of `test.yml` that `needs` every other job in it;
a job added to that workflow belongs in its `needs` list, or it gates
nothing. The name
carries the workflow because a context is keyed by name alone: two
workflows with a job named the same thing produce one ambiguous check.

What the rule holds is read from the endpoint, never assumed:

```shell
gh api repos/btclib-org/btclib-secp256k1/branches/main/protection \
  --jq '.required_status_checks'
```

| Check | Produced by |
| --- | --- |
| `test: every job passed` | `test.yml`, aggregate over its jobs |
| `Lint and type-check` | `lint.yml`, its only job |
| `Build the documentation` | `docs.yml`, its only job |

`codeql: every job passed` is not among them, and its absence is a
decision rather than an impossibility: `codeql.yml` runs on a pull
request and produces that aggregate, so naming it here is a patch to this
rule and nothing in the tree. It takes both halves to be true of a
workflow — a branch rule can only name a context a pull request's own run
produces, and a matrix produces one context per language rather than one
to hold, so a trigger without an aggregate offers no name and an
aggregate without a trigger reports on no pull request.
btclib-org/.github#90 is section 10's one rule on what a required check
may name; btclib-org/.github#459 is where the organization settled that
the aggregate a required check needs is what a matrix needs.

What such a rule would cost is the ceiling: the plan caps how many jobs
an organization may run at once, shared across every repository in it,
and *Plan-gated settings* below has the figure and the command that
re-derives it. This one, bitcoin-core-rpc and one more repository each
ask for more jobs than that cap on every commit, so a pull request in any
of the three spends wall clock waiting for a slot, and this workflow's
matrix and aggregate are among what it waits behind. Requiring the
aggregate would put that wait on the merge path; leaving it unrequired
keeps a finding in the Actions tab and in the Security tab beside it,
where it is read without a merge being held.

`zizmor` is the workflow half of the same question and is required: it is
a `pre-commit` hook, so `lint.yml` audits these very files for an injected
expression on every pull request.

`Build the documentation` is named on its own on purpose: a rule naming
`Lint and type-check` alone would leave a red documentation build outside
the required checks entirely. It moved from `lint.yml` to `docs.yml`
without the rule changing, which is worth knowing before renaming
anything — a context is matched by name, not by the workflow that reported
it, so moving a job is free and renaming one is not.

`pre-commit.ci` is not in the rule either, and it is the one check here
this repository cannot make agree with `lint.yml`. It runs the hooks of
`.pre-commit-config.yaml` from a checkout of its own, and one hook needs
more than that checkout gives: `submodule-pin` resolves the release
`README.md` names in the vendored clone's refs. `submodules: true` under
`ci:` is the documented key for the clone, and it was tried on #132 rather
than reasoned about — with it the submodule arrives and the hook still
fails, `the vendored clone is shallow and carries no v0.8.0 tag`. There is
no `fetch-depth` key to ask that service for, so the hook is the one
entry in the `ci:` `skip` list. What that costs is pre-commit.ci's run
of it: the runner the rule names, `Lint and type-check`, checks the
submodule out with `fetch-depth: 0` precisely so it has what the hook
needs, and so does a developer's own commit. Re-read that skip list
before adding to it: an entry may join for a reason of that kind and no
other.

Neither `os-ubuntu.yml`, `os-macos.yml`, `os-windows.yml`, `deps-latest.yml`,
`links.yml`, `mutation.yml`, `pypi-install.yml`, `vendored-vectors.yml` nor
`wheel-reproducibility.yml` appears in the rule, and none of them must: every
one but the last is expected to go red for a reason no pull request
introduced. `wheel-reproducibility.yml` is the exception, and by design —
issue #508 gave it a `pull_request` trigger precisely so that a branch's own
change to the build can turn a cell red, which is what a required check
exists to catch. What keeps it out of the rule instead is the gap
`wheel-reproducibility.yml`'s own header names: two images of one
platform do not build one wheel yet, one half of that gap open and
pinned by an issue, the other declined outright. Requiring the check
would fail a pull request for that gap rather than for what the pull
request itself did. The first three are the ones worth naming twice,
because they do run the suite: what a merge no longer waits for is
every cell of it but one, the reasoning being in `os-ubuntu.yml`'s
header and the numbers in `test.yml`'s, and `release.yml` calls all
three so that a publication still does. `scorecard.yml` is outside the
rule for a reason of its own: it carries no `pull_request` trigger, so
it produces no context a branch rule could name.

A check can be bound to the app that produces it — `checks` with an
`app_id` rather than the bare `contexts` list — so that nothing else can
satisfy it, and 15368 is Actions, which produces them all. All three carry
that binding, and the two that did not are why it is worth stating: an
unbound context reads `app_id: null` and is satisfied by *any* app
reporting a check run of that name, so anything installed on the
organization with `checks: write` could turn one green with no workflow
having run. A `PATCH` dates that sentence, so read it back rather than
trust it:

```shell
gh api repos/btclib-org/btclib-secp256k1/branches/main/protection \
  --jq '[.required_status_checks.checks[] | {context, app_id}]'
```

Which app reported what is read from the commit rather than assumed. The
sha takes a fence of its own with nothing under it to reach: the
endpoint's path continues past it, so `commits/<sha>/check-runs` gives
the `>` closing the placeholder the target `/check-runs`, at the root of
the filesystem rather than in the directory the reader is standing in.
`${sha:?}` answers the other paste, a command fence alone, where the
value is merely unset: it stops the call before it asks the endpoint
about a commit nobody named.

```shell
sha=<sha>
```

```shell
gh api "repos/btclib-org/btclib-secp256k1/commits/${sha:?}/check-runs" \
  --jq '.check_runs[] | {name, app: .app.slug, app_id: .app.id}'
```

```shell
gh api "repos/btclib-org/btclib-secp256k1/commits/${sha:?}/check-runs" \
  --jq '[.check_runs[] | {name, app: .app.slug}] | unique_by(.app)'
```

**CodeQL is `.github/workflows/codeql.yml`, and code scanning's default
setup is off** — the two are mutually exclusive, and what that costs is not
a workflow GitHub declines to start. The workflow runs, the analysis
completes, the SARIF uploads, and processing answers:

```text
Code Scanning could not process the submitted SARIF file:
CodeQL analyses from advanced configurations cannot be processed when
the default setup is enabled
```

So while the setting is on the analysing jobs are red rather than absent,
and the file is still the one that can be reviewed in a diff. What the
setting holds is read from the endpoint, `state` being the field that
says whether it holds anything:

```shell
gh api repos/btclib-org/btclib-secp256k1/code-scanning/default-setup
```

Turning the setting off takes `state` and nothing else — the languages, the
query suite and the runner it also accepts describe an analysis that is not
going to run:

```shell
gh api -X PATCH \
  repos/btclib-org/btclib-secp256k1/code-scanning/default-setup \
  -F state=not-configured
```

The order used to matter here, back when the branch rule still named
`codeql: every job passed`: dropping that context from the rule before
turning the setting off, and naming it again only after the workflow
had produced it fresh, was what kept the merge path open through the
switch rather than closing it on a context nothing reported for one
step. `enforce_admins` being off is what made that window survivable
rather than a lock.

That exchange has been made: the endpoint above answers
`not-configured`. The sequence would matter again the day the rule named
`codeql: every job passed`, that context being what a merge would then
wait on; while no rule names it, turning the setting back on would turn
the `analyze` matrix and the aggregate red with nothing reading either.

A `CodeQL` check and an `Analyze (python)` job outlive it, and neither
comes from this tree: GitHub keeps a generated
`dynamic/github-code-scanning/codeql` workflow, which uploads *code
quality* results rather than security ones — `python.quality.sarif` in its
log, where the security analysis produced `python.sarif`. That is a
separate setting with an endpoint of its own, the "Code quality" section
below, and the endpoint above reports nothing about it:

```shell
gh api repos/btclib-org/btclib-secp256k1/actions/workflows \
  --jq '.workflows[] | select(.path | startswith("dynamic/"))
        | {name, path, state}'
```

What the file asks for is read off its own triggers; what was actually
analyzed, and under which ref and category, is the API's answer:

```shell
gh api repos/btclib-org/btclib-secp256k1/code-scanning/analyses \
  --jq '.[] | {ref, category, analysis_key, created_at}'
```

The category is what ties an upload to the ones before it, so
`codeql.yml` spells it exactly as the setting did, `/language:python` and
`/language:actions`: an upload under a new category closes every open alert
as fixed and opens a copy of it. The `analysis_key` is the one thing that
does change, from `dynamic/github-code-scanning/codeql:analyze` to this
workflow's path, and no alert is keyed on it.

`Dependency Graph` is not a candidate for the rule either: its runs are
`dynamic`, GitHub submitting the graph after a push rather than checking a
pull request.

**PATCH the sub-endpoint, never PUT the whole protection object**: a
partial PUT drops the reviews, the signatures and the rest. And `-F`,
not `-f`, for `strict` — `gh api`'s `-f` sends every value as a string,
and GitHub refuses `"true"` where a boolean is declared:

```shell
sub=branches/main/protection/required_status_checks
gh api "repos/btclib-org/btclib-secp256k1/$sub" -X PATCH -F strict=true \
  -F 'checks[][context]=test: every job passed' -F 'checks[][app_id]=15368' \
  -F 'checks[][context]=Lint and type-check' -F 'checks[][app_id]=15368' \
  -F 'checks[][context]=Build the documentation' -F 'checks[][app_id]=15368'
```

`checks[][…]` repeated is how one array of objects is written: `-F` pairs
each `context` with the `app_id` that follows it, and sends the number as a
number. Reading the body before sending it is a probe against a path that
does not exist, which reports a 404 and changes nothing:

```shell
gh api --verbose -X POST "repos/btclib-org/btclib-secp256k1/zzz-probe" \
  -F 'checks[][context]=A' -F 'checks[][app_id]=15368' \
  | sed -n '/^{/,/^}/p'
```

Renaming a required check is the one change that cannot be made in a pull
request. The rule names a context by the job's display name, so the pull
request that renames the job stops producing the old name and never
produces the one the rule is still waiting for. The rule moves first,
against the branch, and then the pull request that renames the job reports
the name the rule now wants; `enforce_admins` being off is what makes the
window survivable rather than a lock. Every open pull request that predates
the rename is blocked until it is rebased, which is the reason to do it
with none open but the one doing the renaming.

## Code quality

The analysis the generated workflow above was left running, and it is off.
Its setting is not `code-scanning/default-setup`, and the Actions API is
not the way in either: a generated workflow is not one this repository
owns, and `actions/workflows/<id>/disable` answers 422. The endpoint that
reports the setting is the one that sets it:

```shell
gh api repos/btclib-org/btclib-secp256k1/code-quality/setup
# {"state":"not-configured","languages":["python"], ...}

gh api -X PATCH repos/btclib-org/btclib-secp256k1/code-quality/setup \
  -F state=not-configured
```

What decided it is the ceiling the section above already trades against,
not the queries. `Analyze (python)` ran on every pull request and every
push to `main` — `Code Quality: PR #N` in the run list — for some 52
seconds of a slot each time, and the concurrent jobs the plan allows are
shared with every other repository in the organization, where the same
setting was on. *Plan-gated settings* below carries the figure.

What it produced in exchange cannot be read from outside a browser. There
is no `code-quality/alerts` and no `code-quality/analyses`, both 404, and
a quality upload appears in neither endpoint that does answer: the alert
list is empty, and every analysis carries `codeql.yml`'s own category.

```shell
gh api "repos/btclib-org/btclib-secp256k1/code-scanning/alerts?per_page=100" \
  --jq length
gh api "repos/btclib-org/btclib-secp256k1/code-scanning/analyses?per_page=100" \
  --jq '[.[] | .category] | unique'
```

`state=configured` is the way back, and the argument for it is that these
queries are a class of finding nothing else here makes: ruff, mypy and the
spell checkers are the cover, and they are not the same questions. What
refuses them is the ceiling, so a fleet not waiting for slots is what
would change the answer.

## Branch protection

`main` is the repository's default branch:

```shell
gh api repos/btclib-org/btclib-secp256k1 --jq '.default_branch'
# main
```

Its protection is all read from the endpoint above: `strict` with the three
checks already described, one approving review with
`dismiss_stale_reviews`, **required signatures**, linear history, no force
pushes, no deletions, `required_conversation_resolution`, and
`enforce_admins` **off** — an administrator can bypass all of it, matching
another repository in the organization now and for the same reason: a
solo-maintainer repository cannot satisfy "one approving review" from the
author, GitHub refusing self-approval, so the review is a stop rather than
a speed bump, and the admin bypass is the only way past it without a
second maintainer to add.

```shell
gh api -X DELETE \
  repos/btclib-org/btclib-secp256k1/branches/main/protection/enforce_admins
```

Turned off after being on through the 0.7.1 release, whose squash merge
(see RELEASING.md) is what the previous setting actually cost: with
`enforce_admins` on, neither the force push nor the six unsigned commits
among the ninety-two the development branch carried could have gone back
onto the trunk, admin included. Off would not undo that squash today
either — that commit is what PyPI's PEP 740 attestations for 0.7.1 are
bound to, and moving it now would desynchronize a published release from
what it attests to rather than restore anything. What changed is only
whether the next incident has the same escape hatch another repository in
the organization already keeps.

One protected branch is the whole of it, which is a consequence of there
being one long-lived branch:

```shell
gh api repos/btclib-org/btclib-secp256k1/branches \
  --jq '.[] | "\(.name) protected=\(.protected)"'
```

The minimal rule that used to sit on the development branch — no force
pushes, no deletions, linear history, and nothing else — went with the
branch it protected. Nothing was weakened by that: what it guarded was a
trunk a pull request did not have to pass through, and every change now
reaches `main` through the rules above.

## The rulesets, and what their bypass is for

The rulesets on `main` sit beside that protection, and what separates
them is who may bypass:

```shell
gh api repos/btclib-org/btclib-secp256k1/rulesets \
  --jq '.[] | "\(.name) \(.enforcement) bypass=\(.bypass_actors | length)"'
```

`main-integrity` is what [section 11 of the organization
standard](https://github.com/btclib-org/.github#11-github-settings)
names — a verified signature, linear history, no force push, no branch
deletion — with **no bypass actor at all**, which is what makes "on
every commit, not at review time" true of an administrator too,
`enforce_admins` above being off. `main-self-merge` is the pull request
rule, and names the maintainer as one; the listing above answers each
ruleset's id, and the rules and the bypass of each are read from it:

```shell
gh api --jq '{rules: [.rules[].type], bypass: [.bypass_actors[].actor_type]}' \
  repos/btclib-org/btclib-secp256k1/rulesets/<id>
```

The id goes after `--jq` rather than into the middle of the call, so the
line ends in the placeholder and a paste made before it is filled in has
nothing for its `>` to open — section 9 of the organization standard is
where that rule is.

The split is the point. The review is the rule a solo maintainer cannot
satisfy, GitHub refusing a self-approval; the integrity rules are the
ones nobody should be able to. One ruleset each is what lets the first
be bypassed without the second going with it.

**What the bypass is for is the review, and nothing else.** It is set to
`pull_request` mode, which excuses its holder from the rule *while
merging a pull request* and at no other time — so it answers the one
thing a solo-maintainer repository cannot produce, an approving review
from somebody else, and answers nothing further. A direct push to `main`
is refused for everyone, the holder included: outside a pull request
there is no bypass to apply, and the rule says changes come through one.

The ruleset also names `squash` as the only merge method it will accept,
so that constraint is stated where the rule is and not only in the
repository setting "Merge methods" below reads back.

```shell
gh api --jq '{bypass: [.bypass_actors[].bypass_mode],
              methods: [.rules[] | select(.type=="pull_request")
                                 | .parameters.allowed_merge_methods]}' \
  repos/btclib-org/btclib-secp256k1/rulesets/<id>
```

The other mode, `always`, permits a direct push as well, and it is not
used here. What it would buy is a landing that keeps the maintainer's
own signature on the commit; what it costs is a `main` any local mistake
can reach. The first half is worth nothing once the branch rule is read
as asking for a valid signature rather than for a particular signer,
which makes GitHub's web-flow key as good as the maintainer's.

**The bypass is not the whole of the permission.** The protection above
still carries `required_pull_request_reviews`, and what clears it for
the maintainer is `enforce_admins` being `false` together with holding
`admin`; the ruleset bypass alone would not be enough. Turning
`enforce_admins` on would deadlock every solo merge instead, the classic
review requirement having no bypass list to be named in.

**Every landing is a pull request GitHub merges**, which retires the
question this section used to answer at length: whether the object
arriving on `main` is the one the pull request names. It always is.
GitHub marks the pull request **Merged**, the `Closes #N` in its
description closes the issue, and `delete_branch_on_merge` takes the
head branch a second later.

**A third ruleset, `tag-integrity`, targets tags rather than `main`.**
`release.yml` publishes to PyPI on `push: tags: ["v*"]`, and until this
ruleset existed that tag was the one unattested link in an otherwise
fully-signed chain: every commit reaching `main` carries a verified
signature, but nothing stopped an annotated, unsigned tag from being
the one that triggered a release. RELEASING.md's tagging step already
produces a signed tag (`git tag -s`); `tag-integrity` enforces the same
thing at the repository-settings level — `target: tag`,
`refs/tags/v*`, `required_signatures`, **no bypass actor at all**, the
same "on every push, not at review time" shape as `main-integrity`, for
the same reason. It carries no `deletion` or `non_fast_forward` rule:
RELEASING.md's own recovery path deletes and re-tags a release that
failed before the PyPI upload, and either rule would block that.

```shell
gh api --jq '{name, target, conditions, rules: [.rules[].type],
              bypass: .bypass_actors}' \
  repos/btclib-org/btclib-secp256k1/rulesets/<id>
```

## Head branches after a merge

`delete_branch_on_merge` is on, since 7 August 2026:

```shell
gh api repos/btclib-org/btclib-secp256k1 --jq '.delete_branch_on_merge'
```

GitHub deletes the head branch of a pull request when it is merged, which
is what keeps the branch list a list of live work rather than a history of
every change ever made. It was turned on after a sweep that removed five
merged head branches from here, none of which anybody could tell from live
work without comparing each against the trunk commit by commit.

The case it does not cover is deliberate: a pull request **closed without
merging** keeps its head branch, GitHub having no way to know whether that
work was abandoned or is waiting, so those are the ones still worth
looking at now and then. The setting has a second exception — a protected
branch is never deleted, protection winning over it — which used to reach
the release pull request, whose head branch was protected. No head branch
is protected now.

**The setting hangs on the merge GitHub records**, and every landing
here is one it records, so it fires on its own and nothing is left to
delete by hand. Measured on
<https://github.com/btclib-org/btclib-secp256k1/pull/185>: marked Merged
at 12:39:19 and `head_ref_deleted` at 12:39:20, with nobody asking. The
thing not to do is get ahead of it — deleting the branch before the
reconciliation is what leaves a pull request Closed with its commit on
`main` all the same, as has happened once at another repository in the
organization.

## Merge methods

**Squash is the only *button* enabled**, so it is a setting and not only
the convention CONTRIBUTING.md states:

```shell
gh api repos/btclib-org/btclib-secp256k1 \
  --jq '{allow_squash_merge, allow_merge_commit, allow_rebase_merge,
         squash_merge_commit_title, squash_merge_commit_message}'
# {"allow_merge_commit":false,"allow_rebase_merge":false,
#  "allow_squash_merge":true,"squash_merge_commit_message":"COMMIT_MESSAGES",
#  "squash_merge_commit_title":"COMMIT_OR_PR_TITLE"}
```

The two `squash_merge_commit_*` fields shape the commit the button
writes, and section 11 states what they are set to: `COMMIT_OR_PR_TITLE`
lands a single-commit branch under its own subject and a longer one
under the pull request's title, and `COMMIT_MESSAGES` makes the branch's
commit messages the body — never the pull request's description, which
`PR_BODY` would take with nothing here to show the flip.

**It is also how a pull request lands here**, auto-merge below being
what presses it once the review and the checks are in. The commit that
reaches `main` is therefore one GitHub composes and signs with its
web-flow key, which is the valid signature the rule asks for.

The merge commit was refused by `main`'s required linear history already,
so turning it off takes away a button that could not have worked. The
rebase merge could have, and that is the one this removes: it replays a
branch's commits onto `main`, where one change is one commit and the steps
of a review belong to the pull request that carries them.

What a single method takes away is the dropdown. GitHub preselects
whichever method was used last, and the dialog below carries the same
one, so the answer could be given hours before anything merged and by
whoever switched auto-merge on. One method is one entry: there is no
wrong one to preselect, and nothing to read before pressing — and the
ruleset above names the same one, so the constraint holds even if the
repository setting is flipped.

## Auto-merge

`allow_auto_merge` is on, since 11 August 2026:

```shell
gh api repos/btclib-org/btclib-secp256k1 --jq '.allow_auto_merge'
```

It bypasses nothing: GitHub offers the button **only on a pull request
that cannot be merged immediately**, and then merges it when the last
thing blocking it clears — one of the required checks, the approving
review, an unresolved conversation. Where nothing is pending there is
nothing to wait for and the button is not offered at all, so this
setting does something here precisely because the rule on `main` is what
it is: the matrix is tens of jobs compiling C, and `test.yml`'s header
measures what waiting for it costs.

**Required signatures survive it**, measured rather than assumed,
because GitHub composes the squash commit server-side and signs it with
its own key exactly as a press of the button does. That the signer is
GitHub rather than the author is not a trade this setting makes on its
own: it is what any landing here carries, the rule asking for a valid
signature and not for a particular signer. The check is worth making on
whatever landed all the same:

```shell
gh api --jq '.commit.verification | {verified, reason}' \
  repos/btclib-org/btclib-secp256k1/commits/<sha>
```

**What auto-merge will press was chosen when it was switched on, rather
than when the merge happened.** That dropdown carries one entry, squash
being the only method either the repository setting or the ruleset will
accept — "Merge methods" above is both — so switching auto-merge on
answers nothing a reviewer has to catch before it lands. What a pull
request is holding is still worth reading, the wait itself being what
this bypasses:

```shell
gh pr view --repo btclib-org/btclib-secp256k1 --json autoMergeRequest <n>
```

## Token permissions

**The default `GITHUB_TOKEN` is read-only repository-wide**, so a job
needing more declares it:

```shell
gh api repos/btclib-org/btclib-secp256k1/actions/permissions/workflow
# {"default_workflow_permissions":"read",
#  "can_approve_pull_request_reviews":false}
```

The whole object rather than one field of it: a run that can approve a
pull request is a way around the rule that somebody other than the
author approves, so `can_approve_pull_request_reviews` is read back
beside the token's own scope and not left to be assumed.

What asks for more asks per job, and the declarations are the record of
it — anchored, so that a comment naming a permission stays out of the
answer:

```shell
git grep -n ': write$' -- .github/workflows
```

`release.yml` takes `contents: write` on `github-release` and `id-token:
write` on its publish jobs, which is what Trusted Publishing exchanges,
with `attestations: write` beside it on `attest`. `claude-review.yml`
takes `pull-requests: write` and `id-token: write` on each of its jobs.
`codeql.yml` and `scorecard.yml` take
`security-events: write` on the job that files a SARIF as code scanning
alerts, and `scorecard.yml` takes `id-token: write` besides, for the
transparency-log entry its published score rests on.
`vendored-vectors.yml` takes `issues: write` on the job that opens the
drift issue, and that file's header says why it takes a step the other
sentinels deliberately do not.

One elevation per job is the shape to keep — the job that writes
releases holds no OIDC token, and the job that signs writes no release.
The workflow-level `permissions: contents: read` in every file is belt and
braces; keep it, it is what makes the intent readable where the job is.

What the call above cannot say is whether either value is this
repository's own or the organization's, no endpoint reporting an
override and none clearing one: [the standard's tokens
section](https://github.com/btclib-org/.github/blob/main/README.md#tokens-publishing-scanning)
is where that is argued, and what this file adds is which of the two
states this repository is in.

It is **untested**, and the date is what makes it so: this repository
already held `read` when the organization default moved there on
21 August 2026, so it was not among the ones that could be *seen*
following the move, and an override set before that day reads back
exactly like an inheritance does. Nobody has recorded setting one here,
which is weaker than knowing there is none — `bitcoin-core-rpc` is the
repository where one was found, by that same move, and its
`REPOSITORY.md` records it as pinned.

So whoever moves the organization default reads this repository back
afterwards rather than assuming it followed, and moves it by hand where
it did not:

```shell
gh api -X PUT repos/btclib-org/btclib-secp256k1/actions/permissions/workflow \
  -f default_workflow_permissions=read \
  -F can_approve_pull_request_reviews=false
```

## Publishing

Both environments require a review, so an upload waits for a person:

```shell
gh api repos/btclib-org/btclib-secp256k1/environments \
  --jq '.environments[] | {name, protection_rules}'
```

`pypi` and `testpypi` each have `fametrano` as the required reviewer.
`pypi` carries a deployment branch policy besides — one custom rule
admitting the tag pattern `v*`, that environment being reachable only from
a tag — while `testpypi` has none, being reached from a branch by
dispatch:

```shell
gh api \
  repos/btclib-org/btclib-secp256k1/environments/pypi/deployment-branch-policies
# {"name": "v*", "type": "tag"}
```

The asymmetry is worth reading rather than assuming: a policy admitting
branches alone would refuse the deployment *after* the whole matrix had
been built, and no rehearsal would reveal it, reaching the other
environment.

What that rule constrains is the *name* of the ref and nothing else. A
`v*` tag pushed on a branch head, on a stale state or on a fork-synced
commit satisfies it exactly as the release tag does, so it is not the
check that a release is a release: the `version-check` job of
`release.yml` fails a tag that is not an ancestor of `main`, before the
matrix builds anything. [RELEASING.md](./RELEASING.md) has the rest,
including what a mismatched trusted publisher looks like and why
self-review stays allowed.

**On TestPyPI the project is not ours.** The name carries an unrelated
`0.0.1` from 2021, and a trusted publisher can only be registered by an
owner: what unblocked the rehearsal of 0.7.1 was being made one, which is
a permission granted rather than a project owned. If a rehearsal ever
fails again with `invalid-publisher`, that is the first thing to check.

## Dependabot

No entry names a target: with no `target-branch` Dependabot opens
against the default branch, which is the only branch a change lands on. A
setting that names nothing cannot name something that is gone, which is
what the `dev` it used to name became.

```shell
gh api repos/btclib-org/btclib-secp256k1/contents/.github/dependabot.yml \
  --jq '.content' | base64 -d | grep -E 'package-ecosystem|target-branch'
```

`github-actions` moves the SHA pins, `uv` the locked dependencies, and
`gitsubmodule` signals that a vendored library has moved upstream. The
comment beside that last entry in `.github/dependabot.yml` says how it
reaches the submodules and what its pull request leaves open. That file
is validated by the `check-dependabot` hook, a typo there otherwise
updating nothing and saying nothing.

Dependabot security updates are a repository setting rather than a line
in that file, and they are on:

```shell
gh api repos/btclib-org/btclib-secp256k1/automated-security-fixes
# {"enabled":true,"paused":false}
```

## Private vulnerability reporting

```shell
gh api repos/btclib-org/btclib-secp256k1/private-vulnerability-reporting
# {"enabled":true}
```

On. It is what puts the *Report a vulnerability* button on the Security
tab, and `.github/ISSUE_TEMPLATE/config.yml` links
`/security/advisories/new` on the strength of it.

## Plan-gated settings

Some settings cannot be enabled and fail silently:

```shell
gh api repos/btclib-org/btclib-secp256k1 --jq '.security_and_analysis'
```

Secret scanning and push protection are enabled;
`secret_scanning_non_provider_patterns` and
`secret_scanning_validity_checks` are `disabled` and cannot be turned on,
those needing paid Secret Protection. The API answers a PATCH with 200 and
leaves them off — **do not read that 200 as success.** The
`detect-secrets` hook is the compensating control, and CONTRIBUTING.md
carries what maintaining its baseline costs.

The other plan-gated number is not a setting at all, and it is the one
that has moved this repository's workflows twice: how many jobs may run
at once. It is an attribute of the organization, shared by every
repository in it, and the plan is what sets it — `free`, read back
rather than assumed:

```shell
gh api orgs/btclib-org --jq .plan.name
```

[GitHub's own table](https://docs.github.com/en/actions/reference/limits)
is the authority, and two of its numbers matter here: on the free plan
they are twenty concurrent jobs, of which five may be macOS runners.

**Read the second number before spending anything on the first.** The
twenty is what `os-windows.yml`'s header measured against, and a paid plan
raises it well before it moves the second. The five is the ceiling behind
the macOS queue `test.yml`'s header measures — a macOS column that queued
for tens of minutes was far more jobs than five slots could clear at once,
and only Enterprise changes that arithmetic. So the split that took those
cells out of the merge gate is not a workaround for a plan — on this
repository it is the answer, and the plan below Enterprise that would undo
it does not exist.

What Team would buy is the rest: the Linux and Windows crowding, and the
contention with the other repositories of the organization,
`bitcoin-core-rpc` and one more each asking for well more than the twenty
on their own commits too. Whether that is worth three seats is a question
for whoever pays for them, and it is recorded here so that it is asked
with the second number in view.

## Features

```shell
gh api repos/btclib-org/btclib-secp256k1 --jq '{visibility, has_issues}'
# {"has_issues":true,"visibility":"public"}
```

Section 10's `scorecard` sentinel rests on the first answer: public is
what it reads at all, so a flip to private leaves `scorecard.yml` and
`README.md`'s badge standing while the run stops producing a score, and
`.visibility` above is what puts that flip one command from being seen.

`has_issues` is what `CONTRIBUTING.md`'s *The issue tracker* rests on —
an issue about this tree alone stays here — and so does the
`.github/ISSUE_TEMPLATE/` section 16's checklist gives every repository.

## Topics

The topics are `pyproject.toml`'s `keywords`, entry for entry: one list
spelled in two places, and the same spelling in both is what lets a drift
between them be seen at all. Lowercase throughout, a GitHub topic being
lowercase or not a topic. They were set on 7 August 2026, from the list #81
wrote: that pull request could change the packaging metadata and not the
repository, these settings living outside the tree, which is why it landed
with the topics still empty.

Nothing in the tree holds the two lists together, so this is the command
that does: it prints the difference and exits nonzero on one.

```shell
diff <(gh api repos/btclib-org/btclib-secp256k1 --jq '.topics[]' | sort) \
     <(sed -n '/^keywords = \[/,/^]/s/^ *"\(.*\)",$/\1/p' pyproject.toml \
       | sort)
```

An empty right-hand side is the `sed` having stopped matching
`pyproject.toml`'s spelling rather than an empty `keywords`, and it makes
`diff` name every topic: run the `sed` alone before reading that as
drift. The left-hand side names the repository, and the right-hand side
is whatever `pyproject.toml` the shell can see, so this one is run from a
checkout of this repository and not merely from anywhere.

Both sides are sorted because GitHub returns the topics in an order of
its own rather than the one it was given: a reordering there is not
drift, and only `pyproject.toml`'s order is the deliberate one. The
comment above the `keywords` list says what decided it, and why `musig2`
and `bip324` are in a list of what this package wraps.

## No website

This repository serves no GitHub Pages site, so no file in its root is a
URL anywhere, and the endpoint answers 404:

```shell
gh api repos/btclib-org/btclib-secp256k1/pages
```

**`.homepage` names the tree's own Read the Docs project instead**, read
back from the endpoint rather than from `pyproject.toml`'s own copy of it
(issue btclib-org/.github#533):

```shell
gh api repos/btclib-org/btclib-secp256k1 --jq '.homepage'
# https://btclib-secp256k1.readthedocs.io
```

`[project.urls] homepage` carries the identical string: a releasing tree's
home is its own documentation, not `btclib.org`, the sibling's project
page the field named before.

## Read the Docs, which is btclib-secp256k1.readthedocs.io

The project's slug is `btclib-secp256k1`, and its public API answers
without a token for what section 11 asks of the project — `latest`
follows the default branch, `stable` is the highest release tag, and an
automation rule activates each new tag:

```shell
p=https://app.readthedocs.org/api/v3/projects/btclib-secp256k1
curl -s "$p/" | jq -c '{default_branch, repository: .repository.url}'
# {"default_branch":"main",
#  "repository":"https://github.com/btclib-org/btclib-secp256k1.git"}
curl -s "$p/versions/?active=true" \
  | jq -c '.results[] | select(.slug == "latest" or .slug == "stable")
           | [.slug, .type, .ref]'
# ["stable","tag","v0.8.0.4"]
# ["latest","branch",null]
git tag --list 'v*' --sort=version:refname | tail -1
# v0.8.0.4
```

`repository.url` says which repository the slug serves. `latest` is a
branch, and the branch it follows is the project's `default_branch`;
`stable` is a tag, and its `ref` is the one `git tag` sorts highest. The
tags beside those two in the same answer are the automation rule's
result rather than the rule, which that API does not expose —
`automation-rules/` answers 404 where an endpoint needing a token, such
as `redirects/`, answers 401.

**What connects this repository to Read the Docs is the organization-wide
`read-the-docs-community` GitHub App, not a per-repository webhook.**

```shell
gh api orgs/btclib-org/installations \
  --jq '.installations[] | select(.app_slug == "read-the-docs-community")
        | [.app_slug, .repository_selection]'
# ["read-the-docs-community","all"]
```

`repository_selection: all` is what makes that the connection for every
repository of the organization at once, this one included, rather than a
setting this repository carries on its own. The repository itself carries
no hook:

```shell
gh api repos/btclib-org/btclib-secp256k1/hooks --jq length
# 0
```

A hook that command finds is stale and is deleted rather than repaired:
that is section 11's rule, and the secret is its reason — Read the Docs
issues it on the project's own integration page and GitHub returns it
masked, so nothing read back from the repository says whether a hook
still carries the right one.

## What this file passes over

The API answers for more than this repository decides, and what is left
out below is left out by the scope above rather than by oversight.

**What no call sets.** `gh api repos/btclib-org/btclib-secp256k1`
answers with the repository document, most of which is URLs, counts and
derived state. The fields of it that are settings here are the ones the
sections above quote.

**A credential this repository spends and does not hold.**
`claude-review.yml` reads `secrets.CLAUDE_CODE_OAUTH_TOKEN`, and both
secret stores here answer empty for it:

```shell
gh api repos/btclib-org/btclib-secp256k1/actions/secrets --jq .total_count
gh api repos/btclib-org/btclib-secp256k1/dependabot/secrets \
  --jq .total_count
# 0, both
gh api orgs/btclib-org/actions/secrets \
  --jq '.secrets[] | [.name, .visibility]'
gh api orgs/btclib-org/dependabot/secrets \
  --jq '.secrets[] | [.name, .visibility]'
# ["CLAUDE_CODE_OAUTH_TOKEN","all"], both
```

Those two zeros record a decision, and it is section 11's: the token is
an organization secret at `visibility=all`, in both stores, so a
repository adopting the workflow configures nothing for it, and a copy
of it in a store here would be that decision undone.

**A switch this repository does not set.** `claude-review.yml` guards
its jobs with `vars.CLAUDE_REVIEW_ENABLED`, and neither variable store
holds it:

```shell
gh api repos/btclib-org/btclib-secp256k1/actions/variables --jq .total_count
# 0
gh api orgs/btclib-org/actions/variables --jq '.variables[].name'
# (nothing)
gh api orgs/btclib-org/actions/variables --jq .total_count
# 0
```

The organization secret above answering with a name is what makes these
zeros absences rather than an endpoint that answers empty for everyone.
The variable store prints nothing at all when it answers, so its own
`total_count` of `0` is what shows the call reached it: one that does not
reach it prints an error and exits non-zero. Section 11 reads that empty
name list as `vars.CLAUDE_REVIEW_ENABLED`'s off state, an undefined
`vars.X` being the empty string. Both stores are read because a variable
set here would take precedence over one of the same name set on the
organization, so the organization's answer alone would not show the
switch off for this tree.

**A facility nobody reached for.** Self-hosted runners, deploy keys,
autolinks and custom property values each answer empty, and an empty
answer there records no decision:

```shell
for e in actions/runners keys autolinks properties/values; do
  printf '%-24s ' "$e"
  gh api "repos/btclib-org/btclib-secp256k1/$e" \
    --jq 'if type == "array" then length else .total_count end'
done
```

Environments answer non-empty, and *Publishing* above is where they are
read back; the webhook list answers empty, and *Read the Docs* above is
where that zero is read; the repository's variable store answers empty,
and *A switch this repository does not set* above is what reads it.
Whichever of the facilities listed here is used one day arrives with the
section that uses it.

**A field the standard states no rule about, and no call above answers
alongside one it does.** `allow_forking`, `allow_update_branch`,
`has_discussions`, `has_downloads`, `is_template` and
`web_commit_signoff_required` are in the repository document, in none of
the `--jq` objects here, and named nowhere in the standard:

```shell
std=$(mktemp)
gh api repos/btclib-org/.github/contents/README.md \
  -H 'Accept: application/vnd.github.raw' > "$std"
for f in allow_forking allow_update_branch has_discussions \
         has_downloads is_template web_commit_signoff_required; do
  printf '%-30s %s\n' "$f" "$(grep -c "$f" "$std")"
done
grep -c delete_branch_on_merge "$std"
rm "$std"
```

The `delete_branch_on_merge` count is the control that makes those zeros
an absence rather than a read of nothing. Recording a field on no rule
grows this file with GitHub's API rather than with the standard, and the
price is that a change to any of them is invisible here.

`has_wiki` and `has_projects` are outside the perimeter by section 11's
own sentence, which states no rule about either, so this file neither
reads them back nor explains an answer to them. That sentence is what
the grep above would find, which is why the pair is not in its list.
